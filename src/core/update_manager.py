"""
Claude Voice Assistant - Auto-aktualizacja (Etap M3)

Klient aktualizacji w aplikacji. Cały ruch sieciowy idzie w wątku tła i wraca
do GUI przez sygnały Qt (kolejkowane = bezpieczne wątkowo), więc nigdy nie
zamraża interfejsu ani nie wywala aplikacji przy braku internetu.

Przepływ:
  check_async()  → pobierz appcast.json, wybierz wpis dla swojej platformy,
                   porównaj wersje → update_available / no_update / check_failed
  download_async(info) → pobierz paczkę z postępem, zweryfikuj sha256 (i opcjonalnie
                   podpis Ed25519), zdejmij kwarantannę (macOS) → download_finished
  open_installer(path) → otwórz pobraną paczkę instalatorem systemu

Decyzje (M3): instalacja = „otwórz instalator" (bez automatycznej podmiany);
podpis Ed25519 to gniazdo gotowe-ale-wyłączone (działa tylko gdy podano klucz
publiczny i dostępna jest biblioteka `cryptography`). sha256 jest obowiązkowe,
gdy appcast je podaje.
"""
import os
import re
import hashlib
import threading
import subprocess
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.platform_utils import is_macos, is_windows


class UpdateInfo:
    """Opis dostępnej aktualizacji (wpis z appcast dla bieżącej platformy)."""

    def __init__(self, version, url, size=0, sha256="", signature="",
                 notes_url="", mandatory=False, platform_id=""):
        self.version = version
        self.url = url
        self.size = size or 0
        self.sha256 = sha256 or ""
        self.signature = signature or ""
        self.notes_url = notes_url or ""
        self.mandatory = bool(mandatory)
        self.platform_id = platform_id or ""

    def __repr__(self):
        return f"<UpdateInfo {self.version} {self.platform_id} {self.url}>"


