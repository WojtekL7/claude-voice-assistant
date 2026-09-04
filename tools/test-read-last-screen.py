#!/usr/bin/env python3
"""BRAMKA: 🔊 „czytaj ostatnią" przy ZAMROŻONYM dzienniku — odczyt z EKRANU.

PO CO: 2026-09-04 user kliknął 🔊 w zakładce SEO M i dostał CISZĘ. Zmierzone
w `read-last-debug.log`: wykrycie zamrożenia zadziałało (762 s), ale plan B
(ekran) zwrócił 0 znaków, bo kotwica z dziennika była o 73 min STARSZA niż
zawartość bufora ekranu (przycinanego do 5000 zn.), a zapasowy ekstraktor ramek
oddaje 0 na prawdziwych zrzutach.

CO PILNUJE:
  A. filtr ozdób TUI działa i NIE zjada treści (kontrola odwrotna),
  B. wzorzec ozdób stoi w JEDNYM miejscu (nikt go nie wkleił inline),
  C. trzy tory `_screen_tail_since` — w tym TOR 3, który nie pozwala oddać
     pustki, gdy ekran coś ma (to on naprawia zgłoszenie),
  D. mostek do siatki xterma istnieje po obu stronach (JS + Python),
  E. kontrole odwrotne: pusty ekran nadal daje „nic".

WYNIKI SABOTAŻU — ZMIERZONE 2026-09-04 (nie przewidywane), narzędzie:
`tools/sabotaz-read-last-screen.py <wariant>` (jeden wariant = jedno wywołanie):
    bez-ogona                 -> 2 asercje  (wraca CISZA ze zgłoszenia)
    bez-naprawy-kodowania     -> 1 asercja
    bez-progu-ekstraktora     -> 2 asercje  (czyta 79 zn. z 490)
    bez-siatki                -> 11 asercji
    filtr-nic-nie-robi        -> 10 asercji
    wzorzec-wklejony-inline   -> 2 asercje
    bez-mostka-js             -> 1 asercja
⚠️ `bez-mostka-js` zapalał POCZĄTKOWO 0 asercji: asercja pytała o PODCIĄG
`window.__termScreenText`, który siedzi też w `__termScreenTextWYLACZONE`.
Wykrył to dopiero sabotaż — sama zielona bramka tego nie widziała.
Uruchamiać z korzenia repo:
    env -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH \\
        QT_QPA_PLATFORM=offscreen python3 -B tools/test-read-last-screen.py
"""
import os
import sys
import tempfile

# ⛔ HOME PRZED importem config — ścieżki liczą się w chwili importu, a kod
# produkcyjny wołany z testu pisze tam, gdzie pisze na produkcji (już raz
# zatruliśmy w ten sposób prawdziwy dziennik diagnostyczny usera).
_ATRAPA_HOME = tempfile.mkdtemp(prefix="cva-test-screen-")
os.environ['HOME'] = _ATRAPA_HOME
os.environ.pop('CVA_READ_LAST_DEBUG', None)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KORZEN, 'src'))
os.chdir(KORZEN)

from core.text_cleaner import strip_tui_noise, repair_terminal_mojibake  # noqa: E402

OK = FAIL = 0


def spr(warunek, opis):
    global OK, FAIL
    if warunek:
        OK += 1
        print("[OK ] " + opis)
    else:
        FAIL += 1
        print("[FAIL] " + opis)


# ---------------------------------------------------------------- A. FILTR TUI
print("\n--- A. Filtr ozdób interfejsu ---")
SMIECI = [
    "* Working… (12m 12s · ↓ 22.4k tokens)",
    "✻ Pondering… (3m 1s · ↑ 1.2k tokens · esc to interrupt)",
    "  ⎿  Tip: Use /btw to ask a quick side question",
    "Enter to select · Tab/Arrow keys to navigate · Esc to cancel",
    "  Read 1 file (ctrl+o to expand)",
    "? for shortcuts",
    "⏵⏵ accept edits on",
    "─────────────────────────────────────────",
]
for linia in SMIECI:
    spr(strip_tui_noise(linia) == "", "ozdoba znika: %r" % linia.strip()[:44])

