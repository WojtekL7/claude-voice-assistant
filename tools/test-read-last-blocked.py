#!/usr/bin/env python3
"""Bramka: 🔊 a PYTANIE Z POLAMI WYBORU na dole ekranu.

Po co: user 2026-08-28 — „jeżeli agent daje na dole pola wyboru odpowiedzi, to
przycisk przeczytaj ostatnie nie działa; zdarzyło się kilka razy w kilku
zakładkach".

MECHANIZM (zmierzony, nie zgadnięty): Claude Code 2.1.250 NIE zapisuje wypowiedzi
do dziennika, dopóki pytanie czeka na odpowiedź — cały blok (tekst ORAZ pytanie)
ląduje w pliku dopiero po kliknięciu. Dowód z żywego dziennika: wpisy ze
znacznikiem 08:27 trafiły do pliku po 09:00 (plik zamrożony 32 minuty, rozmiar
i mtime identyczne przy trzech kolejnych kliknięciach). Przez ten czas 🔊 widzi
STARĄ, krótką wypowiedź sprzed pytania, stan tury = „winien tekst" → czeka →
po 30 s uznaje „agent stanął" → MILCZY.

SKALA (dziennik diagnostyczny, 111 kliknięć jednego dnia):
  • 26 z 28 nieudanych kliknięć (93%) miało wiszące, nieodpowiedziane pytanie;
  • kontrola negatywna: tylko 5 z 83 udanych (6%).

⛔ To NIE jest regresja naprawy `621b977` — ona słusznie zabroniła czytania
STAREJ wypowiedzi po poddaniu się. Brakowało planu B: ekran.

⛔ SPROSTOWANIE TEZY Z KODU: komentarz w `main_window` twierdził (sonda PTY na
Claude Code 2.1.212), że „nowszy Claude Code zapisuje wypowiedź OD RAZU", więc
odraczanie przy pytaniu to przeszłość. Na 2.1.250 to JUŻ NIEPRAWDA.

NAPRAWA (wybór usera: czytać opcje + skrócić czekanie):
  1. gdy czekanie się poddaje → czytaj z EKRANU (tam tekst JEST, z opcjami);
  2. gdy dziennik zamarł >120 s przy turze „winnej tekst" → nie czekaj wcale;
  3. bufora ekranu NIE czyścimy (drugie kliknięcie pod rząd ma z czego czytać).

⛔ DLACZEGO KOTWICA, A NIE SAM `extract_last_claude_response`: on szuka RAMEK
okna (`╰`), a te bywają rozsypane przez kodowanie. Na PRAWDZIWYM zrzucie
z `crash-logs/` (fixture niżej) zwraca 0 znaków — czyli naprawa oparta na nim
milczałaby po cichu. Pilnuje tego asercja A3; gdyby kiedyś zaczął działać,
A3 zapali się i będzie to informacja, nie awaria.

SABOTAŻ — wyniki ZMIERZONE 2026-08-28 (uruchomione i wpisane PO fakcie; każdy
przebieg wykonał komplet 25 sprawdzeń, więc „0 padło” znaczyłoby „nie wykrywa”,
a nie „bramka się urwała”). Wszystkie 7 wariantów wykryte:
  1. poddanie się nie próbuje ekranu (brak planu B)  -> 2 padło (E1, E2)
  2. szybka ścieżka wyłączona                        -> 2 padło (D1, D7)
  3. próg zamrożenia 120 s -> 0 s (nadgorliwy)       -> 1 padło (D2)
  4. kotwica wyłączona (zostaje sam ekstraktor)      -> 7 padło (A1, A2, B1, B2, B5, E1, E2)
  5. bezpiecznik „ta sama wypowiedź” usunięty        -> 1 padło (C1)
  6. naprawa mojibake wyłączona                      -> 1 padło (B3)
  7. bufor ekranu znów czyszczony po czytaniu        -> 1 padło (B4)
Wariant 4 pada najszerzej i to jest wynik POŻĄDANY: pokazuje, że kotwica, a nie
ekstraktor ramek, dźwiga tę funkcję na prawdziwych danych.

⚠️ Sabotaż uruchamiaj z `python3 -B` i kasuj `__pycache__` (src, src/core, src/gui).
Bez tego warianty dające plik tej samej długości w tej samej sekundzie dostają
STARY bytecode i raportują cudzy wynik (zdarzyło się 2026-08-28 w bramce tabel).
"""
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

