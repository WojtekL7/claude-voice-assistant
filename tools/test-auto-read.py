#!/usr/bin/env python3
"""Testy auto-czytania: czytnik dziennika + nadganianie lektora.

Tło (2026-07-21). User zgłosił „program czyta przedostatnią wypowiedź".
Zmierzone w dzienniku sesji: wypowiedzi zapisywały się na czas i po kolei,
a wybór wypowiedzi był prawidłowy — spóźniało się samo CZYTANIE. Kolejka
lektora jest FIFO i nic nie pomija, więc przy 4 wypowiedziach (~3200 znaków
≈ 3,5 min mowy) w ciągu 2 minut lektor mówił to, co agent napisał 2 minuty
wcześniej. Stąd nadganianie: powyżej ~minuty zaległości skacz do najnowszej.

Sprawdzamy OBA kierunki — także to, że poniżej progu NIC nie jest pomijane.

Uruchomienie:  python3 tools/test-auto-read.py
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import config                                              # noqa: E402
from core.transcript_reader import TranscriptReader, _encode_project_dir  # noqa: E402

PASS = FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    ok = got == want
    PASS, FAIL = PASS + ok, FAIL + (not ok)
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"         oczekiwano: {want!r}\n         otrzymano : {got!r}")


def entry(text, api_error=False):
    """Wpis dziennika w kształcie, jaki realnie zapisuje Claude Code."""
    obj = {
        "type": "assistant",
        "isSidechain": False,
        "timestamp": "2026-07-21T10:00:00.000Z",
        "message": {
            "model": "<synthetic>" if api_error else "claude-opus-4-8",
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
        },
    }
    if api_error:
        obj["isApiErrorMessage"] = True
    return json.dumps(obj)


def test_reader():
    tmp = Path(tempfile.mkdtemp(prefix="cva-read-"))
    try:
        cwd = "/home/tester/Projekty/demo"
        reader = TranscriptReader(cwd)
        reader._projects_base = tmp / "projects"
        pdir = tmp / "projects" / _encode_project_dir(cwd)
        pdir.mkdir(parents=True)
        reader.set_working_directory(cwd)
        uuid = "11111111-2222-3333-4444-555555555555"
        f = pdir / f"{uuid}.jsonl"
        f.write_bytes(b"")
        reader.pin_session(uuid)

        def append(raw: bytes):
            with open(f, "ab") as fh:
                fh.write(raw)

        print("\n1. Zapis W TOKU (wpis bez znaku konca linii)")
        append(entry("Pierwsza odpowiedz").encode())
        check("niekompletna linia NIE jest czytana", reader.poll(), [])

        print("\n2. Zapis domkniety znakiem konca linii")
        append(b"\n")
        check("czytana dokladnie raz", reader.poll(), ["Pierwsza odpowiedz"])
        check("i nie powtarza sie", reader.poll(), [])

        print("\n3. Fragment urwany w polowie")
        half = entry("Druga odpowiedz").encode()
        cut = len(half) // 2
        append(half[:cut])
        check("urwany fragment NIE czytany", reader.poll(), [])
        append(half[cut:] + b"\n")
        check("po domknieciu czytany raz", reader.poll(), ["Druga odpowiedz"])

        print("\n4. Komunikat bledu Claude Code (wygasle logowanie)")
        append(entry("Login expired · Please run /login", api_error=True).encode() + b"\n")
        check("NIE trafia do lektora", reader.poll(), [])
        errs = reader.take_api_errors()
        check("trafia do kolejki GUI", len(errs), 1)
        check("rozpoznany jako sprawa logowania", errs[0]["is_auth"] if errs else None, True)
        check("kolejka oproznia sie po odbiorze", reader.take_api_errors(), [])

        print("\n5. Rozmowa O bledzie (kontrola negatywna)")
        talk = "Naprawiamy blad 'Please run /login' w zakladkach"
        append(entry(talk).encode() + b"\n")
        check("czytana normalnie jako wypowiedz", reader.poll(), [talk])
        check("i NIE uznana za blad", reader.take_api_errors(), [])

        print("\n6. Regresja: auto-skrocenie dziennika (auto-compact)")
        f.write_bytes(entry("Po kompaktowaniu").encode() + b"\n")   # plik krotszy niz offset
        check("nie recytuje pliku od poczatku", reader.poll(), [])
        append(entry("Nowa po kompaktowaniu").encode() + b"\n")
        check("czyta tylko to, co przyszlo pozniej",
              reader.poll(), ["Nowa po kompaktowaniu"])

        print("\n7. Regresja: kilka wypowiedzi naraz, kolejnosc zachowana")
        f.write_bytes((entry("A") + "\n" + entry("B") + "\n" + entry("C") + "\n").encode())
        reader.pin_session(uuid)          # reset offsetu jak przy restarcie zakladki
        check("wszystkie po kolei", reader.poll(), ["A", "B", "C"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_catchup():
    """Sama REGULA nadganiania (bez GUI i bez dzwieku)."""
    prog = config.TTS_CATCHUP_CHARS
    print(f"\n8. Nadganianie lektora (prog: {prog} znakow ≈ minuta mowy)")
    check("pusta kolejka -> czytaj wszystko", config.tts_should_catch_up(0), False)
    check("krotka zaleglosc -> czytaj wszystko", config.tts_should_catch_up(516), False)
    check("dokladnie prog -> jeszcze bez skoku", config.tts_should_catch_up(prog), False)
    check("duza zaleglosc -> przeskocz do najnowszej",
          config.tts_should_catch_up(prog + 1), True)
    check("zmierzony przypadek usera (2682 znaki w kolejce)",
          config.tts_should_catch_up(2682), True)


def test_i18n_parity():
    print("\n9. Parytet tlumaczen (nowy komunikat w OBU jezykach)")
    pl = set(config.UI_TRANSLATIONS["pl-PL"])
    en = set(config.UI_TRANSLATIONS["en-US"])
    check("klucz istnieje w PL", "status_tts_catchup" in pl, True)
    check("klucz istnieje w EN", "status_tts_catchup" in en, True)
    check("slowniki nadal maja komplet tych samych kluczy", pl - en | en - pl, set())


if __name__ == "__main__":
    test_reader()
    test_catchup()
    test_i18n_parity()
    print(f"\n=== WYNIK: {PASS} OK, {FAIL} FAIL ===")
    sys.exit(1 if FAIL else 0)