# ⛔ KONTROLA ODWROTNA — to jest sedno tej sekcji. Filtr, który zjada treść,
# jest GORSZY niż brak filtra: lektor zamilkłby w połowie zdania, a nikt by
# nie wiedział dlaczego (dokładnie historia `tables_to_prose`).
TRESC = [
    "Zmierzyłem stan faktyczny, zanim cokolwiek zaproponuję.",
    "1. Runbook faktycznie wysyła śmieci. Puściłem próbę na sucho.",
    "Pełny: 4 punkty (Zalecane)",
    "Enter kosztuje mniej niż godzina pracy.",
    "Tworzenie kopii zapasowej trwa 12 minut (bez kompresji).",
    "Wpisać PEŁNE polecenie zamiast skrótu rsync i tak dalej.",
]
for linia in TRESC:
    spr(strip_tui_noise(linia).strip() == linia.strip(),
        "treść przeżywa: %r" % linia[:44])

spr(strip_tui_noise("│  Jaki zakres poprawki wykonuję?  │").strip().startswith("Jaki zakres"),
    "ramka zdjęta, treść w środku zostaje")
spr(strip_tui_noise("") == "" and strip_tui_noise(None) is None,
    "pusty/None nie wywraca filtra")

# ---------------------------------------- A2. GRANICA METODY (zmierzona, nie założona)
print("\n--- A2. Granica metody na PRAWDZIWYM starym zrzucie ---")
ZRZUT = os.path.join(KORZEN, 'tools', 'fixtures', 'ekran-pytanie-2026-06-18.txt')
surowy = open(ZRZUT, encoding='utf-8', errors='replace').read()
po = strip_tui_noise(repair_terminal_mojibake(surowy))
spr(len(po) > 200, "ze starego zrzutu zostaje treść (%d zn. z %d)" % (len(po), len(surowy)))
# ⚠️ TO NIE JEST USTERKA FILTRA, TYLKO POWÓD ZMIANY ŹRÓDŁA. W starym buforze
# (strumień porcji z PTY) pasek spinnera jest POSZATKOWANY na pojedyncze znaki
# rozsypane po setkach linii ('W', 'o', 'r', '✻Wk', 'orin6'…), więc żaden filtr
# LINIOWY go nie posklei. W siatce xterma to jeden wiersz — i tam filtr działa
# (dowodzą tego asercje z sekcji A). Asercja stoi tu jawnie, żeby nikt nie
# „naprawiał" filtra w miejscu, w którym problemem jest ŹRÓDŁO.
spr("Working" in po,
    "GRANICA: w starym strumieniu PTY spinner jest poszatkowany — filtr liniowy "
    "go NIE usunie (dlatego czytamy siatkę xterma)")

# ------------------------------------------------- B. JEDNO ŹRÓDŁO WZORCA OZDÓB
print("\n--- B. Wzorzec ozdób TUI stoi w JEDNYM miejscu ---")
zrodla = []
for katalog, _, pliki in os.walk(os.path.join(KORZEN, 'src')):
    for p in pliki:
        if p.endswith('.py'):
            zrodla.append(os.path.join(katalog, p))
definicje = [p for p in zrodla
             if '_TUI_NOISE_LINE_RE = re.compile' in open(p, encoding='utf-8').read()]
spr(len(definicje) == 1,
    "wzorzec ozdób zdefiniowany dokładnie RAZ (znaleziono %d)" % len(definicje))
spr(definicje and definicje[0].endswith('text_cleaner.py'),
    "…i stoi w text_cleaner.py")

# ------------------------------------------------------ C. TRZY TORY ODCZYTU EKRANU
print("\n--- C. _screen_tail_since: trzy tory (KOD WYCIĘTY Z PRODUKCJI) ---")
from gui.main_window import MainWindow  # noqa: E402


class AtrapaZakladki:
    """Atrapa BRZEGU (zakładka), nie logiki. Decyzję bada kod produkcyjny."""

    def __init__(self, siatka="", bufor=""):
        self._siatka = siatka
        self._terminal_output_buffer = bufor

    def screen_text_snapshot(self, max_age_secs):
        return self._siatka


