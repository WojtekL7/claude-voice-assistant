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
  apply_update_async(path) → ZAINSTALUJ pobraną paczkę:
                   • macOS + .zip + uruchomiona apka .app → samo-podmiana pakietu
                     i restart (relaunch_ready) — bez ręcznego przeciągania,
                   • Windows + .exe + apka spakowana → uruchom instalator Inno PO CICHU
                     (/VERYSILENT, per-user, bez UAC); Restart Manager podmienia pliki,
                     sekcja [Run] wznawia program (relaunch_ready) — też bez klikania,
                   • pozostałe (np. Linux / uruchomienie „z kodu") → otwórz paczkę
                     instalatorem (installer_opened).

Decyzje: sha256 obowiązkowe, gdy appcast je podaje. Podpis Ed25519 to gniazdo
gotowe-ale-wyłączone (działa tylko z kluczem publicznym + biblioteką
`cryptography`). Samo-podmiana (Etap 2) jest dziś realna na macOS i Windows; Linux
zostaje na „otwórz instalator", dopóki nie powstanie paczka podmienialna w miejscu
(AppImage) — patrz TODO w build/packaging.
"""
import os
import re
import hashlib
import tempfile
import threading
import subprocess
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.platform_utils import is_macos, is_windows, is_frozen, macos_app_bundle


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
    # ---- instalacja pobranej paczki (Etap 2) ----
    relaunch_ready = pyqtSignal()           # macOS: podmiana przygotowana, aplikacja ma się zamknąć (pomocnik ją wznowi)
    installer_opened = pyqtSignal(str)      # inne systemy: otwarto pobraną paczkę instalatorem
    apply_failed = pyqtSignal(str)          # nie udało się zainstalować (komunikat)

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

    # ==================== Instalacja pobranej paczki (Etap 2) ====================

    def apply_update_async(self, path):
        """Zainstaluj pobraną paczkę. macOS + paczka .zip + uruchomiona apka .app
        → prawdziwa samo-podmiana (aplikacja wymieni się i wystartuje ponownie).
        Pozostałe przypadki → otwórz paczkę instalatorem systemu (jak dotąd).
        Cała robota w wątku tła (rozpakowanie .zip bywa kilkusekundowe)."""
        threading.Thread(target=self._apply_worker, args=(str(path),),
                         daemon=True).start()

    def can_self_replace(self, path) -> bool:
        """Czy dla tej paczki zrobimy prawdziwą samo-podmianę:
          • macOS: paczka .zip + uruchomiona apka .app,
          • Windows: pobrany instalator .exe + aplikacja spakowana (frozen) —
            instalator (Inno, per-user) podmieni pliki po cichu i wznowi program.
        Inaczej (np. uruchomienie „z kodu") → otwórz instalator ręcznie."""
        p = str(path).lower()
        if is_macos() and p.endswith(".zip") and macos_app_bundle() is not None:
            return True
        if is_windows() and p.endswith(".exe") and is_frozen():
            return True
        return False

    def _apply_worker(self, path):
        if self.can_self_replace(path):
            try:
                if is_macos():
                    self._macos_self_replace(path, macos_app_bundle())
                elif is_windows():
                    self._windows_self_replace(path)
            except Exception as e:
                self.apply_failed.emit(f"Samo-aktualizacja nie powiodła się: {e}")
                return
            # macOS: pomocnik wznowi apkę; Windows: instalator (sekcja [Run]) ją wznowi.
            self.relaunch_ready.emit()
            return
        # Nie-macOS / nie-.zip / uruchomione „z kodu" → otwórz paczkę ręcznie.
        if self.open_installer(path):
            self.installer_opened.emit(str(path))
        else:
            self.apply_failed.emit(
                f"Nie udało się otworzyć pobranej paczki. Plik:\n{path}")

    def _macos_self_replace(self, zip_path, target_app: Path):
        """Rozpakuj nową aplikację z .zip i uruchom pomocnika, który po
        zamknięciu tej aplikacji podmieni pakiet .app i odpali nową wersję.

        Używamy macowego `ditto` (nie zipfile Pythona!) — poprawnie odtwarza
        dowiązania symboliczne i bity wykonywalności wewnątrz `.app` (frameworki
        Qt mają symlinki, których `zipfile` by nie odtworzył → uszkodzona apka)."""
        staging = Path(tempfile.mkdtemp(prefix="cva-update-"))
        # ditto -x -k: rozpakuj archiwum PKZip zachowując symlinki/uprawnienia.
        subprocess.run(["ditto", "-x", "-k", str(zip_path), str(staging)],
                       check=True, capture_output=True)
        apps = sorted(staging.glob("*.app")) or sorted(staging.rglob("*.app"))
        if not apps:
            raise RuntimeError("w pobranej paczce nie znaleziono aplikacji .app")
        new_app = apps[0]
        # Zdejmij kwarantannę z nowej apki (niepodpisana — by start był gładki).
        subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(new_app)],
                       check=False, capture_output=True)

        pid = os.getpid()
        # Pomocnik: czeka aż TA aplikacja (pid) się zamknie, podmienia pakiet,
        # uruchamia nową wersję. `mv` może paść między wolumenami → fallback cp.
        script = staging / "cva-swap.sh"
        script.write_text(
            "#!/bin/bash\n"
            "# Auto-podmiana Claude Voice Assistant — generowane przez updater.\n"
            f"PID={pid}\n"
            f'NEW_APP="{new_app}"\n'
            f'TARGET="{target_app}"\n'
            'for _ in $(seq 1 150); do\n'
            '  kill -0 "$PID" 2>/dev/null || break\n'
            '  sleep 0.2\n'
            'done\n'
            'sleep 0.5\n'
            'rm -rf "$TARGET"\n'
            'mv "$NEW_APP" "$TARGET" 2>/dev/null || cp -R "$NEW_APP" "$TARGET"\n'
            'xattr -dr com.apple.quarantine "$TARGET" 2>/dev/null\n'
            'open "$TARGET"\n'
        )
        script.chmod(0o755)
        subprocess.Popen(
            ["/bin/bash", str(script)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)

    def _windows_self_replace(self, installer_path):
        """Uruchom pobrany instalator Inno PO CICHU i odłączony od tej aplikacji.

        Instalator jest per-user ({localappdata}) → bez UAC. Z `CloseApplications=yes`
        w skrypcie .iss Inno (Restart Manager) zamknie działającą aplikację, podmieni
        pliki i — dzięki sekcji [Run] bez `skipifsilent` — wznowi nową wersję. My zaraz
        po starcie instalatora emitujemy `relaunch_ready` (aplikacja sama się zamyka),
        więc pliki nie są zablokowane.

        DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP: instalator przeżyje zamknięcie
        aplikacji (inaczej zginąłby razem z procesem-rodzicem)."""
        DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        subprocess.Popen(
            [str(installer_path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            close_fds=True)

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
