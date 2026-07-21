"""Dysk Google jako magazyn paczek „mózgu" agenta (Faza 1 chmury).

Świadomie BEZ bibliotek Google — czysty `requests`, spójnie z resztą projektu
(`stt/license/update` też chodzą na `requests`). Dzięki temu paczka aplikacji
nie rośnie o kilkanaście megabajtów zależności, a cała logika mieści się tutaj.

Logowanie: OAuth 2.0 dla **aplikacji desktopowej** — klient PUBLICZNY, więc
zamiast polegać na sekrecie stosujemy **PKCE** (jednorazowa zagadka: apka losuje
sekret, wysyła jego skrót, a przy odbiorze kodu pokazuje oryginał — podsłuchany
kod jest bezużyteczny dla kogoś, kto zagadki nie zna). Zgoda odbywa się
w przeglądarce, a odpowiedź łapie mikroserwer na `127.0.0.1` (pętla lokalna,
nic nie wychodzi poza komputer).

Uprawnienie: **`drive.file`** — apka widzi WYŁĄCZNIE pliki, które sama utworzyła.
Nie ma wglądu w resztę Dysku użytkownika. To zakres „niewrażliwy", więc Google
nie wymaga od nas audytu (patrz `docs/PLAN-CHMURA-SYNC.md`, sekcja 9.4).

⚠️ Metody są BLOKUJĄCE (sieć + oczekiwanie na zgodę w przeglądarce). GUI musi
wołać je w wątku roboczym, nigdy w wątku okna.

Testowalność: wszystkie adresy Google są parametrami konstruktora, a otwieranie
przeglądarki wstrzykiwanym wywołaniem → `tools/test-cloud-drive.py` przepuszcza
pełny scenariusz przez atrapę serwera, bez sieci i bez konta usera.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable, Dict, List, Optional

import requests

from .cloud_provider import CloudProvider

# Adresy Google (nadpisywalne w testach)
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://www.googleapis.com/drive/v3"
UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"

# Najsłabsze uprawnienie, jakie wystarcza: tylko pliki utworzone przez tę apkę.
SCOPE = "https://www.googleapis.com/auth/drive.file"

FOLDER_MIME = "application/vnd.google-apps.folder"
BUNDLE_MIME = "application/octet-stream"

HTTP_TIMEOUT = 30          # [s] pojedyncze wywołanie REST
CONSENT_TIMEOUT = 300      # [s] ile czekamy, aż user kliknie zgodę w przeglądarce
TOKEN_MARGIN = 120         # [s] odświeżamy token z zapasem przed wygaśnięciem


class CloudError(RuntimeError):
    """Błąd komunikacji z chmurą (czytelny dla GUI, BEZ wartości tokenów)."""


class CloudAuthError(CloudError):
    """Problem z logowaniem/uprawnieniami — user musi połączyć konto ponownie."""


def _b64url(raw: bytes) -> str:
    """base64url bez znaków wypełnienia (wymóg PKCE)."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class _ConsentHandler(BaseHTTPRequestHandler):
    """Odbiera powrót z przeglądarki po zgodzie (albo odmowie)."""

    result: Dict[str, str] = {}

    def do_GET(self):                                    # noqa: N802 (API biblioteki)
        query = urllib.parse.urlparse(self.path).query
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        _ConsentHandler.result = params
        ok = "code" in params
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        tytul = "Połączono z Dyskiem Google" if ok else "Nie udało się połączyć"
        tresc = ("Możesz zamknąć tę kartę i wrócić do aplikacji."
                 if ok else "Wróć do aplikacji i spróbuj ponownie.")
        self.wfile.write(
            f"<!doctype html><meta charset='utf-8'>"
            f"<body style='font-family:sans-serif;background:#1b1b1d;color:#eae6f2;"
            f"display:flex;flex-direction:column;align-items:center;justify-content:center;"
            f"height:90vh'><h2>{tytul}</h2><p>{tresc}</p></body>".encode("utf-8"))

    def log_message(self, *args):
        """Cisza — domyślnie logowałby adres z KODEM autoryzacji na stderr."""