class Sonda:
    """Prawdziwe metody MainWindow, bez budowania całego okna."""
    _screen_source = MainWindow._screen_source
    # ⚠️ `_bez_spacji` jest @staticmethod — wstawiona do klasy „goła"
    # dostałaby `self` jako pierwszy argument. Owijamy z powrotem.
    _bez_spacji = staticmethod(MainWindow._bez_spacji)
    _screen_tail_since = MainWindow._screen_tail_since


sonda = Sonda()
KOTWICA = ("Przeczytałem oba pliki w całości (COMMON: 1172 linie / 331 kB) "
           "oraz CLAUDE-SEO-MANAGER, a poniżej wypisuję otwarte sprawy.")
NOWA = ("Zmierzyłem stan faktyczny, zanim cokolwiek zaproponuję. Notatka w pamięci "
        "częściowo kłamała — poniżej co jest naprawdę, punkt po punkcie i z liczbami.")

# TOR 1 — kotwica JEST na ekranie: bierzemy wszystko po niej.
tab = AtrapaZakladki(siatka=KOTWICA + "\n" + NOWA)
tekst, metoda = sonda._screen_tail_since(tab, KOTWICA)
spr(tekst is not None and metoda.startswith('kotwica'), "TOR 1: kotwica na ekranie → 'kotwica'")
spr(tekst is not None and "Zmierzyłem stan faktyczny" in tekst,
    "TOR 1: oddaje treść PO kotwicy, nie samą kotwicę")
spr(tekst is not None and "1172 linie" not in tekst,
    "TOR 1: stara wypowiedź NIE wchodzi do wyniku (kontrola odwrotna)")

# TOR 1 na mojibake — to była druga, niezmierzona wcześniej słabość.
tab = AtrapaZakladki(siatka=(KOTWICA + "\n" + NOWA).encode('utf-8').decode('latin-1'))
tekst, metoda = sonda._screen_tail_since(tab, KOTWICA)
spr(tekst is not None and metoda.startswith('kotwica'),
    "TOR 1: kotwica trafia MIMO mojibake na ekranie (naprawa PRZED porównaniem)")

# DZISIEJSZY PRZYPADEK: kotwicy na ekranie NIE MA (wyjechała 73 min temu).
# Najważniejsza asercja całej bramki — to ona odpowiada na zgłoszenie „zero reakcji".
tab = AtrapaZakladki(siatka=NOWA)
tekst, metoda = sonda._screen_tail_since(tab, KOTWICA)
spr(tekst is not None, "BRAK KOTWICY: NIE oddajemy pustki (to naprawa zgłoszenia)")
spr(tekst is not None and "Zmierzyłem stan faktyczny" in tekst,
    "BRAK KOTWICY: w wyniku jest nowa wypowiedź")

# TOR 3 na PRAWDZIWYM ekranie + PRÓG ZAUFANIA do ekstraktora.
# ⛔ Premisa jest ZMIERZONA, nie założona: ekstraktor ramek oddaje na tym
# ekranie 79 zn. z 490, bo ramki należą do widgetu PYTANIA, nie do wypowiedzi.
# Bez progu lektor przeczytałby 1/6 treści — dla użytkownika nowa usterka.
ekran_realny = strip_tui_noise(repair_terminal_mojibake(surowy))
tekst, metoda = sonda._screen_tail_since(
    AtrapaZakladki(siatka=ekran_realny), "KOTWICY-TEJ-NA-PEWNO-TU-NIE-MA-ZMYSLONA-DLUGA-FRAZA")
spr(metoda.startswith('ogon ekranu'),
    "TOR 3: na prawdziwym ekranie wygrywa ogon, nie okruch (%s)" % metoda)
spr(tekst is not None and len(tekst.strip()) >= 400,
    "TOR 3: oddaje CAŁĄ widoczną treść (%d zn. z %d), nie 79 zn."
    % (len((tekst or "").strip()), len(ekran_realny)))

