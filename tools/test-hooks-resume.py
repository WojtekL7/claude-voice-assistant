#!/usr/bin/env python3
"""Bramka ETAPU 4: hooki Claude Code (pewna wiedza o modelu) + wznawianie rozmów.

Uruchom:  python3 tools/test-hooks-resume.py

Fixture = PRAWDZIWE ładunki hooków zdjęte 2026-09-14 z żywego `claude` 2.1.270
(`tools/fixtures/hook-events-2026-09-14.jsonl`). Parser cudzego formatu pisany
„z głowy" przechodzi na zielono i milczy na produkcji — stąd dosłowny ładunek.

DWIE RZECZY, KTÓRYCH APKA DOTĄD NIE WIEDZIAŁA NA PEWNO:
  1. jaki model NAPRAWDĘ pracuje (dziennik mówi dopiero przy odpowiedzi),
  2. które rozmowy żyły przy zamknięciu (identyfikatory sesji nigdzie nie
     były zapisywane, więc po restarcie zakładki wstawały puste).

⛔ ASERCJA PILNUJĄCA NAJWIĘKSZEGO RYZYKA TEGO ETAPU (sekcja 4): hooki NIE MOGĄ
trafiać do `~/.claude/settings.json`. Tamten plik obowiązuje KAŻDĄ sesję Claude
Code na tym komputerze, także uruchomioną poza apką — zostawialibyśmy ślad
w cudzej pracy. Wpinamy je wyłącznie przez własny plik i `--settings`.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FIX = ROOT / "tools" / "fixtures" / "hook-events-2026-09-14.jsonl"

_passed = 0
_failed = 0


def check(name, condition, detail=""):
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"[OK]   {name}")
    else:
        _failed += 1
        print(f"[FAIL] {name}  {detail}")


from core import claude_hooks as ch  # noqa: E402
from core import session_registry as sr  # noqa: E402

# ===================== 1. czytanie PRAWDZIWYCH zdarzeń =====================
with tempfile.TemporaryDirectory() as tmp:
    kat = Path(tmp)
    (kat / ch.EVENTS_NAME).write_bytes(FIX.read_bytes())

    zdarzenia, offset = ch.read_events(kat, 0)
    check("odczytane wszystkie zdarzenia z prawdziwego dziennika",
          len(zdarzenia) == 5, len(zdarzenia))
    check("offset przesunął się na koniec pliku",
          offset == (kat / ch.EVENTS_NAME).stat().st_size, offset)
    nazwy = [z.get("hook_event_name") for z in zdarzenia]
    check("rozpoznane rodzaje zdarzeń",
          nazwy == ["SessionStart", "PostModelSwitch", "SessionEnd",
                    "SessionStart", "SessionEnd"], nazwy)
    # ⭐ Dowód, że `--resume` NIE zakłada nowej rozmowy: drugi start ma to samo
    # `session_id` i `source="resume"` — czytnik dziennika zostaje przypięty.
    _starty = [z for z in zdarzenia if z.get("hook_event_name") == "SessionStart"]
    check("wznowienie zachowuje TEN SAM identyfikator sesji",
          len({z.get("session_id") for z in _starty}) == 1,
          [z.get("session_id") for z in _starty])
    check("wznowiona sesja jest oznaczona jako `resume`",
          [z.get("source") for z in _starty] == ["startup", "resume"],
          [z.get("source") for z in _starty])

    # Drugi odczyt od tego samego miejsca MUSI być pusty — inaczej apka
    # przerabiałaby te same zdarzenia w kółko przy każdym ticku (800 ms).
    znowu, offset2 = ch.read_events(kat, offset)
    check("drugi odczyt nic nie powtarza", znowu == [] and offset2 == offset)

    # Skurczony plik (przycinanie) NIE MOŻE odgrywać historii od zera —
    # ta sama pułapka wywróciła kiedyś auto-czytanie po kompaktowaniu.
    # ⛔ PLIK MUSI ZOSTAĆ NIEPUSTY: przy pustym poprawne i zepsute zachowanie
    # dają identyczny wynik ([], 0), więc test NIC NIE ROZRÓŻNIA. Zmierzone —
    # pierwsza wersja tej asercji przepuściła sabotaż H1 na zielono.
    krotszy = json.dumps({"hook_event_name": "SessionStart",
                          "session_id": "po-przycieciu"}) + "\n"
    (kat / ch.EVENTS_NAME).write_text(krotszy, encoding="utf-8")
    rozmiar_po = (kat / ch.EVENTS_NAME).stat().st_size
    puste, offset3 = ch.read_events(kat, offset)
    check("po skurczeniu pliku zaczynamy od jego KOŃCA, nie od zera",
          puste == [] and offset3 == rozmiar_po, (puste, offset3, rozmiar_po))

_prz = [z for z in zdarzenia if z.get("hook_event_name") == "PostModelSwitch"][0]
check("model PO przełączeniu wyłuskany",
      ch.model_from_event(_prz) == "claude-haiku-4-5-20251001", ch.model_from_event(_prz))
check("model SPRZED przełączenia niesie to, co uruchomił „Domyślny”",
      _prz.get("from_model") == "claude-opus-5[1m]", _prz.get("from_model"))
check("dopisek wariantu okna zdjęty z identyfikatora",
      ch.normalize_model_id("claude-opus-5[1m]") == "claude-opus-5")
check("identyfikator bez dopisku zostaje nietknięty",
      ch.normalize_model_id("claude-sonnet-5") == "claude-sonnet-5")
# KONTROLE ODWROTNE — zdarzenia sesji NIE niosą modelu w tym ładunku.
_start = [z for z in zdarzenia if z.get("hook_event_name") == "SessionStart"][0]
check("SessionStart bez pola `model` → None, a nie zgadywanie",
      ch.model_from_event(_start) is None, _start.get("model"))
check("nieznane zdarzenie → None", ch.model_from_event({"hook_event_name": "Cos"}) is None)
check("śmieć zamiast zdarzenia → None zamiast wyjątku",
      ch.model_from_event(None) is None and ch.model_from_event("tekst") is None)

# Model z hooka MUSI dać się przełożyć na naszą nazwę — inaczej pasek
# pokazałby surowy identyfikator zamiast „Haiku 4.5".
import config as cfg  # noqa: E402
check("identyfikator z hooka mapuje się na klucz modelu apki",
      cfg.CLAUDE_MODEL_API_IDS.get("claude-haiku-4-5-20251001") == "haiku",
      cfg.CLAUDE_MODEL_API_IDS.get("claude-haiku-4-5-20251001"))
check("identyfikator sprzed przełączenia też się mapuje",
      cfg.CLAUDE_MODEL_API_IDS.get(ch.normalize_model_id("claude-opus-5[1m]")) == "opus")

# ===================== 2. przygotowanie hooków i limit =====================
with tempfile.TemporaryDirectory() as tmp:
    kat = Path(tmp)
    ustawienia = ch.ensure_hooks(kat)
    check("plik ustawień powstał", ustawienia.is_file())
    dane = json.loads(ustawienia.read_text(encoding="utf-8"))
    check("plik zawiera WYŁĄCZNIE hooki (nic cudzego nie dokładamy)",
          list(dane) == ["hooks"], list(dane))
    # ⛔ ZBIÓR WYPISANY WPROST, NIE `ch.HOOK_EVENTS`. Porównanie z tą stałą
    # przesuwa OBIE strony naraz, gdy ktoś ją rozszerzy — czyli test porównuje
    # stałą samą ze sobą (zmierzone: sabotaż H10 dokładający `PreToolUse`
    # przeszedł wtedy na zielono). Hook odpala się przy KAŻDEJ turze, więc
    # dołożenie zdarzenia to koszt płacony bez przerwy i musi być decyzją.
    check("prosimy DOKŁADNIE o trzy zdarzenia, nie o więcej",
          set(dane["hooks"]) == {"SessionStart", "SessionEnd", "PostModelSwitch"},
          sorted(dane["hooks"]))
    check("plik zgadza się z listą zadeklarowaną w module",
          set(dane["hooks"]) == set(ch.HOOK_EVENTS), sorted(ch.HOOK_EVENTS))
    skrypt = ch.script_path(kat)
    check("dopisywacz powstał", skrypt.is_file())
    check("dopisywacz jest wykonywalny", os.access(skrypt, os.X_OK) or os.name == "nt")
    tresc = skrypt.read_text(encoding="utf-8")
    check("dopisywacz kończy się kodem 0 (hook nie może wywrócić sesji)",
          "exit 0" in tresc or "exit /b 0" in tresc)
    check("dopisywacz NIE pisze na wyjście (wyjście idzie do Claude = koszt tokenów)",
          "echo " not in tresc.replace("echo.", ""))
    check("powtórne przygotowanie nie wywraca się (idempotentne)",
          ch.ensure_hooks(kat) == ustawienia)

    # Limit dziennika — pasywny log bez limitu urósł kiedyś do 99 MB.
    dziennik = ch.events_path(kat)
    dziennik.write_text("x" * 100, encoding="utf-8")
    check("mały plik NIE jest przycinany", ch.trim_events(kat, max_bytes=1000) is False)
    # ⛔ LIMIT NIE MOŻE DZIELIĆ SIĘ BEZ RESZTY PRZEZ DŁUGOŚĆ LINII — inaczej
    # cięcie trafia w granicę linii PRZEZ PRZYPADEK i sabotaż „tnij w połowie"
    # przechodzi na zielono (zmierzone: 8-bajtowe linie przy limicie 200).
    # Stąd linie o RÓŻNEJ długości i limit niebędący ich wielokrotnością.
    dziennik.write_text("".join(
        json.dumps({"hook_event_name": "SessionStart", "n": i}) + "\n"
        for i in range(200)), encoding="utf-8")
    check("duży plik jest przycinany", ch.trim_events(kat, max_bytes=205) is True)
    po = dziennik.read_text(encoding="utf-8")
    check("po przycięciu plik mieści się w limicie", len(po.encode()) <= 205, len(po))
    check("przycinamy po CAŁYCH liniach (urwana linia to śmieć dla czytnika)",
          all(l.startswith("{") and l.endswith("}")
              for l in po.splitlines() if l.strip()), po[:80])
    # ⛔ OSŁONA: badany błąd zostawia linię, której `json.loads` NIE przeczyta
    # — gołe wywołanie wywaliłoby bramkę zamiast zgłosić [FAIL] (zmierzone
    # sabotażem H3: 28 z 63 wykonanych sprawdzeń, wynik nic nie znaczył).
    def _czyta_sie(linia):
        try:
            json.loads(linia)
            return True
        except Exception:
            return False
    check("po przycięciu wszystkie linie NADAL dają się odczytać jako JSON",
          all(_czyta_sie(l) for l in po.splitlines() if l.strip()), po[:80])

check("ścieżka w argumencie jest w cudzysłowie (ścieżki bywają ze spacjami)",
      ch.settings_argument(Path("/a b/c.json")) == '--settings "/a b/c.json"')
check("cudzysłów w ścieżce jest odsiewany (rozerwałby polecenie)",
      '"' not in ch.settings_argument(Path('/a"b/c.json')).split('--settings ')[1][1:-1])

# ===================== 3. rejestr rozmów =====================
with tempfile.TemporaryDirectory() as tmp:
    kat = Path(tmp)
    projekty = kat / "projects"
    check("pusty rejestr → brak wpisów", sr.load(kat) == {})
    check("pusty rejestr → nic do wznowienia", sr.resumable(kat, projekty) == [])

    check("zapis wpisu", sr.record(kat, "agent-1", "sesja-aaa", "/tmp/x", "CRM") is True)
    check("brak identyfikatora agenta → nie zapisujemy",
          sr.record(kat, "", "sesja-bbb") is False)
    check("brak identyfikatora sesji → nie zapisujemy",
          sr.record(kat, "agent-2", "") is False)
    check("odczyt zwraca zapisane", sr.load(kat)["agent-1"]["session_id"] == "sesja-aaa")

    # ⛔ NAJWAŻNIEJSZE W TEJ SEKCJI: wpis bez dziennika NIE jest ofertą.
    check("wpis BEZ dziennika nie trafia do wznawialnych",
          sr.resumable(kat, projekty) == [], sr.resumable(kat, projekty))

    kat_proj = projekty / sr.encode_project_dir("/tmp/x")
    kat_proj.mkdir(parents=True, exist_ok=True)
    (kat_proj / "sesja-aaa.jsonl").write_text('{"a":1}\n', encoding="utf-8")
    lista = sr.resumable(kat, projekty)
    check("wpis Z dziennikiem jest wznawialny", len(lista) == 1, lista)
    check("wznawialny wpis niesie ścieżkę dziennika i rozmiar",
          lista and lista[0]["size"] > 0 and lista[0]["transcript_path"].endswith(
              "sesja-aaa.jsonl"), lista[:1])

    # Dziennik w INNYM katalogu projektów (user zmienił katalog roboczy agenta)
    # — identyfikator sesji jest unikalny, więc szukamy szerzej.
    sr.record(kat, "agent-3", "sesja-ccc", "/tmp/zupelnie-inny", "Inny")
    inny = projekty / "-jakis-inny-katalog"
    inny.mkdir(parents=True, exist_ok=True)
    (inny / "sesja-ccc.jsonl").write_text("{}\n", encoding="utf-8")
    check("dziennik znaleziony mimo zmiany katalogu roboczego",
          any(w["agent_id"] == "agent-3" for w in sr.resumable(kat, projekty)))

    check("zapomnienie wpisu", sr.forget(kat, "agent-1") is True)
    check("zapomnienie nieistniejącego → False", sr.forget(kat, "nie-ma") is False)
    check("po zapomnieniu wpis znika", "agent-1" not in sr.load(kat))

    zly = kat / sr.REGISTRY_NAME
    zly.write_text("{to nie jest json", encoding="utf-8")
    check("uszkodzony rejestr → pusto (fail-open), a nie wyjątek", sr.load(kat) == {})

# ===================== 4. wpięcie w okno główne (AST/treść) =====================
import ast  # noqa: E402

mw_txt = (ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
mw_tree = ast.parse(mw_txt)
mw_cls = {n.name: n for n in mw_tree.body if isinstance(n, ast.ClassDef)}.get("MainWindow")
mw_methods = ({n.name for n in ast.walk(mw_cls) if isinstance(n, ast.FunctionDef)}
              if mw_cls else set())
for nazwa in ("_hooks_argument", "_poll_hook_events", "_maybe_offer_resume",
              "_restart_agent_tab"):
    check(f"MainWindow ma metodę {nazwa}", nazwa in mw_methods)

check("polecenie startowe dokłada hooki", "self._hooks_argument()" in mw_txt)
check("pętla odpytująca czyta zdarzenia (sama metoda nie wystarcza)",
      "self._poll_hook_events()" in mw_txt)
check("wznawianie proponowane przy starcie",
      "QTimer.singleShot(2500, self._maybe_offer_resume)" in mw_txt)
# ⛔ PYTAMY O WYWOŁANIE, NIE O NAZWĘ. Sabotaż H8 zostawił `None and record(...)`,
# czyli wywołanie MARTWE — a asercja „czy napis występuje w pliku" przeszła na
# zielono. Liczymy instrukcje, które są SAMODZIELNYM wywołaniem `record`.
_zapisy_rejestru = 0
for n in ast.walk(mw_cls) if mw_cls else []:
    if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)):
        continue
    f = n.value.func
    if isinstance(f, ast.Attribute) and f.attr == "record":
        _zapisy_rejestru += 1
check("sesja jest ZAPISYWANA do rejestru (żywym wywołaniem, nie martwym)",
      _zapisy_rejestru >= 1, _zapisy_rejestru)
check("wznowienie idzie przez --resume", "--resume {wznow}" in mw_txt)

# ⛔ ASERCJA Z NAGŁÓWKA PLIKU.
_kod_hooki = ""
for n in ast.walk(mw_cls) if mw_cls else []:
    if isinstance(n, ast.FunctionDef) and n.name == "_hooks_argument":
        _ciało = [w for w in n.body
                  if not (isinstance(w, ast.Expr) and isinstance(w.value, ast.Constant)
                          and isinstance(w.value.value, str))]
        _kod_hooki = "\n".join(ast.unparse(w) for w in _ciało)
        break
check("hooki wpinane przez WŁASNY plik i --settings", "settings_argument" in _kod_hooki)
check("hooki NIE trafiają do ~/.claude/settings.json (cudzy plik, każda sesja)",
      "claude_settings" not in _kod_hooki and ".claude/settings" not in _kod_hooki,
      _kod_hooki[:120])

# Pierwszeństwo hooka nad dziennikiem — bez tego pasek migałby tam i z powrotem.
_kod_sync = ""
for n in ast.walk(mw_cls) if mw_cls else []:
    if isinstance(n, ast.FunctionDef) and n.name == "_sync_detected_model":
        _ciało = [w for w in n.body
                  if not (isinstance(w, ast.Expr) and isinstance(w.value, ast.Constant)
                          and isinstance(w.value.value, str))]
        _kod_sync = "\n".join(ast.unparse(w) for w in _ciało)
        break
check("dziennik NIE nadpisuje modelu, o którym powiedział hook",
      "_model_from_hook_session" in _kod_sync, _kod_sync[:120])
check("znacznik pierwszeństwa wiąże się z KONKRETNĄ sesją (restart go zeruje)",
      "_pinned_session_id" in _kod_sync)

for _k in ("dlg_resume_title", "dlg_resume_msg", "status_resumed"):
    check(f"napis '{_k}' w OBU językach",
          _k in cfg.UI_TRANSLATIONS["pl-PL"] and _k in cfg.UI_TRANSLATIONS["en-US"])
check("parytet słowników PL/EN",
      set(cfg.UI_TRANSLATIONS["pl-PL"]) == set(cfg.UI_TRANSLATIONS["en-US"]))
check("pytanie mówi WPROST, co się stanie po „Nie” (user musi wiedzieć, czy traci)",
      "nic nie tracą" in cfg.UI_TRANSLATIONS["pl-PL"]["dlg_resume_msg"])

print(f"\n=== {_passed} OK / {_failed} FAIL ===")
sys.exit(1 if _failed else 0)