os.environ["QT_QPA_PLATFORM"] = "offscreen"
# ⚠️ Czujnik diagnostyczny 🔊 wyłączony ZANIM zaimportujemy okno: bramka wołająca
# produkcyjny `_read_last_debug` dopisywałaby ATRAPOWE wpisy do żywego
# `read-last-debug.log`, nieodróżnialne od pomiarów z prawdziwych kliknięć
# (zdarzyło się 2026-08-11). Tu i tak podstawiamy własny zbieracz.
os.environ.pop("CVA_READ_LAST_DEBUG", None)

from config import READ_LAST_BLOCKED_AGE_SECS  # noqa: E402
from core.text_cleaner import extract_last_claude_response  # noqa: E402
from core.transcript_reader import (  # noqa: E402
    TURN_IDLE,
    TURN_OWES_TEXT,
    TURN_TOOL_PENDING,
)
from gui.main_window import MainWindow  # noqa: E402

PASS = 0
FAIL = 0


def jest(nazwa, warunek, szczegol=""):
    global PASS, FAIL
    if warunek:
        PASS += 1
        print(f"[OK] {nazwa}")
    else:
        FAIL += 1
        print(f"[FAIL] {nazwa}")
        if szczegol:
            print(f"       {szczegol}")


EKRAN = (ROOT / "tools" / "fixtures" / "ekran-pytanie-2026-06-18.txt").read_text(encoding="utf-8")
# Ostatnia wypowiedź znana z dziennika — w tym zrzucie stoi PRZED pudełkiem pytania.
KOTWICA = "Bash(cd /tmp && nohuppython3/tmp/pw_verify.py>/tmp/pw_verify.log2>&1& echo"


class FakeTab:
    def __init__(self, bufor="", idle=1.0):
        self._terminal_output_buffer = bufor
        self._last_terminal_data_ts = time.monotonic() - idle
        self.pending_backlog = []


class FakeReader:
    def __init__(self, wiek=0.0, wybuch=False):
        self._wiek = wiek
        self._wybuch = wybuch

    def session_age_secs(self):
        if self._wybuch:
            raise RuntimeError("czytnik padl")
        return self._wiek


class FakeTts:
    def __init__(self):
        self.wypowiedziane = []

    def speak(self, text):
        self.wypowiedziane.append(text)


_METODY = ('_screen_tail_since', '_screen_source', '_speak_screen_text',
           '_journal_is_frozen', '_terminal_idle_secs', '_give_up_read_last_wait',
           '_cancel_read_last_wait', '_question_on_screen', '_check_read_last_wait',
           '_session_size')


class FakeWindow:
    """Atrapa okna z PRAWDZIWYMI metodami z produkcji."""

    def __init__(self):
        self.tts = FakeTts()
        self.current_language = 'pl-PL'
        self.statuses = []
        self.log = []
        self._tts_timer = None
        self._read_wait_timer = None
        self._read_wait_tab = None
        self._read_wait_started = time.monotonic()
        # `_bez_spacji` jest statyczna — wiązanie przez __get__ wpychałoby self
        # jako pierwszy argument. Bierzemy gołą funkcję.
        self._bez_spacji = MainWindow._bez_spacji
        self._refresh_screen = MainWindow._refresh_screen
        self._QUESTION_FOOTER_RE = MainWindow._QUESTION_FOOTER_RE
        self._QUESTION_FOOTER_LINES = MainWindow._QUESTION_FOOTER_LINES
        for m in _METODY:
            setattr(self, m, getattr(MainWindow, m).__get__(self))

    # własny zbieracz zamiast produkcyjnego zapisu do pliku
    def _read_last_debug(self, msg):
        self.log.append(msg)

    def _update_status(self, text):
        self.statuses.append(text)


print("=" * 78)
print("A. WYŁUSKANIE Z PRAWDZIWEGO ZRZUTU EKRANU Z PUDEŁKIEM WYBORU")
print("=" * 78)

w = FakeWindow()
tab = FakeTab(EKRAN)
ogon, metoda = w._screen_tail_since(tab, KOTWICA)

jest("A1 kotwica z dziennika odnaleziona w buforze ekranu",
     ogon is not None and metoda.startswith('kotwica'), f"metoda={metoda}")
plaski = re.sub(r"\s+", "", ogon or "")
jest("A2 w ogonie są OPCJE pytania (user chce je słyszeć)",
     all(p.replace(" ", "") in plaski for p in ["Do you want to proceed", "1. Yes", "3. No"]),
     repr((ogon or "")[:120]))
jest("A3 sam `extract_last_claude_response` na tym zrzucie zwraca PUSTO "
     "(dlatego kotwica jest nośna, nie ozdobna)",
     not (extract_last_claude_response(EKRAN) or "").strip(),
     "ekstraktor zaczął działać — sprawdź, czy kotwica nadal potrzebna")

