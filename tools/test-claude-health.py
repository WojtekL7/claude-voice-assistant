#!/usr/bin/env python3
"""Bramka: rozpoznawanie USZKODZONEJ instalacji Claude Code (atrapa po npm).

Po co: paczka `@anthropic-ai/claude-code` z npm nie zawiera gotowego programu —
wozi ATRAPĘ (`bin/claude.exe` = zwykły TEKST) i dociąga prawdziwą binarkę
osobnym krokiem (`install.cjs`). Gdy krok się nie wykona, atrapa zostaje, a
Windows pokazuje modalne „Nieobsługiwana aplikacja 16-bitowa" — użytkownik
czyta to jako awarię NASZEJ aplikacji (zgłoszenie 2026-08-07).

Ładunek NIE jest odtworzony z pamięci: `fixtures/claude-npm-placeholder.txt`
to dosłowna treść pliku `package/bin/claude.exe` z paczki npm 2.1.228.

═══ WYNIKI SABOTAŻU — ZMIERZONE 2026-08-12, nie przewidziane (25 asercji) ═══
  1. znacznik atrapy podmieniony na nieistniejący napis      → padły 3
  2. `find_claude_command` bierze pierwszy zamiast sprawnego → padł  1
  3. warunek magii `MZ` odwrócony                            → padło 6
  4. `claude_is_broken` zawsze False                         → padły 2
  5. nakładka `.cmd` nierozwiązywalna (`resolved = None`)    → padło 7
  6. `_win_shim_target` bez zapasowej ścieżki `node_modules` → padł  1
  7. brak warunku „ścieżka bezwzględna ⇒ missing"            → padł  1
  8. okno ignoruje stan „uszkodzony" i radzi INSTALACJĘ      → padło 6
  9. chip stanu bez trzeciego stanu (uszkodzony = „brak")    → padł  1
Każdy wariant wykryty przez co najmniej jeden test.

⚠️ Dwie rzeczy wyszły dopiero z SABOTAŻU, nie z zielonego przebiegu:
  • wariant 6 początkowo NIE wywalał NICZEGO — zapasowa ścieżka `node_modules`
    była martwa dla testów (nakładka rozwiązywała się wcześniej regexem).
    Dopisany przypadek „nieznany format nakładki" domyka tę drugą linię obrony;
    nie kasuj go jako duplikatu.
  • wariant 5 wywalał CAŁĄ bramkę wyjątkiem w połowie — przy filtrowanym
    wyjściu (`grep FAIL`) wyglądało to jak komplet zielonych. Stąd licznik
    WYKONANYCH ASERCJI na końcu: jego spadek jest awarią bramki, nie dowodem
    zdrowia (COMMON: „przy sabotażu licz też, ILE testów się WYKONAŁO").
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "claude-npm-placeholder.txt"

import core.platform_utils as pu  # noqa: E402

OK = 0
FAIL = 0


def check(label, got, want):
    global OK, FAIL
    if got == want:
        OK += 1
        print(f"[OK] {label}")
    else:
        FAIL += 1
        print(f"[FAIL] {label}: dostałem {got!r}, oczekiwano {want!r}")


def force_os(windows: bool):
    """Udawaj Windows/Linux — sprawdzenie magii pliku .exe jest platformowe."""
    pu.is_windows = lambda: windows
    pu.is_macos = lambda: False
    pu.is_linux = lambda: not windows


def restore_os():
    pu.is_windows = _real_is_windows
    pu.is_macos = _real_is_macos
    pu.is_linux = _real_is_linux


_real_is_windows = pu.is_windows
_real_is_macos = pu.is_macos
_real_is_linux = pu.is_linux

PLACEHOLDER = FIXTURE.read_bytes()
# Prawdziwy program Windows zaczyna się od znacznika „MZ" (nagłówek DOS/PE).
REAL_WINDOWS_EXE = b"MZ\x90\x00" + b"\x00" * 512
REAL_ELF = b"\x7fELF" + b"\x00" * 512

# Nakładka npm `claude.cmd` — kieruje do binarki liczonej od własnego katalogu.
NPM_SHIM = (
    "@ECHO off\r\n"
    "SETLOCAL\r\n"
    "CALL :find_dp0\r\n"
    'endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & '
    '"%dp0%\\node_modules\\@anthropic-ai\\claude-code\\bin\\claude.exe" %*\r\n'
)
# Nakładka bez czytelnej ścieżki — nie wolno na jej podstawie nikogo oskarżać.
OPAQUE_SHIM = "@ECHO off\r\nsome_unknown_launcher %*\r\n"


def write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    return path


BROKEN_READINESS = {
    'claude_installed': True,
    'claude_broken': True,
    'claude_broken_path': r"C:\Users\HP\AppData\Roaming\npm\node_modules"
                          r"\@anthropic-ai\claude-code\bin\claude.exe",
    'claude_logged_in': False,
    'dictation': True,
}


def check_dialog():
    """Czy kreator pokazuje instrukcję NAPRAWY, a nie instrukcję INSTALACJI.

    Sam brak ucięć (scan-dialog-clipping) tego nie dowodzi — okno mogłoby się
    ładnie rysować, radząc użytkownikowi z zepsutym Claude Code, żeby go
    „zainstalował", czyli powtórzył dokładnie tę czynność, która zawiodła."""
    global OK, FAIL
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PyQt5.QtWidgets import QApplication, QLabel, QLineEdit
    except Exception as exc:
        print(f"[POMINIĘTE] okno kreatora — brak PyQt5 ({exc})")
        return
    app = QApplication.instance() or QApplication([])
    pu.os_key = lambda: "windows"  # wariant, który realnie widzi użytkownik
    import gui.dialogs as gd

    dlg = gd.ClaudeSetupDialog(None, readiness=BROKEN_READINESS)
    texts = " ".join(l.text() for l in dlg.findChildren(QLabel))
    commands = [e.text() for e in dlg.findChildren(QLineEdit)]

    check('okno: chip stanu mówi USZKODZONY, a nie „do zrobienia”',
          any(l.text() == tr_broken_chip() for l in dlg.findChildren(QLabel)), True)
    check("okno: podaje polecenie usuwające zepsutą wersję z npm",
          gd.ClaudeSetupDialog.NPM_UNINSTALL_COMMAND in commands, True)
    check("okno: podaje instalator natywny dla Windows",
          gd.ClaudeSetupDialog.NATIVE_INSTALL_COMMAND_WINDOWS in commands, True)
    # Sedno: NIE wolno kazać powtarzać instalacji, która właśnie zawiodła.
    check("okno: NIE radzi ponownej instalacji przez npm",
          any(gd.ClaudeSetupDialog.NPM_COMMAND in c for c in commands), False)
    check("okno: tłumaczy objaw, który widzi użytkownik Windows",
          "16-bitowej" in texts or "16-bit" in texts, True)
    check("okno: podaje sposób sprawdzenia po naprawie",
          "claude --version" in texts, True)
    check("okno: wskazuje uszkodzony plik z nazwy",
          "claude.exe" in texts, True)
    dlg.deleteLater()
    restore_os()


