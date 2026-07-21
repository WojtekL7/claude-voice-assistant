#!/usr/bin/env python3
"""Testy polaczenia z Dyskiem Google — na ATRAPIE serwera, bez sieci i bez konta.

Atrapa udaje Google na tyle serio, ze realnie SPRAWDZA zagadke PKCE i wazność
tokenu — dzieki temu zielony wynik cos znaczy (kontrola negatywna nizej dowodzi,
ze atrapa potrafi odrzucic zle dane).

Uruchomienie:  python3 tools/test-cloud-drive.py
"""
import base64
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core.cloud.google_drive import (                      # noqa: E402
    GoogleDriveProvider, CloudAuthError)

PASS = FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    ok = got == want
    PASS, FAIL = PASS + ok, FAIL + (not ok)
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"         oczekiwano: {want!r}\n         otrzymano : {got!r}")


class FakeGoogle:
    """Minimalny, ale UCZCIWY serwer: sprawdza PKCE, tokeny i uprawnienia."""

    def __init__(self):
        self.challenges = {}        # code -> code_challenge
        self.access = {}            # token -> czy wazny
        self.refresh = set()
        self.files = {}             # id -> {name, parents, data, mimeType}
        self.next_id = 1
        self.browser_opens = 0
        self.pkce_checked = False
        self.break_state = False
        self.expire_next_call = False
        srv = self
        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(srv))
        self.port = self._srv.server_port
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()

    @property
    def base(self):
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        self._srv.shutdown()

    def open_browser(self, url):
        """Udaje przegladarke: wchodzi na ekran zgody i idzie za przekierowaniem."""
        self.browser_opens += 1
        requests.get(url, timeout=10)