print()
print("=" * 78)
print("B. CZYTANIE Z EKRANU")
print("=" * 78)

w = FakeWindow()
tab = FakeTab(EKRAN)
ok = w._speak_screen_text(tab, KOTWICA, 'test')
mowione = w.tts.wypowiedziane[0] if w.tts.wypowiedziane else ""

jest("B1 przeczytane (zwraca True i coś poszło do lektora)", ok and bool(mowione),
     f"log={w.log[-1] if w.log else ''}")
jest("B2 opcje wyboru dotarły do lektora",
     "1. Yes" in mowione and "3. No" in mowione, repr(mowione[-160:]))
jest("B3 mojibake naprawione — lektor nie dostaje ściany śmieci",
     "â" not in mowione and "Â" not in mowione,
     repr([c for c in mowione if c in "âÂ"][:5]))
jest("B4 bufor ekranu NIE wyczyszczony (drugie kliknięcie ma z czego czytać)",
     tab._terminal_output_buffer == EKRAN)

w2 = FakeWindow()
ok2 = w2._speak_screen_text(FakeTab(EKRAN), KOTWICA, 'test')
jest("B5 drugie kliknięcie pod rząd też czyta", ok2 and bool(w2.tts.wypowiedziane))

print()
print("=" * 78)
print("C. CZEGO CZYTAĆ NIE WOLNO (bezpieczniki)")
print("=" * 78)

w = FakeWindow()
stary = "To jest dokladnie ta sama wypowiedz, ktora lezy juz w dzienniku sesji i nic nowego nie wnosi."
jest("C1 ekran pokazuje TĘ SAMĄ wypowiedź co dziennik → NIE czytamy "
     "(to byłby powrót bugu „przeczytał przedostatnią”)",
     w._speak_screen_text(FakeTab(stary), stary, 'test') is False,
     f"log={w.log[-1] if w.log else ''}")

w = FakeWindow()
jest("C2 pusty bufor → NIE czytamy",
     w._speak_screen_text(FakeTab(""), KOTWICA, 'test') is False)

w = FakeWindow()
jest("C3 brak zakładki → NIE czytamy (i nic nie wybucha)",
     w._speak_screen_text(None, KOTWICA, 'test') is False)

w = FakeWindow()
jest("C4 sam szum bez treści → NIE czytamy",
     w._speak_screen_text(FakeTab("   \n\n  \n"), KOTWICA, 'test') is False)

print()
print("=" * 78)
print("D. DECYZJA: CZY DZIENNIK ZAMARŁ (szybka ścieżka — krok 2 usera)")
print("=" * 78)

w = FakeWindow()
jest(f"D1 tura winna tekst + dziennik zamrożony {READ_LAST_BLOCKED_AGE_SECS:.0f}s → nie czekaj",
     w._journal_is_frozen(FakeReader(wiek=300.0), TURN_OWES_TEXT) >= 0)
jest("D2 tura winna tekst, ale dziennik świeży (agent MYŚLI) → czekaj jak dotąd",
     w._journal_is_frozen(FakeReader(wiek=5.0), TURN_OWES_TEXT) < 0)
jest("D3 agent bezczynny → to nie ta sytuacja, choćby dziennik był stary",
     w._journal_is_frozen(FakeReader(wiek=9999.0), TURN_IDLE) < 0)
jest("D4 pracuje narzędzie → to nie ta sytuacja",
     w._journal_is_frozen(FakeReader(wiek=9999.0), TURN_TOOL_PENDING) < 0)
jest("D5 czytnik padł → nie zgadujemy, zachowujemy się jak dotąd",
     w._journal_is_frozen(FakeReader(wybuch=True), TURN_OWES_TEXT) < 0)
jest("D6 brak czytnika → jak dotąd",
     w._journal_is_frozen(None, TURN_OWES_TEXT) < 0)
jest("D7 próg dokładnie na granicy liczy się jako zamrożony",
     w._journal_is_frozen(FakeReader(wiek=READ_LAST_BLOCKED_AGE_SECS), TURN_OWES_TEXT) >= 0)

print()
print("=" * 78)
print("E. PODDANIE SIĘ CZEKANIA MA PLAN B (rdzeń naprawy)")
print("=" * 78)

w = FakeWindow()
tab = FakeTab(EKRAN)
w._read_wait_tab = tab
w._give_up_read_last_wait(KOTWICA, 'status_reading_wait_stalled', 'agent stanal bez pisania')
jest("E1 zamiast milczeć — czyta to, co na ekranie",
     bool(w.tts.wypowiedziane), f"log={w.log}")