def tr_broken_chip():
    from config import t
    return t('dlg_setup_broken_chip')


def main():
    print("=" * 70)
    print("BRAMKA: uszkodzona instalacja Claude Code (atrapa npm)")
    print("=" * 70)

    # --- Ładunek jest tym, za co się podaje ---
    check("atrapa z npm to TEKST, nie program (brak znacznika MZ)",
          PLACEHOLDER[:2] != b"MZ", True)
    check("atrapa niesie znacznik rozpoznawczy",
          pu._CLAUDE_PLACEHOLDER_MARK in PLACEHOLDER, True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # ============ WINDOWS ============
        force_os(True)

        broken_exe = write(tmp / "npm" / "node_modules" / "@anthropic-ai"
                           / "claude-code" / "bin" / "claude.exe", PLACEHOLDER)
        shim = write(tmp / "npm" / "claude.cmd", NPM_SHIM)

        h = pu.claude_binary_health(str(shim))
        check("Windows: nakładka .cmd → atrapa rozpoznana jako 'broken'",
              h['status'], 'broken')
        check("Windows: powód nazwany wprost", h['reason'], 'placeholder')
        # Bez `or ''` sabotaż zwracający None wywalałby CAŁĄ bramkę w tym miejscu,
        # a filtrowane wyjście wyglądałoby jak komplet zielonych.
        check("Windows: wskazujemy PLIK, który jest zepsuty (nie nakładkę)",
              Path(h['target'] or 'brak').name, 'claude.exe')
        check("Windows: skrót claude_is_broken zgadza się z werdyktem",
              pu.claude_is_broken(str(shim)), True)

        # Ten sam plik podany WPROST (bez nakładki).
        check("Windows: atrapa podana wprost też jest 'broken'",
              pu.claude_binary_health(str(broken_exe))['status'], 'broken')

        # Binarka Linuksa nazwana .exe — drugi wariant tej samej usterki.
        elf_exe = write(tmp / "obcy" / "claude.exe", REAL_ELF)
        h = pu.claude_binary_health(str(elf_exe))
        check("Windows: binarka innego systemu też jest 'broken'", h['status'], 'broken')
        check("Windows: powód odróżnia ją od atrapy", h['reason'], 'not_windows_program')

        # --- KONTROLA ODWROTNA: sprawny program NIE MOŻE być oskarżony ---
        good_exe = write(tmp / "dobry" / "claude.exe", REAL_WINDOWS_EXE)
        check("Windows: sprawny program = 'ok'",
              pu.claude_binary_health(str(good_exe))['status'], 'ok')
        check("Windows: sprawny program NIE jest blokowany",
              pu.claude_is_broken(str(good_exe)), False)

        good_shim_dir = tmp / "dobry-npm"
        write(good_shim_dir / "node_modules" / "@anthropic-ai" / "claude-code"
              / "bin" / "claude.exe", REAL_WINDOWS_EXE)
        good_shim = write(good_shim_dir / "claude.cmd", NPM_SHIM)
        check("Windows: sprawna instalacja npm przez nakładkę = 'ok'",
              pu.claude_binary_health(str(good_shim))['status'], 'ok')

        # Skrypt Node to POPRAWNA droga uruchomienia — tekst w środku jest OK.
        cjs = write(tmp / "node" / "cli-wrapper.cjs", "#!/usr/bin/env node\n")
        check("Windows: skrypt Node nie jest mylony z atrapą",
              pu.claude_binary_health(str(cjs))['status'], 'ok')

        # --- FAIL-OPEN: przy niepewności nie oskarżamy ---
        opaque = write(tmp / "dziwny" / "claude.cmd", OPAQUE_SHIM)
        h = pu.claude_binary_health(str(opaque))
        check("Windows: nierozpoznana nakładka → 'unknown', NIE 'broken'",
              h['status'], 'unknown')
        check("Windows: nierozpoznana nakładka nie blokuje pracy",
              pu.claude_is_broken(str(opaque)), False)

        # Nakładka bez czytelnej ścieżki, ale obok LEŻY typowy układ npm —
        # wtedy wolno sięgnąć po ścieżkę zapasową. To osobna linia obrony na
        # wypadek, gdyby npm zmieniło format nakładki (bez tego przypadku
        # sabotaż zapasowej ścieżki nie wywalał ŻADNEGO testu — zmierzone).
        fb_dir = tmp / "npm-inny-format"
        write(fb_dir / "node_modules" / "@anthropic-ai" / "claude-code"
              / "bin" / "claude.exe", PLACEHOLDER)
        fb_shim = write(fb_dir / "claude.cmd", OPAQUE_SHIM)
        check("Windows: nieznany format nakładki → ratuje ścieżka zapasowa npm",
              pu.claude_binary_health(str(fb_shim))['status'], 'broken')

        check("brak pliku → 'missing' (co innego niż 'broken')",
              pu.claude_binary_health(str(tmp / "nie-ma" / "claude.exe"))['status'],
              'missing')

        # --- Wybór komendy: sprawna wygrywa z zepsutą ---
        # Odtwarzamy układ z maszyny użytkownika: zepsuty npm na PATH (pierwszy)
        # oraz naprawiona instalacja natywna w ~/.local/bin.
        home = tmp / "home"
        native = write(home / ".local" / "bin" / "claude.exe", REAL_WINDOWS_EXE)
        npm_shim = write(home / "AppData" / "Roaming" / "npm" / "claude.cmd", NPM_SHIM)
        write(home / "AppData" / "Roaming" / "npm" / "node_modules" / "@anthropic-ai"
              / "claude-code" / "bin" / "claude.exe", PLACEHOLDER)

        real_home, real_which = pu.Path.home, pu.shutil.which
        pu.Path.home = staticmethod(lambda: home)
        pu.shutil.which = lambda name, path=None: str(npm_shim) if name == "claude" else None
        try:
            picked = pu.find_claude_command()
            check("wybór komendy: pomija zepsutą z npm, bierze sprawną natywną",
                  picked, str(native))

            # Gdy sprawnej NIE MA — oddajemy zepsutą, żeby apka mogła powiedzieć
            # „uszkodzony", a nie mylące „nie znaleziono".
            native.unlink()
            picked = pu.find_claude_command()
            check("wybór komendy: same zepsute → oddaj zepsutą (nie 'claude')",
                  picked, str(npm_shim))
            check("…i ta zepsuta jest zgłaszana jako uszkodzona",
                  pu.claude_is_broken(picked), True)
        finally:
            pu.Path.home = real_home
            pu.shutil.which = real_which

        # ============ LINUX / macOS ============
        force_os(False)
        lin_placeholder = write(tmp / "lin" / "claude", PLACEHOLDER)
        check("Linux: ta sama atrapa też jest rozpoznana",
              pu.claude_binary_health(str(lin_placeholder))['status'], 'broken')
        lin_real = write(tmp / "lin-ok" / "claude", REAL_ELF)
        check("Linux: prawdziwy program = 'ok'",
              pu.claude_binary_health(str(lin_real))['status'], 'ok')
        # Na Linuksie brak znacznika MZ jest NORMĄ — nie wolno tego karać.
        lin_script = write(tmp / "lin-sh" / "claude", "#!/bin/sh\nexec real\n")
        check("Linux: skrypt powłoki nie jest brany za uszkodzony",
              pu.claude_binary_health(str(lin_script))['status'], 'ok')
        restore_os()

    # --- Parytet tłumaczeń: nowe napisy muszą być w OBU językach ---
    import config
    pl = set(config.UI_TRANSLATIONS['pl-PL'])
    en = set(config.UI_TRANSLATIONS['en-US'])
    new_keys = [k for k in pl if 'broken' in k]
    check("nowe napisy o uszkodzonej instalacji istnieją", len(new_keys) >= 10, True)
    check("parytet PL/EN dla nowych napisów", sorted(k for k in pl if 'broken' in k),
          sorted(k for k in en if 'broken' in k))

    check_dialog()

    print("=" * 70)
    print(f"WYKONANYCH ASERCJI: {OK + FAIL}   OK: {OK}   FAIL: {FAIL}")
    print("=" * 70)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