class GoogleDriveProvider(CloudProvider):
    """Magazyn paczek „mózgu" na Dysku Google."""

    def __init__(
        self,
        client_id: str,
        client_secret: str = "",
        token_path: Optional[Path] = None,
        folder_name: str = "Vibe Coding Assistant",
        *,
        auth_url: str = AUTH_URL,
        token_url: str = TOKEN_URL,
        api_base: str = API_BASE,
        upload_base: str = UPLOAD_BASE,
        open_browser: Optional[Callable[[str], None]] = None,
        consent_timeout: int = CONSENT_TIMEOUT,
    ) -> None:
        if not client_id:
            raise CloudAuthError("Brak identyfikatora klienta OAuth (client_id).")
        self._client_id = client_id
        self._client_secret = client_secret or ""
        self._token_path = Path(token_path) if token_path else None
        self._folder_name = folder_name
        self._auth_url = auth_url
        self._token_url = token_url
        self._api_base = api_base.rstrip("/")
        self._upload_base = upload_base.rstrip("/")
        self._open_browser = open_browser or webbrowser.open
        self._consent_timeout = consent_timeout

        self._access_token = ""
        self._expires_at = 0.0
        self._refresh_token = ""
        self._folder_id = ""
        self._load_token()

    # ---------------------------------------------------------- poświadczenia

    def _load_token(self) -> None:
        if not self._token_path or not self._token_path.exists():
            return
        try:
            data = json.loads(self._token_path.read_text(encoding="utf-8"))
            self._refresh_token = data.get("refresh_token", "") or ""
            self._access_token = data.get("access_token", "") or ""
            self._expires_at = float(data.get("expires_at", 0) or 0)
        except Exception:
            # Uszkodzony plik = po prostu brak logowania; nie wywracamy apki.
            self._refresh_token = self._access_token = ""
            self._expires_at = 0.0

    def _save_token(self) -> None:
        if not self._token_path:
            return
        payload = {
            "refresh_token": self._refresh_token,
            "access_token": self._access_token,
            "expires_at": self._expires_at,
        }
        self._token_path.parent.mkdir(parents=True, exist_ok=True)
        # Zapis przez plik tymczasowy + prawa 600 JESZCZE przed wpisaniem treści,
        # żeby token ani przez chwilę nie był czytelny dla innych kont.
        tmp = self._token_path.with_suffix(".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, self._token_path)
        try:
            os.chmod(self._token_path, 0o600)
        except OSError:
            pass

    def is_connected(self) -> bool:
        """Czy mamy zapisane logowanie (bez ruszania sieci)?"""
        return bool(self._refresh_token)

    def disconnect(self) -> None:
        """Zapomnij logowanie (przycisk „Odłącz konto")."""
        self._access_token = self._refresh_token = ""
        self._expires_at = 0.0
        self._folder_id = ""
        if self._token_path and self._token_path.exists():
            try:
                self._token_path.unlink()
            except OSError:
                pass

    # ------------------------------------------------------------- logowanie

    def auth(self) -> None:
        """Zapewnij ważny dostęp: odśwież zapisane logowanie albo poproś o zgodę."""
        if self._access_token and time.time() < self._expires_at - TOKEN_MARGIN:
            return
        if self._refresh_token:
            try:
                self._refresh()
                return
            except CloudAuthError:
                # Bilet odnowienia stracił ważność (np. user cofnął dostęp)
                # → jedyne wyjście to ponowna zgoda w przeglądarce.
                self._refresh_token = ""
        self._consent_flow()

    def _refresh(self) -> None:
        data = {
            "client_id": self._client_id,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
        }
        if self._client_secret:
            data["client_secret"] = self._client_secret
        self._exchange(data)

    def _consent_flow(self) -> None:
        """Pełna zgoda: przeglądarka → mikroserwer na pętli lokalnej → token."""
        verifier = _b64url(secrets.token_bytes(48))
        challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
        state = secrets.token_urlsafe(24)

        _ConsentHandler.result = {}
        server = HTTPServer(("127.0.0.1", 0), _ConsentHandler)
        server.timeout = self._consent_timeout
        redirect_uri = f"http://127.0.0.1:{server.server_port}/"

        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "access_type": "offline",       # bez tego nie dostaniemy biletu odnowienia
            "prompt": "consent",
        }
        url = f"{self._auth_url}?{urllib.parse.urlencode(params)}"

        # Serwer obsługuje DOKŁADNIE jedno wywołanie, w tle — inaczej zablokowałby
        # otwarcie przeglądarki i całość stanęłaby w miejscu.
        worker = threading.Thread(target=server.handle_request, daemon=True)
        worker.start()
        try:
            self._open_browser(url)
        except Exception as exc:
            server.server_close()
            raise CloudAuthError(f"Nie udało się otworzyć przeglądarki: {exc}") from exc
        worker.join(self._consent_timeout)
        server.server_close()

        result = dict(_ConsentHandler.result)
        _ConsentHandler.result = {}
        if not result:
            raise CloudAuthError(
                "Nie doczekaliśmy się zgody w przeglądarce (upłynął limit czasu).")
        if result.get("error"):
            raise CloudAuthError(f"Google odmówiło dostępu: {result['error']}")
        if result.get("state") != state:
            # Ktoś podrzucił odpowiedź spoza naszego logowania — odrzucamy.
            raise CloudAuthError("Odpowiedź logowania nie pasuje do żądania (state).")
        code = result.get("code")
        if not code:
            raise CloudAuthError("Google nie zwróciło kodu autoryzacji.")

        data = {
            "client_id": self._client_id,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        if self._client_secret:
            data["client_secret"] = self._client_secret
        self._exchange(data)

    def _exchange(self, data: Dict[str, str]) -> None:
        """Wymiana kodu/biletu na token. Nigdy nie loguje wartości tokenów."""
        try:
            resp = requests.post(self._token_url, data=data, timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            raise CloudError(f"Brak połączenia z Google: {exc}") from exc
        if resp.status_code >= 400:
            raise CloudAuthError(
                f"Google odrzuciło logowanie (HTTP {resp.status_code}). "
                f"Sprawdź dane klienta OAuth i spróbuj połączyć konto ponownie.")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise CloudError("Google zwróciło odpowiedź, której nie rozumiemy.") from exc

        self._access_token = payload.get("access_token", "") or ""
        if not self._access_token:
            raise CloudAuthError("Google nie zwróciło tokenu dostępu.")
        self._expires_at = time.time() + float(payload.get("expires_in", 3600) or 3600)
        if payload.get("refresh_token"):
            # Przy odświeżaniu Google zwykle NIE przysyła nowego biletu — stary zostaje.
            self._refresh_token = payload["refresh_token"]
        self._save_token()

    # ----------------------------------------------------------------- Drive

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    def _request(self, method: str, url: str,
                 extra_headers: Optional[Dict[str, str]] = None,
                 **kw) -> requests.Response:
        """Wywołanie REST z jedną automatyczną próbą po wygaśnięciu tokenu."""
        self.auth()
        kw.setdefault("timeout", HTTP_TIMEOUT)

        def _hdrs() -> Dict[str, str]:
            h = self._headers()
            if extra_headers:
                h.update(extra_headers)
            return h

        try:
            resp = requests.request(method, url, headers=_hdrs(), **kw)
            if resp.status_code == 401:
                self._access_token = ""          # wymuś odświeżenie i spróbuj raz
                self.auth()
                resp = requests.request(method, url, headers=_hdrs(), **kw)
        except requests.RequestException as exc:
            raise CloudError(f"Brak połączenia z Dyskiem Google: {exc}") from exc
        if resp.status_code == 403:
            raise CloudAuthError(
                "Dysk Google odmówił dostępu (403). Połącz konto ponownie.")
        if resp.status_code >= 400 and resp.status_code != 404:
            raise CloudError(f"Dysk Google zwrócił błąd HTTP {resp.status_code}.")
        return resp

    def _ensure_folder(self) -> str:
        """Znajdź (albo utwórz) folder aplikacji na Dysku usera."""
        if self._folder_id:
            return self._folder_id
        query = (f"mimeType='{FOLDER_MIME}' and trashed=false "
                 f"and name='{self._folder_name}'")
        resp = self._request("GET", f"{self._api_base}/files",
                             params={"q": query, "fields": "files(id,name)"})
        files = (resp.json() or {}).get("files") if resp.status_code < 400 else None
        if files:
            self._folder_id = files[0]["id"]
            return self._folder_id
        resp = self._request(
            "POST", f"{self._api_base}/files",
            json={"name": self._folder_name, "mimeType": FOLDER_MIME})
        self._folder_id = (resp.json() or {}).get("id", "")
        if not self._folder_id:
            raise CloudError("Nie udało się utworzyć folderu na Dysku Google.")
        return self._folder_id

    def _find_file(self, name: str) -> Optional[str]:
        folder = self._ensure_folder()
        query = f"'{folder}' in parents and trashed=false and name='{name}'"
        resp = self._request("GET", f"{self._api_base}/files",
                             params={"q": query, "fields": "files(id,name)"})
        files = (resp.json() or {}).get("files") if resp.status_code < 400 else None
        return files[0]["id"] if files else None

    def upload(self, name: str, data: bytes) -> None:
        existing = self._find_file(name)
        if existing:
            # Podmiana treści istniejącej paczki — bez tworzenia duplikatu.
            self._request("PATCH", f"{self._upload_base}/files/{existing}",
                          params={"uploadType": "media"}, data=data)
            return
        folder = self._ensure_folder()
        meta = json.dumps({"name": name, "parents": [folder]}).encode("utf-8")
        boundary = "vca-" + secrets.token_hex(16)
        body = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
            + meta
            + f"\r\n--{boundary}\r\nContent-Type: {BUNDLE_MIME}\r\n\r\n".encode()
            + data
            + f"\r\n--{boundary}--\r\n".encode()
        )
        self._request(
            "POST", f"{self._upload_base}/files",
            params={"uploadType": "multipart"}, data=body,
            extra_headers={"Content-Type": f"multipart/related; boundary={boundary}"})

    def download(self, name: str) -> bytes:
        file_id = self._find_file(name)
        if not file_id:
            raise KeyError(name)
        resp = self._request("GET", f"{self._api_base}/files/{file_id}",
                             params={"alt": "media"})
        if resp.status_code == 404:
            raise KeyError(name)
        return resp.content

    def list(self) -> List[str]:
        folder = self._ensure_folder()
        resp = self._request(
            "GET", f"{self._api_base}/files",
            params={"q": f"'{folder}' in parents and trashed=false",
                    "fields": "files(id,name)"})
        files = (resp.json() or {}).get("files") if resp.status_code < 400 else []
        return sorted(f["name"] for f in (files or []))

    def delete(self, name: str) -> None:
        file_id = self._find_file(name)
        if not file_id:
            return                                    # idempotentnie: brak = brak błędu
        self._request("DELETE", f"{self._api_base}/files/{file_id}")