class UpdateManager(QObject):
    """Sprawdzanie, pobieranie i weryfikacja aktualizacji."""

    update_available = pyqtSignal(object)   # UpdateInfo — jest nowsza wersja
    no_update = pyqtSignal()                # brak nowszej (lub brak wpisu dla platformy)
    check_failed = pyqtSignal(str)          # błąd sieci/parsowania (komunikat)
    download_progress = pyqtSignal(int, int)  # pobrane_bajty, total_bajtów (0 = nieznane)
    download_finished = pyqtSignal(str)     # ścieżka pobranej, zweryfikowanej paczki
    download_failed = pyqtSignal(str)       # błąd pobierania/weryfikacji (komunikat)

    def __init__(self, appcast_url, current_version, platform_id,
                 public_key="", download_dir=None, parent=None):
        super().__init__(parent)
        self.appcast_url = appcast_url
        self.current_version = current_version
        self.platform_id = platform_id
        self.public_key = public_key or ""
        self.download_dir = Path(download_dir) if download_dir else (
            Path.home() / ".claude-voice-assistant" / "updates")

    # ==================== Porównanie wersji (czysta logika) ====================

    @staticmethod
    def _parse_version(v):
        """'1.2.3-beta' → (1, 2, 3). Przerywa na pierwszym nie-liczbowym członie."""
        nums = []
        for part in re.split(r'[.\-+]', str(v).strip()):
            m = re.match(r'^(\d+)', part)
            if not m:
                break
            nums.append(int(m.group(1)))
        return tuple(nums) or (0,)

    @classmethod
    def is_newer(cls, remote, local):
        """Czy `remote` to wyższa wersja niż `local` (semver liczbowy)."""
        a = cls._parse_version(remote)
        b = cls._parse_version(local)
        n = max(len(a), len(b))
        a = a + (0,) * (n - len(a))
        b = b + (0,) * (n - len(b))
        return a > b

    # ==================== Wybór wpisu z appcast (czysta logika) ====================

    def select_entry(self, appcast: dict):
        """Z surowego appcast wyciągnij UpdateInfo dla bieżącej platformy.

        Zwraca None, jeśli brak sekcji 'latest', wersji, wpisu dla platformy lub URL.
        """
        latest = (appcast or {}).get("latest") or {}
        version = latest.get("version")
        platforms = latest.get("platforms") or {}
        entry = platforms.get(self.platform_id)
        if not version or not entry or not entry.get("url"):
            return None
        return UpdateInfo(
            version=version,
            url=entry.get("url"),
            size=entry.get("size", 0),
            sha256=entry.get("sha256", ""),
            signature=entry.get("signature", ""),
            notes_url=latest.get("notes_url", ""),
            mandatory=latest.get("mandatory", False),
            platform_id=self.platform_id,
        )

    # ==================== Sprawdzanie (wątek tła) ====================

    def check_async(self):
        threading.Thread(target=self._check_worker, daemon=True).start()

    def _check_worker(self):
        try:
            appcast = self._fetch_appcast()
            info = self.select_entry(appcast)
        except Exception as e:
            self.check_failed.emit(str(e))
            return
        if info is None:
            self.no_update.emit()
            return
        if self.is_newer(info.version, self.current_version):
            self.update_available.emit(info)
        else:
            self.no_update.emit()

    def _fetch_appcast(self) -> dict:
        import requests
        resp = requests.get(self.appcast_url, timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ==================== Pobieranie + weryfikacja (wątek tła) ====================

    def download_async(self, info: UpdateInfo):
        threading.Thread(target=self._download_worker, args=(info,), daemon=True).start()

    def _download_worker(self, info: UpdateInfo):
        import requests
        try:
            self.download_dir.mkdir(parents=True, exist_ok=True)
            filename = info.url.split("/")[-1] or f"update-{info.version}"
            dest = self.download_dir / filename
            sha = hashlib.sha256()
            downloaded = 0
            with requests.get(info.url, stream=True, timeout=60) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length") or info.size or 0)
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(65536):
                        if not chunk:
                            continue
                        f.write(chunk)
                        sha.update(chunk)
                        downloaded += len(chunk)
                        self.download_progress.emit(downloaded, total)
        except Exception as e:
            self.download_failed.emit(f"Pobieranie nie powiodło się: {e}")
            return

        # sha256 — obowiązkowe, gdy appcast je podaje.
        if info.sha256 and sha.hexdigest().lower() != info.sha256.lower():
            self._safe_unlink(dest)
            self.download_failed.emit(
                "Suma kontrolna pliku (sha256) się nie zgadza — paczka odrzucona.")
            return

        # Podpis Ed25519 — tylko gdy włączony (klucz + podpis obecne).
        if self.public_key and info.signature:
            if not self._verify_signature(dest, info.signature, self.public_key):
                self._safe_unlink(dest)
                self.download_failed.emit(
                    "Podpis aktualizacji jest nieprawidłowy — paczka odrzucona.")
                return

        # macOS: zdejmij kwarantannę, by instalacja była „gładka".
        self._remove_quarantine(dest)
        self.download_finished.emit(str(dest))

    # ==================== Weryfikacja / system ====================

    @staticmethod
    def verify_sha256(path, expected: str) -> bool:
        """Pomocniczo/testowo: policz sha256 pliku i porównaj."""
        if not expected:
            return True
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest().lower() == expected.lower()

    @staticmethod
    def _verify_signature(path, signature_b64, public_key_b64) -> bool:
        """Ed25519 nad bajtami pliku. Brak biblioteki/klucza → False (odrzuć)."""
        try:
            import base64
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
            pub.verify(base64.b64decode(signature_b64), Path(path).read_bytes())
            return True
        except Exception:
            return False

    @staticmethod
    def _remove_quarantine(path):
        if not is_macos():
            return
        try:
            subprocess.run(
                ["xattr", "-dr", "com.apple.quarantine", str(path)],
                check=False, capture_output=True)
        except Exception:
            pass

    @staticmethod
    def _safe_unlink(path):
        try:
            Path(path).unlink()
        except Exception:
            pass

    @staticmethod
    def open_installer(path) -> bool:
        """Otwórz pobraną paczkę instalatorem systemu (bez powłoki, lista argów)."""
        try:
            if is_macos():
                subprocess.run(["open", str(path)], check=False)
            elif is_windows():
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
            return True
        except Exception:
            return False