# Kontrola odwrotna progu: gdy ekran jest KRÓTKI, ekstraktorowi ufamy dalej.
maly = "⏺ To jest krótka odpowiedź agenta, która w całości mieści się na ekranie."
tekst_m, metoda_m = sonda._screen_tail_since(AtrapaZakladki(siatka=maly), "")
spr(tekst_m is not None, "PRÓG: na krótkim ekranie nadal coś oddajemy (%s)" % metoda_m)

# ŹRÓDŁO — siatka bije stary bufor 5000 zn.
tab = AtrapaZakladki(siatka=NOWA, bufor="STARY BUFOR " * 40)
tekst, metoda = sonda._screen_tail_since(tab, "")
spr('[siatka]' in metoda, "ŹRÓDŁO: siatka xterma wygrywa z buforem 5k (%s)" % metoda)
spr(tekst is not None and "STARY BUFOR" not in tekst, "ŹRÓDŁO: stary bufor nie wchodzi, gdy jest siatka")

# ŹRÓDŁO — brak siatki (QTermWidget / migawka nieświeża) → schodzimy na bufor.
tab = AtrapaZakladki(siatka="", bufor=NOWA)
tekst, metoda = sonda._screen_tail_since(tab, "")
spr(tekst is not None and '[bufor5k]' in metoda,
    "ŹRÓDŁO: bez siatki schodzimy na stary bufor (%s)" % metoda)

# ------------------------------------------------------------ E. KONTROLE ODWROTNE
print("\n--- E. Kontrole odwrotne ---")
tekst, metoda = sonda._screen_tail_since(AtrapaZakladki(), KOTWICA)
spr(tekst is None and 'brak bufora' in metoda, "pusty ekran → 'brak bufora', nie zmyślony tekst")
tekst, metoda = sonda._screen_tail_since(AtrapaZakladki(siatka="   \n \n"), KOTWICA)
spr(tekst is None, "ekran z samych spacji → nadal nic")
tekst, metoda = sonda._screen_tail_since(AtrapaZakladki(siatka="krótko"), KOTWICA)
spr(tekst is None, "ekran krótszy niż próg 40 zn. → nic (nie czytamy okruchów)")
spr(sonda._screen_tail_since(None, KOTWICA)[0] is None, "brak zakładki nie wywraca kodu")

# ------------------------------------------------------------- D. MOSTEK DO SIATKI
print("\n--- D. Mostek do siatki xterma (obie strony) ---")
html = open(os.path.join(KORZEN, 'src', 'assets', 'web', 'terminal.html'), encoding='utf-8').read()
spr('window.__termScreenText = function' in html,
    "JS: terminal.html DEFINIUJE __termScreenText (nie sama nazwa — podciąg myli)")
spr('translateToString' in html, "JS: czyta wyrenderowaną siatkę (translateToString)")
tb = open(os.path.join(KORZEN, 'src', 'gui', 'terminal_backend.py'), encoding='utf-8').read()
spr(tb.count('def screen_text') == 2, "Python: interfejs + implementacja WebTerminala (%d)" % tb.count('def screen_text'))
spr('__termScreenText' in tb, "Python: WebTerminal woła tę właśnie funkcję JS")
at = open(os.path.join(KORZEN, 'src', 'gui', 'agent_tab.py'), encoding='utf-8').read()
spr('def refresh_screen_text_cache' in at and 'def screen_text_snapshot' in at,
    "Zakładka: ma odświeżanie i odczyt migawki")
mw = open(os.path.join(KORZEN, 'src', 'gui', 'main_window.py'), encoding='utf-8').read()
spr(mw.count('refresh_screen_text_cache()') >= 2,
    "Migawka podgrzewana w pętli ORAZ przy kliknięciu (%d wywołań)" % mw.count('refresh_screen_text_cache()'))
spr('strip_tui_noise(repair_terminal_mojibake(' in mw,
    "KOLEJNOŚĆ: naprawa kodowania PRZED filtrem ozdób")

print("\nWYNIK: %d OK, %d FAIL" % (OK, FAIL))
sys.exit(1 if FAIL else 0)
