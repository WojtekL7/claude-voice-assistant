#!/usr/bin/env python3
"""Test CALEJ drogi chmury: przeprowadzka agentow na nowy komputer.

Zbierz mozg -> zaszyfruj -> wyslij na Dysk -> pobierz na "nowym komputerze" ->
odszyfruj -> odtworz agentow. Wszystko na atrapie serwera Google: bez sieci,
bez konta usera, bez dotykania prawdziwej konfiguracji.

Kluczowe pytanie, na ktore ten test odpowiada: czy dane, ktore realnie leca do
chmury, sa NIECZYTELNE. Dowodem NIE jest "nie widac hasla w bajtach" (kompresja
i tak by je ukryla), tylko to, ze paczki NIE DA SIE otworzyc jako archiwum.

Uruchomienie:  python3 tools/test-cloud-e2e.py
"""
import importlib.util
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS.parent / "src"))

import core.skills_manager as skills_manager                    # noqa: E402
from core.cloud import bundle_crypto as bc                      # noqa: E402
from core.cloud.agent_bundle import export_sealed, import_sealed  # noqa: E402
from core.cloud.google_drive import GoogleDriveProvider         # noqa: E402

# Atrapa Google zyje w pliku z myslnikami (nieimportowalnym) -> ladujemy sciezka.
_spec = importlib.util.spec_from_file_location("fake_google", TOOLS / "test-cloud-drive.py")
_fake_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fake_mod)
FakeGoogle = _fake_mod.FakeGoogle

PASS = FAIL = 0
KLUCZ_API = "gsk_TAJNY_KLUCZ_TESTOWY_1234567890"


def check(label, got, want):
    global PASS, FAIL
    ok = got == want
    PASS, FAIL = PASS + ok, FAIL + (not ok)
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"         oczekiwano: {want!r}\n         otrzymano : {got!r}")


def zbuduj_komputer_a(root: Path) -> Path:
    """Konfiguracja 'starego komputera': 2 agentow, pliki pamieci, klucz API."""
    cfg = root / "config-a"
    projekty = root / "Projekty"
    (cfg).mkdir(parents=True)
    for nazwa in ("crm", "sklep"):
        d = projekty / nazwa
        d.mkdir(parents=True)
        (d / "PAMIEC.md").write_text(f"# Pamiec projektu {nazwa}\nWazna wiedza.\n",
                                     encoding="utf-8")
    agenci = [
        {"name": "CRM", "working_directory": str(projekty / "crm"),
         "memory_files": [str(projekty / "crm" / "PAMIEC.md")],
         "model": "opus", "tab_color": "#7c5cff", "auto_start": True},
        {"name": "Sklep", "working_directory": str(projekty / "sklep"),
         "memory_files": [str(projekty / "sklep" / "PAMIEC.md")],
         "model": "sonnet", "tab_color": "#00b3a4", "auto_start": False},
    ]
    (cfg / "agents.json").write_text(json.dumps(agenci), encoding="utf-8")
    (cfg / "config.json").write_text(json.dumps({
        "language": "pl-PL", "skin_version": 4, "auto_read": True,
        "skin_colors": {"button_bg": "#7c5cff"},
        "groq_api_key": KLUCZ_API,                  # SEKRET — tylko przez szyfrowanie
        "claude_command": "/home/stary/.local/bin/claude",   # sciezka lokalna maszyny
        "wymyslone_nowe_pole": "cokolwiek",         # nieznane -> ma zostac pominiete
    }), encoding="utf-8")
    (cfg / "memory_projects.json").write_text(json.dumps({"crm": ["PAMIEC.md"]}),
                                              encoding="utf-8")
    (cfg / "quick_actions.json").write_text(json.dumps({"a1": "Zrob podsumowanie"}),
                                            encoding="utf-8")
    return cfg