jest("E2 ...i są tam opcje pytania",
     w.tts.wypowiedziane and "1. Yes" in w.tts.wypowiedziane[0])

w = FakeWindow()
w._read_wait_tab = FakeTab("")
w._give_up_read_last_wait("stara wypowiedz", 'status_reading_wait_stalled', 'test')
jest("E3 gdy ekran też nic nie ma → milczy jak dotąd i mówi o tym userowi "
     "(kontrola, że E1 nie zdaje przez przypadek)",
     not w.tts.wypowiedziane and w.statuses)

print()
print("=" * 78)
print("G. STOPKA PYTANIA NA EKRANIE = NIE CZEKAJ (2026-10-19)")
print("=" * 78)
# Siatka przepisana z PRAWDZIWEGO zrzutu usera (2026-10-19 15:26, zakładka CRM):
# dwie wypowiedzi PO ostatniej zapisanej w dzienniku + pytanie z polami wyboru.
# Dziennik stał 19 s, więc szybka ścieżka (120 s) nie miała prawa ruszyć.
KOTWICA_G = ("Klient dzisiaj (19.10) odpisał i podał dane osoby odpowiedzialnej "
             "za produkt w UE. Czytam cały mail.")
SIATKA_PYTANIE = """● Karta 681 jest, a klient 13.10 wypełnił formularz danych do umowy (zgłoszenie #125).

  Ran 5 shell commands

● Klient dzisiaj (19.10) odpisał i podał dane osoby odpowiedzialnej za produkt w UE.
  Czytam cały mail.

  Ran 4 shell commands

● Potwierdziłem w wykazie podatników, że firma ma status „czynny VAT”, a adres zgadza
  się z danymi od klienta. Teraz sprawdzę dostępne opcje odpowiedzi w formularzu.

  Ran 3 shell commands

● Z 38 wymaganych danych mam już 31, a brakujące uzupełnię z maila klienta i wzorca
  umowy — proszę o zgodę na zapis zmian w bazie produkcyjnej.
────────────────────────────────────────────────────────────────────────────────
 ←  ☐ GPSR kontakt  ☐ Zgoda  ✔ Submit  →

Telefon i e-mail firmy Neurobit (osoby odpowiedzialnej w UE) – co wpisać?

❯ 1. Zostaw widoczny brak (Recommended)
     Umowa pokaże „[DO UZUPEŁNIENIA]” w dwóch miejscach.
  2. Znam te dane – podam
  3. Przygotuj mail do klienta
  4. Type something.
────────────────────────────────────────────────────────────────────────────────
  5. Chat about this

Enter to select · Tab/Arrow keys to navigate · Esc to cancel

"""
# Wypowiedź, która stopkę CYTUJE (tak jak diagnoza tego błędu w zakładce VCA).
SIATKA_CYTAT = """● Pytanie z polami wyboru ma na dole stały napis
  „Enter to select · Tab/Arrow keys to navigate”. Proponuję, żeby program
  przy kliknięciu 🔊 najpierw sprawdzał, czy ten napis jest widoczny.

  Czy mogę to zrobić?

────────────────────────────────────────────────────────────────────────────────
❯ 
────────────────────────────────────────────────────────────────────────────────
  ⏵⏵ auto mode on (shift+tab to cycle)
"""


class FakeTabSiatka(FakeTab):
    """Zakładka z siatką xterma: `snapshot` oddaje ją tylko, gdy jest „świeża”."""

    def __init__(self, siatka, swieza=True, bufor="", idle=1.0):
        super().__init__(bufor, idle)
        self._siatka = siatka
        self._swieza = swieza
        self.odswiezen = 0

    def screen_text_snapshot(self, max_age_secs):
        return self._siatka if self._swieza else ""

    def refresh_screen_text_cache(self):
        self.odswiezen += 1


w = FakeWindow()
jest("G1 stopka pytania na dole świeżej siatki → wykryte",
     w._question_on_screen(FakeTabSiatka(SIATKA_PYTANIE)))
jest("G2 wypowiedź CYTUJĄCA stopkę w środku zdania → NIE pytanie "
     "(kontrola negatywna: inaczej 🔊 w zakładce z tą diagnozą czytałby ekran)",
     not w._question_on_screen(FakeTabSiatka(SIATKA_CYTAT)))
stara = SIATKA_PYTANIE + "\n".join(f"● wiersz po odpowiedzi {i}" for i in range(12))
jest("G3 stopka wyjechała w górę (pytanie już odpowiedziane) → NIE pytanie",
     not w._question_on_screen(FakeTabSiatka(stara)))
jest("G4 siatka nieświeża → „nie wiem” = False (zachowanie jak dotąd)",
     not w._question_on_screen(FakeTabSiatka(SIATKA_PYTANIE, swieza=False)))