def _make_handler(state: FakeGoogle):
    def _json(h, code, obj):
        body = json.dumps(obj).encode()
        h.send_response(code)
        h.send_header("Content-Type", "application/json")
        h.send_header("Content-Length", str(len(body)))
        h.end_headers()
        h.wfile.write(body)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        # ---------------------------------------------------------- logowanie
        def _auth_screen(self, params):
            code = f"code-{len(state.challenges) + 1}"
            state.challenges[code] = params.get("code_challenge", [""])[0]
            redirect = params.get("redirect_uri", [""])[0]
            st = params.get("state", [""])[0]
            if state.break_state:
                st = "PODMIENIONY"
            self.send_response(302)
            self.send_header("Location", f"{redirect}?code={code}&state={st}")
            self.end_headers()

        def _token(self, form):
            grant = form.get("grant_type", [""])[0]
            if grant == "authorization_code":
                code = form.get("code", [""])[0]
                verifier = form.get("code_verifier", [""])[0]
                expected = state.challenges.get(code)
                digest = base64.urlsafe_b64encode(
                    hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
                state.pkce_checked = True
                if expected is None or digest != expected:
                    return _json(self, 400, {"error": "invalid_grant"})
                tok, ref = f"acc-{len(state.access) + 1}", f"ref-{len(state.refresh) + 1}"
                state.access[tok] = True
                state.refresh.add(ref)
                return _json(self, 200, {"access_token": tok, "refresh_token": ref,
                                         "expires_in": 3600})
            if grant == "refresh_token":
                if form.get("refresh_token", [""])[0] not in state.refresh:
                    return _json(self, 400, {"error": "invalid_grant"})
                tok = f"acc-{len(state.access) + 1}"
                state.access[tok] = True
                return _json(self, 200, {"access_token": tok, "expires_in": 3600})
            return _json(self, 400, {"error": "unsupported_grant_type"})

        def _bearer_ok(self):
            tok = (self.headers.get("Authorization") or "").replace("Bearer ", "")
            if state.expire_next_call:
                state.expire_next_call = False
                state.access.pop(tok, None)          # token "wygasl" w trakcie pracy
            return state.access.get(tok, False)

        # ------------------------------------------------------------- Drive
        def _files_list(self, q):
            out = []
            for fid, f in state.files.items():
                if "mimeType='application/vnd.google-apps.folder'" in q:
                    if f["mimeType"] != "application/vnd.google-apps.folder":
                        continue
                m = re.search(r"name='([^']+)'", q)
                if m and f["name"] != m.group(1):
                    continue
                m = re.search(r"'([^']+)' in parents", q)
                if m and m.group(1) not in f["parents"]:
                    continue
                if not m and "in parents" in q:
                    continue
                out.append({"id": fid, "name": f["name"]})
            return {"files": out}

        def do_GET(self):                                  # noqa: N802
            url = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(url.query)
            if url.path == "/auth":
                return self._auth_screen(params)
            if not self._bearer_ok():
                return _json(self, 401, {"error": "unauthorized"})
            if url.path == "/drive/v3/files":
                return _json(self, 200, self._files_list(params.get("q", [""])[0]))
            m = re.match(r"^/drive/v3/files/([^/]+)$", url.path)
            if m and params.get("alt", [""])[0] == "media":
                f = state.files.get(m.group(1))
                if not f:
                    return _json(self, 404, {"error": "not found"})
                self.send_response(200)
                self.send_header("Content-Length", str(len(f["data"])))
                self.end_headers()
                return self.wfile.write(f["data"])
            return _json(self, 404, {"error": "not found"})

        def do_POST(self):                                 # noqa: N802
            url = urllib.parse.urlparse(self.path)
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if url.path == "/token":
                return self._token(urllib.parse.parse_qs(raw.decode()))
            if not self._bearer_ok():
                return _json(self, 401, {"error": "unauthorized"})
            fid = f"id-{state.next_id}"
            state.next_id += 1
            if url.path == "/drive/v3/files":              # utworzenie folderu
                meta = json.loads(raw.decode() or "{}")
                state.files[fid] = {"name": meta.get("name", ""), "parents": [],
                                    "data": b"", "mimeType": meta.get("mimeType", "")}
                return _json(self, 200, {"id": fid})
            if url.path == "/upload/drive/v3/files":       # nowa paczka (multipart)
                head, _, rest = raw.partition(b"\r\n\r\n")
                meta_raw, _, tail = rest.partition(b"\r\n--")
                meta = json.loads(meta_raw.decode("utf-8", "ignore"))
                data = tail.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n--", 1)[0]
                state.files[fid] = {"name": meta["name"], "parents": meta["parents"],
                                    "data": data, "mimeType": "application/octet-stream"}
                return _json(self, 200, {"id": fid})
            return _json(self, 404, {"error": "not found"})

        def do_PATCH(self):                                # noqa: N802
            url = urllib.parse.urlparse(self.path)
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if not self._bearer_ok():
                return _json(self, 401, {"error": "unauthorized"})
            m = re.match(r"^/upload/drive/v3/files/([^/]+)$", url.path)
            if m and m.group(1) in state.files:
                state.files[m.group(1)]["data"] = raw
                return _json(self, 200, {"id": m.group(1)})
            return _json(self, 404, {"error": "not found"})

        def do_DELETE(self):                               # noqa: N802
            url = urllib.parse.urlparse(self.path)
            if not self._bearer_ok():
                return _json(self, 401, {"error": "unauthorized"})
            m = re.match(r"^/drive/v3/files/([^/]+)$", url.path)
            if m:
                state.files.pop(m.group(1), None)
                return _json(self, 200, {})
            return _json(self, 404, {"error": "not found"})

    return H


def provider(fake, tmp, **kw):
    return GoogleDriveProvider(
        client_id="test-client.apps.googleusercontent.com",
        token_path=Path(tmp) / "token.json",
        folder_name="Vibe Coding Assistant",
        auth_url=f"{fake.base}/auth", token_url=f"{fake.base}/token",
        api_base=f"{fake.base}/drive/v3", upload_base=f"{fake.base}/upload/drive/v3",
        open_browser=fake.open_browser, consent_timeout=20, **kw)


def main():
    fake = FakeGoogle()
    tmp = tempfile.mkdtemp(prefix="cva-drive-")
    try:
        print("\n1. Pierwsze logowanie (zgoda w przegladarce + PKCE)")
        p = provider(fake, tmp)
        check("na starcie NIE jestesmy polaczeni", p.is_connected(), False)
        p.auth()
        check("przegladarka otwarta raz", fake.browser_opens, 1)
        check("atrapa naprawde sprawdzila zagadke PKCE", fake.pkce_checked, True)
        check("po zalogowaniu jestesmy polaczeni", p.is_connected(), True)
        tok_file = Path(tmp) / "token.json"
        check("token zapisany na dysku", tok_file.exists(), True)
        check("plik tokenu tylko dla wlasciciela (600)",
              oct(tok_file.stat().st_mode & 0o777), "0o600")

        print("\n2. Kontrola negatywna: czy atrapa w ogole potrafi odrzucic?")
        bad = requests.post(f"{fake.base}/token", data={
            "grant_type": "authorization_code", "code": "code-1",
            "code_verifier": "zle-haslo"}, timeout=5)
        check("zly code_verifier -> odmowa", bad.status_code, 400)

        print("\n3. Kolejne uruchomienie apki (token z dysku)")
        p2 = provider(fake, tmp)
        check("pamieta polaczenie bez sieci", p2.is_connected(), True)
        p2.auth()
        check("NIE otwiera przegladarki drugi raz", fake.browser_opens, 1)

        print("\n4. Wyslanie i pobranie paczki")
        dane = os.urandom(2048)
        p2.upload("brain.vcabundle", dane)
        check("paczka widoczna w chmurze", p2.list(), ["brain.vcabundle"])
        check("pobrane bajty identyczne z wyslanymi", p2.download("brain.vcabundle"), dane)

        print("\n5. Ponowna wysylka tej samej nazwy")
        nowe = os.urandom(1024)
        p2.upload("brain.vcabundle", nowe)
        check("NIE powstal duplikat", p2.list(), ["brain.vcabundle"])
        check("tresc podmieniona", p2.download("brain.vcabundle"), nowe)

        print("\n6. Wygasly token w srodku pracy")
        fake.expire_next_call = True
        check("sam sie odswieza i konczy zadanie", p2.list(), ["brain.vcabundle"])
        check("bez pytania usera o zgode", fake.browser_opens, 1)

        print("\n7. Przypadki brzegowe")
        try:
            p2.download("nie-ma-takiej")
            check("brak paczki -> KeyError", "brak wyjatku", "KeyError")
        except KeyError:
            check("brak paczki -> KeyError", "KeyError", "KeyError")
        p2.delete("brain.vcabundle")
        check("po skasowaniu chmura pusta", p2.list(), [])
        p2.delete("brain.vcabundle")
        check("kasowanie nieistniejacej nie wybucha", True, True)

        print("\n8. Bezpieczenstwo logowania: podmieniona odpowiedz")
        fake.break_state = True
        p3 = provider(fake, tempfile.mkdtemp(prefix="cva-drive2-"))
        try:
            p3.auth()
            check("odpowiedz z obcym 'state' odrzucona", "przeszla", "CloudAuthError")
        except CloudAuthError as exc:
            check("odpowiedz z obcym 'state' odrzucona", "CloudAuthError", "CloudAuthError")
            check("komunikat nie zawiera tokenu", "acc-" in str(exc), False)
        fake.break_state = False

        print("\n9. Odlaczenie konta")
        p2.disconnect()
        check("token skasowany z dysku", tok_file.exists(), False)
        check("apka wie, ze nie jest polaczona", p2.is_connected(), False)

        print(f"\n=== WYNIK: {PASS} OK, {FAIL} FAIL ===")
        return 1 if FAIL else 0
    finally:
        fake.stop()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
