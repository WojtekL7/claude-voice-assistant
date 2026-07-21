#!/usr/bin/env python3
"""Testy wykrywania wyscigu o odswiezenie tokenu ("Please run /login").

Tlo (zmierzone 2026-07-20): wszystkie zakladki dziela JEDEN plik poswiadczen,
a bilet do odnowienia jest jednorazowy. Pierwsza zakladka go zuzywa, pozostale
dostaja "Please run /login", CHOC user nie jest wylogowany. Objaw myli
podwojnie: plik poswiadczen jest caly i swiezy, a proces nie ginie.

Najwazniejsze jest rozpoznanie w OBIE strony: bez niego automatyczny restart
(etap 2) wpadlby w petle przy PRAWDZIWYM wylogowaniu.

Uruchomienie:  python3 tools/test-login-race.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import config                                                    # noqa: E402
from core.platform_utils import (                                # noqa: E402
    claude_credentials_state, credentials_refreshed_since)
from core.transcript_reader import TranscriptReader              # noqa: E402

PASS = FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    ok = got == want
    PASS, FAIL = PASS + ok, FAIL + (not ok)
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"         oczekiwano: {want!r}\n         otrzymano : {got!r}")


def test_verdict_rule():
    print("\n1. Regula werdyktu: wyscig czy prawdziwe wylogowanie?")
    blad_o = 1000.0
    check("poswiadczenia odnowione PO bledzie -> wyscig",
          credentials_refreshed_since(blad_o, {"available": True, "mtime": 1500.0}), True)
    check("nikt nie odnowil -> prawdziwe wylogowanie",
          credentials_refreshed_since(blad_o, {"available": True, "mtime": 1000.0}), False)
    check("plik starszy niz blad -> prawdziwe wylogowanie",
          credentials_refreshed_since(blad_o, {"available": True, "mtime": 900.0}), False)
    check("macOS (Pek kluczy, brak pliku) -> nie da sie orzec, wiec NIE wyscig",
          credentials_refreshed_since(blad_o, {"available": False, "mtime": None}), False)
    check("brak pomiaru z chwili bledu -> NIE wyscig",
          credentials_refreshed_since(None, {"available": True, "mtime": 1500.0}), False)


def test_credentials_state():
    print("\n2. Odczyt stanu poswiadczen (bez czytania sekretow)")
    st = claude_credentials_state()
    check("zwraca komplet pol", sorted(st), ["available", "expires_at", "mtime"])
    if not st["available"]:
        print("  [i]  brak pliku poswiadczen (macOS / nie zalogowano) - reszta pominieta")
        return
    check("zna date zapisu", isinstance(st["mtime"], float), True)
    check("zna moment wygasniecia", isinstance(st["expires_at"], float), True)
    # Kontrola bezpieczenstwa: w wyniku nie moze byc niczego, co wyglada na token.
    dlugie = [v for v in st.values() if isinstance(v, str) and len(v) > 20]
    check("NIE zwraca zadnych dlugich lancuchow (tokenow)", dlugie, [])


def test_detection_source():
    print("\n3. Skad bierzemy sygnal (pieczatka, nie tresc)")
    blad = {"type": "assistant", "isApiErrorMessage": True,
            "message": {"model": "<synthetic>",
                        "content": [{"type": "text", "text": "Login expired · Please run /login"}]}}
    rozmowa = {"type": "assistant",
               "message": {"content": [{"type": "text",
                                        "text": "Naprawiamy blad 'Please run /login' w zakladkach"}]}}
    check("prawdziwy komunikat rozpoznany", TranscriptReader._is_api_error(blad), True)
    check("ROZMOWA o bledzie nie jest bledem", TranscriptReader._is_api_error(rozmowa), False)
    check("wzorzec logowania trafia w tresc komunikatu",
          bool(TranscriptReader._AUTH_ERROR_RE.search("Login expired · Please run /login")), True)
    check("i w wariant 401",
          bool(TranscriptReader._AUTH_ERROR_RE.search("API Error: 401 Invalid authentication")), True)
    check("ale nie w zwykle przeciazenie serwera",
          bool(TranscriptReader._AUTH_ERROR_RE.search("API Error: 529 Overloaded")), False)


def test_settings():
    print("\n4. Ustawienia obserwacji")
    okno = config.LOGIN_VERDICT_INTERVAL_SECS * config.LOGIN_VERDICT_MAX_CHECKS / 60
    check("okno obserwacji dluzsze niz zmierzone 8 min", okno >= 8, True)
    check("log ma twardy limit rozmiaru", config.LOGIN_EVENT_LOG_MAX_BYTES > 0, True)
    print(f"  [i]  okno obserwacji: {okno:.0f} min, log: {config.LOGIN_EVENT_LOG}")


def test_i18n_parity():
    print("\n5. Parytet tlumaczen")
    pl, en = config.UI_TRANSLATIONS["pl-PL"], config.UI_TRANSLATIONS["en-US"]
    for k in ("status_login_checking", "status_login_race", "status_login_real"):
        check(f"{k} w obu jezykach", (k in pl, k in en), (True, True))
        check(f"{k} - zgodne pola do podstawienia",
              "{name}" in pl.get(k, ""), "{name}" in en.get(k, ""))
    check("slowniki nadal maja komplet tych samych kluczy",
          set(pl) ^ set(en), set())


if __name__ == "__main__":
    test_verdict_rule()
    test_credentials_state()
    test_detection_source()
    test_settings()
    test_i18n_parity()
    print(f"\n=== WYNIK: {PASS} OK, {FAIL} FAIL ===")
    sys.exit(1 if FAIL else 0)