jest("G5 zakładka bez siatki (stary silnik) → False, nic nie wybucha",
     not w._question_on_screen(FakeTab(SIATKA_PYTANIE)))
jest("G6 brak zakładki → False", not w._question_on_screen(None))


class FakeTurnReader:
    def __init__(self, last, stan):
        self._last, self._stan = last, stan

    def turn_snapshot(self):
        return self._last, self._stan

    def session_size(self):
        return 1000


class FakeTimer:
    def __init__(self):
        self.zatrzymany = False

    def stop(self):
        self.zatrzymany = True


def petla(siatka, swieza=True):
    """Jeden obrót PRAWDZIWEJ `_check_read_last_wait` przy czekaniu na odpowiedź."""
    w = FakeWindow()
    tab = FakeTabSiatka(siatka, swieza=swieza, idle=1.0)
    w._get_current_agent_tab = lambda: tab
    timer = FakeTimer()
    teraz = time.monotonic()
    w._read_wait_timer = timer
    w._read_wait_tab = tab
    w._read_wait_reader = FakeTurnReader(KOTWICA_G, TURN_OWES_TEXT)
    w._read_wait_before = KOTWICA_G
    w._read_wait_started = teraz
    w._read_wait_hard_deadline = teraz + 180
    w._read_wait_size = 1000
    w._read_wait_size_changed = teraz
    w._read_wait_tool_since = None
    w._check_read_last_wait()
    return w, tab, timer


w, tab, timer = petla(SIATKA_PYTANIE)
mowione = w.tts.wypowiedziane[0] if w.tts.wypowiedziane else ""
jest("G7 czekanie + pytanie na ekranie → czyta OD RAZU (pierwszy obrót pętli)",
     bool(mowione) and timer.zatrzymany, f"log={w.log}")
jest("G8 ...i czyta NOWE wypowiedzi spod kotwicy, nie starą z dziennika",
     "Z 38 wymaganych" in mowione and "Potwierdziłem" in mowione
     and "Czytam cały mail" not in mowione, repr(mowione[:160]))
jest("G9 ...a w logu stoi powód „pytanie na ekranie” (diagnoza po fakcie)",
     any("pytanie na ekranie" in l for l in w.log), f"log={w.log}")

w, tab, timer = petla(SIATKA_CYTAT)
jest("G10 agent MYŚLI (brak stopki pytania) → czeka dalej jak dotąd, nic nie czyta",
     not w.tts.wypowiedziane and not timer.zatrzymany, f"log={w.log}")
jest("G11 ...i w każdym obrocie prosi o świeżą siatkę (inaczej G7 nie zadziała na żywo)",
     tab.odswiezen >= 1)

w, tab, timer = petla(SIATKA_PYTANIE, swieza=False)
jest("G12 siatka nieświeża → czeka dalej (nie zgaduje po starym ekranie)",
     not w.tts.wypowiedziane and not timer.zatrzymany)

zrodlo_g = (ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
klik = zrodlo_g.split("def _read_last_response(self):")[1]
jest("G13 kliknięcie sprawdza stopkę PRZED szybką ścieżką 120 s",
     0 <= klik.find("_question_on_screen(tab)") < klik.find("_journal_is_frozen(reader"))
start = zrodlo_g.split("def _start_read_last_wait")[1].split("def ")[0]
jest("G14 start czekania prosi o świeżą siatkę", "_refresh_screen(tab)" in start)

print()
print("=" * 78)
print("F. STRUKTURA")
print("=" * 78)

zrodlo = (ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
jest("F1 bufor ekranu nie jest czyszczony po czytaniu w torze 🔊",
     "tab._terminal_output_buffer = \"\"" not in zrodlo.split("_speak_screen_text")[0],
     "wrócilo czyszczenie bufora — drugie kliknięcie przestanie działać")
jest("F2 obalona teza o Claude Code 2.1.212 jest w kodzie SPROSTOWANA",
     "SPROSTOWANIE 2026-08-28" in zrodlo,
     "komentarz znów twierdzi, że nowszy Claude zapisuje od razu")
jest("F3 próg zamrożenia jest w konfiguracji, nie wklepany w kod",
     "READ_LAST_BLOCKED_AGE_SECS" in zrodlo and str(int(READ_LAST_BLOCKED_AGE_SECS)) not in
     zrodlo.split("_journal_is_frozen")[1][:400])

print()
print("=" * 78)
print(f"PODSUMOWANIE: {PASS} OK, {FAIL} FAIL")
print("=" * 78)
sys.exit(1 if FAIL else 0)
