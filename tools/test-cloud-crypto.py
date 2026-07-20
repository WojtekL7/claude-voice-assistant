#!/usr/bin/env python3
"""Testy szyfrowania paczki agentów + INWARIANTU sekretów.

Uruchom: ./venv/bin/python tools/test-cloud-crypto.py

Nacisk położony na KONTROLE NEGATYWNE — samo „działa szczęśliwa ścieżka" niczego tu
nie dowodzi. Musimy pokazać, że złe hasło NIE otwiera paczki, że ruszony plik jest
ODRZUCANY, i że klucze API nie mają jak wyjść niezaszyfrowane.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.cloud import bundle_crypto as bc          # noqa: E402
from core.cloud import agent_bundle as ab           # noqa: E402

FAILED = []


def check(label, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {label}")
    if not cond:
        FAILED.append(label)


def expect_raises(label, fn, needle=""):
    try:
        fn()
    except Exception as exc:
        ok = needle.lower() in str(exc).lower() if needle else True
        print(f"[{'PASS' if ok else 'FAIL'}] {label} (odmowa: {str(exc)[:70]})")
        if not ok:
            FAILED.append(label)
        return
    print(f"[FAIL] {label} — NIE odmówiło, a powinno!")
    FAILED.append(label)


SECRET = "gsk_TAJNYKLUCZTESTOWY1234567890abcdefXYZ"
PASS = "poprawne-haslo-testowe"


def make_config(root: Path) -> Path:
    cfg = root / "cfg"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "config.json").write_text(json.dumps({
        "language": "pl-PL", "auto_read": True,
        "groq_api_key": SECRET,
        "claude_command": "/home/ktos/.local/bin/claude",
    }), encoding="utf-8")
    (cfg / "agents.json").write_text(json.dumps([
        {"id": "a1", "name": "Test", "working_directory": str(root / "proj"),
         "memory_files": [], "icon": {"emoji": "🤖"}, "tab_color": "#ff0000",
         "tts_voice": "pl-PL-MarekNeural"},
    ]), encoding="utf-8")
    (root / "proj").mkdir(exist_ok=True)
    return cfg


print("=== 1. Szyfrowanie: podstawy ===")
data = b"tresc paczki" * 1000
sealed = bc.seal(data, PASS)
check("zaszyfrowana paczka jest rozpoznawalna", bc.is_sealed(sealed))
check("jawne bajty NIE wygladaja na paczke", not bc.is_sealed(data))
check("odszyfrowanie poprawnym haslem zwraca oryginal", bc.unseal(sealed, PASS) == data)
check("tresc NIE jest widoczna w szyfrogramie", b"tresc paczki" not in sealed)

print("\n=== 2. Kontrole negatywne (tu sie wszystko rozstrzyga) ===")
expect_raises("zle haslo NIE otwiera paczki", lambda: bc.unseal(sealed, "zle-haslo"), "hasło")
expect_raises("puste haslo odrzucone", lambda: bc.unseal(sealed, ""), "hasło")
tampered = bytearray(sealed)
tampered[-1] ^= 0x01
expect_raises("PODMIENIONY szyfrogram odrzucony", lambda: bc.unseal(bytes(tampered), PASS))
tampered2 = bytearray(sealed)
tampered2[len(bc.MAGIC) + 20] ^= 0x01          # ruszamy NAGŁÓWEK
expect_raises("ruszony NAGLOWEK odrzucony", lambda: bc.unseal(bytes(tampered2), PASS))
expect_raises("obce bajty odrzucone", lambda: bc.unseal(b"cokolwiek innego", PASS))
check("dwa szyfrowania tej samej tresci daja ROZNE bajty (losowa sol/nonce)",
      bc.seal(data, PASS) != bc.seal(data, PASS))

print("\n=== 3. Haslo generowane dla usera ===")
p1, p2 = bc.generate_passphrase(), bc.generate_passphrase()
check("generowane hasla sa rozne", p1 != p2)
check("format czytelny do przepisania z kartki", len(p1.split("-")) == 6)
check("bez znakow mylacych (0/O/1/I/L)", not set("01OIL") & set(p1.replace("-", "")))

print("\n=== 4. INWARIANT: sekrety tylko w paczce zaszyfrowanej ===")
tmp = Path(tempfile.mkdtemp())
try:
    cfg = make_config(tmp)

    plain_bundle = ab.export_bundle(cfg)
    check("paczka JAWNA nie zawiera klucza API", SECRET.encode() not in plain_bundle)

    expect_raises(
        "export_sealed BEZ hasla ODMAWIA (nie wysyla jawnie)",
        lambda: ab.export_sealed("", cfg), "odmawiam")

    sealed_bundle = ab.export_sealed(PASS, cfg)
    check("zapieczetowana paczka jest zaszyfrowana", bc.is_sealed(sealed_bundle))
    check("klucz API NIEwidoczny w bajtach lecacych do chmury",
          SECRET.encode() not in sealed_bundle)

    import io, zipfile
    opened = bc.unseal(sealed_bundle, PASS)
    # UWAGA: paczka to zip (DEFLATE) - klucza NIE ma doslownie w surowych bajtach,
    # bo jest skompresowany. Szukamy w ROZPAKOWANEJ tresci, inaczej test klamie.
    with zipfile.ZipFile(io.BytesIO(opened)) as zf:
        man = json.loads(zf.read("manifest.json").decode())
    check("po odszyfrowaniu klucz API JEST w srodku (czyli naprawde go wyslalismy)",
          man.get("config", {}).get("groq_api_key") == SECRET)

    # Wzmocniony dowod nieczytelnosci: samo 'nie widac stringa' to za slaby test
    # (kompresja tez by go ukryla). Zaszyfrowanej paczki nie da sie NAWET otworzyc
    # jako zip - czyli chmura nie wyciagnie z niej niczego, nie tylko kluczy.
    try:
        zipfile.ZipFile(io.BytesIO(sealed_bundle)).namelist()
        check("zaszyfrowanej paczki NIE da sie otworzyc jako zip", False)
    except zipfile.BadZipFile:
        check("zaszyfrowanej paczki NIE da sie otworzyc jako zip", True)
    check("lokalna sciezka 'claude_command' NIE trafila do paczki",
          "claude_command" not in man.get("config", {}))
    check("manifest jawnie oznacza, ze niesie sekrety",
          man.get("contains_secrets") is True)

    print("\n=== 5. Odtworzenie na 'nowym komputerze' ===")
    fresh = tmp / "nowy"
    fresh.mkdir()
    summary = ab.import_sealed(sealed_bundle, PASS, fresh / "projekty", fresh / "cfg")
    new_cfg = json.loads((fresh / "cfg" / "config.json").read_text())
    check("agent odtworzony", summary["agents_imported"] == 1)
    check("klucz API dziala na nowym urzadzeniu", new_cfg.get("groq_api_key") == SECRET)
    check("podsumowanie MOWI userowi, ze wgralo klucz",
          "groq_api_key" in summary["secrets_applied"])
    check("ustawienia przenosne przyszly", new_cfg.get("language") == "pl-PL")
    check("lokalna sciezka claude NIE nadpisana z paczki",
          "claude_command" not in new_cfg)

    expect_raises("import ZLYM haslem odmawia",
                  lambda: ab.import_sealed(sealed_bundle, "zle", fresh / "p2", fresh / "c2"))
    expect_raises("import paczki NIEzaszyfrowanej odrzucony",
                  lambda: ab.import_sealed(plain_bundle, PASS, fresh / "p3", fresh / "c3"))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n" + ("=== WYNIK: WSZYSTKO OK ===" if not FAILED
              else f"=== WYNIK: {len(FAILED)} BLEDOW ===\n" + "\n".join(FAILED)))
sys.exit(1 if FAILED else 0)