def main():
    root = Path(tempfile.mkdtemp(prefix="cva-e2e-"))
    fake = FakeGoogle()
    try:
        # Skille kierujemy do katalogu tymczasowego — test NIE moze dotknac
        # prawdziwego ~/.claude/skills usera (ani czytac, ani zapisywac).
        skills_a = root / "skills-a"
        (skills_a / "raport").mkdir(parents=True)
        (skills_a / "raport" / "SKILL.md").write_text("Instrukcja robienia raportu.",
                                                      encoding="utf-8")
        skills_manager.SKILLS_DIR = skills_a

        cfg_a = zbuduj_komputer_a(root)
        haslo = bc.generate_passphrase()

        print(f"\n1. Stary komputer: pakowanie mozgu (haslo: {len(haslo)} znakow)")
        paczka = export_sealed(haslo, config_dir=cfg_a)
        check("paczka powstala", len(paczka) > 200, True)
        check("jest oznaczona jako zaszyfrowana", bc.is_sealed(paczka), True)

        print("\n2. Czy to, co leci do chmury, jest NIECZYTELNE")
        try:
            zipfile.ZipFile(__import__("io").BytesIO(paczka)).namelist()
            check("nie da sie otworzyc jako archiwum", "otworzyla sie", "BadZipFile")
        except zipfile.BadZipFile:
            check("nie da sie otworzyc jako archiwum", "BadZipFile", "BadZipFile")
        check("klucz API niewidoczny w bajtach", KLUCZ_API.encode() in paczka, False)
        check("nazwy agentow niewidoczne w bajtach", b"CRM" in paczka, False)

        print("\n3. Wysylka na Dysk Google (atrapa)")
        dysk_a = GoogleDriveProvider(
            client_id="test.apps.googleusercontent.com",
            token_path=root / "token-a.json", folder_name="Vibe Coding Assistant",
            auth_url=f"{fake.base}/auth", token_url=f"{fake.base}/token",
            api_base=f"{fake.base}/drive/v3", upload_base=f"{fake.base}/upload/drive/v3",
            open_browser=fake.open_browser, consent_timeout=20)
        dysk_a.upload("brain.vcabundle", paczka)
        check("paczka widoczna w chmurze", dysk_a.list(), ["brain.vcabundle"])

        print("\n4. NOWY komputer: osobne konto lokalne, pobranie paczki")
        dysk_b = GoogleDriveProvider(
            client_id="test.apps.googleusercontent.com",
            token_path=root / "token-b.json", folder_name="Vibe Coding Assistant",
            auth_url=f"{fake.base}/auth", token_url=f"{fake.base}/token",
            api_base=f"{fake.base}/drive/v3", upload_base=f"{fake.base}/upload/drive/v3",
            open_browser=fake.open_browser, consent_timeout=20)
        pobrana = dysk_b.download("brain.vcabundle")
        check("pobrane bajty identyczne z wyslanymi", pobrana, paczka)

        print("\n5. Odtworzenie agentow na nowym komputerze")
        cfg_b = root / "config-b"
        cfg_b.mkdir()
        projekty_b = root / "NoweProjekty"
        projekty_b.mkdir()
        skills_b = root / "skills-b"
        skills_b.mkdir()
        skills_manager.SKILLS_DIR = skills_b
        import_sealed(pobrana, haslo, projekty_b, config_dir=cfg_b)

        agenci_b = json.loads((cfg_b / "agents.json").read_text(encoding="utf-8"))
        check("obaj agenci odtworzeni", sorted(a["name"] for a in agenci_b),
              ["CRM", "Sklep"])
        check("ustawienia agenta zachowane (model)",
              sorted(a.get("model", "") for a in agenci_b), ["opus", "sonnet"])
        wd = [a["working_directory"] for a in agenci_b]
        check("sciezki przemapowane na NOWY katalog projektow",
              all(str(projekty_b) in w for w in wd), True)
        check("zadna sciezka nie wskazuje starego komputera",
              any(str(root / "Projekty") in w for w in wd), False)

        pamiec = list(projekty_b.rglob("PAMIEC.md"))
        check("pliki pamieci odtworzone", len(pamiec), 2)
        check("tresc pamieci zachowana",
              "Wazna wiedza" in pamiec[0].read_text(encoding="utf-8"), True)

        cfg_json = json.loads((cfg_b / "config.json").read_text(encoding="utf-8"))
        check("klucz API dojechal (decyzja usera: klucze w paczce)",
              cfg_json.get("groq_api_key"), KLUCZ_API)
        check("jezyk, skorka i ustawienia przeniesione",
              (cfg_json.get("language"), cfg_json.get("skin_version"),
               cfg_json.get("auto_read")), ("pl-PL", 4, True))
        check("kolory skorki przeniesione",
              (cfg_json.get("skin_colors") or {}).get("button_bg"), "#7c5cff")
        check("sciezka do claude NIE zostala przeniesiona (lokalna maszyny)",
              cfg_json.get("claude_command"), None)
        check("NIEZNANE pole configu pominiete (biala lista chroni przed wyciekiem)",
              cfg_json.get("wymyslone_nowe_pole"), None)
        check("skill odtworzony", (skills_b / "raport" / "SKILL.md").exists(), True)
        # Szybkie akcje i projekty pamieci tez sa czescia "mozgu" — bez tej
        # asercji gwarancja byla tylko deklaracja (pytanie usera 2026-07-21).
        qa_path, mp_path = cfg_b / "quick_actions.json", cfg_b / "memory_projects.json"
        check("szybkie akcje przeniesione",
              json.loads(qa_path.read_text(encoding="utf-8")) if qa_path.exists() else None,
              {"a1": "Zrob podsumowanie"})
        check("projekty pamieci przeniesione",
              json.loads(mp_path.read_text(encoding="utf-8")) if mp_path.exists() else None,
              {"crm": ["PAMIEC.md"]})

        print("\n6. Przypadki brzegowe (bez nich zielone nic nie znaczy)")
        try:
            import_sealed(pobrana, "ZLE-HASLO-1234", projekty_b, config_dir=cfg_b)
            check("zle haslo -> odmowa", "przeszlo", "wyjatek")
        except Exception:
            check("zle haslo -> odmowa", "wyjatek", "wyjatek")
        try:
            import_sealed(b"PK\x03\x04zwykly zip", haslo, projekty_b, config_dir=cfg_b)
            check("paczka niezaszyfrowana -> odmowa", "przeszla", "wyjatek")
        except Exception:
            check("paczka niezaszyfrowana -> odmowa", "wyjatek", "wyjatek")
        try:
            export_sealed("", config_dir=cfg_a)
            check("brak hasla -> odmowa wysylki", "przeszlo", "wyjatek")
        except Exception:
            check("brak hasla -> odmowa wysylki", "wyjatek", "wyjatek")

        print(f"\n=== WYNIK: {PASS} OK, {FAIL} FAIL ===")
        return 1 if FAIL else 0
    finally:
        fake.stop()
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
