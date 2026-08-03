#!/usr/bin/env python3
"""Test wyszukiwarki rozmowy (🔍) — logika, odczyt dziennika i okno.

Funkcja szuka w DZIENNIKU SESJI (cała rozmowa, czysty tekst), nie w buforze
ekranu — bufor ma cap 5000 znaków, znaki sterujące i RÓŻNI SIĘ między silnikami
terminala. Testujemy więc: dopasowanie (bez ogonków/wielkości liter), wyciąganie
rozmowy z prawdziwego dziennika oraz to, że okno naprawdę się buduje.

Każdy blok ma kontrolę negatywną — inaczej komplet zielonych niczego nie dowodzi.

WYNIKI SABOTAŻU (2026-08-03) — ZMIERZONE, nie przewidziane. Psułem po jednej
rzeczy w `search_dialog.py` i notowałem, co realnie padło:

  1. pozycja pythonowa wprost do Qt (stary błąd emoji)  → 2 testy padły
     („podświetlone DOKŁADNIE szukane słowo" pokazało ' (lu')
  2. usunięte `setCurrentCharFormat(...)` (oba)          → ⚠️ NIC NIE PADŁO
     Bo bleedowi zapobiega już ZWINIĘCIE kursora (przejmuje format znaku sprzed
     trafienia). Zerowania są DRUGĄ LINIĄ OBRONY i żaden test ich nie pilnuje —
     nie usuwaj ich jako „martwy kod", ale i nie licz, że są przetestowane.
  3. zaznaczenie zostawione (bez zwinięcia)              → 4 testy padły
     Ujawniło niespodziankę: `setCurrentCharFormat` przy AKTYWNYM zaznaczeniu
     nadaje format zaznaczeniu, więc podświetlenie robi się PUSTE (nie niebieskie).
  4. zawsze forma mnoga („1 razy")                       → 1 test padł
  5. lista bez zawijania + stare proporcje 3:2           → 2 testy padły

Uruchomienie:  python3 tools/test-conversation-search.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from core.conversation_search import fold, find_hits, summarize, Hit  # noqa: E402
from core.transcript_reader import TranscriptReader  # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[OK]   {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}")


# ============================================================================
# 1. Składanie znaków: bez ogonków, bez wielkości liter — ale DŁUGOŚĆ ta sama
# ============================================================================
# Długość jest warunkiem poprawności pozycji trafienia: gdyby złożenie skracało
# tekst, podświetlenie wskazywałoby inne miejsce niż faktyczne dopasowanie.
for src in ["żółw", "Zażółć gęślą jaźń", "ŁÓDŹ", "Straße", "emoji ⏳ tu", ""]:
    check(f"złożenie zachowuje długość: {src!r}", len(fold(src)) == len(src),
          f"{len(fold(src))} != {len(src)}")
check("ł jest składane na l (NFKD samo tego NIE robi — zjadłoby literę)",
      fold("Łódź działa") == "lodz dziala", fold("Łódź działa"))
check("kontrola negatywna: różne słowa nie stają się sobą",
      fold("kot") != fold("kod"))

# ============================================================================
# 2. Szukanie w rozmowie
# ============================================================================
ROZMOWA = [
    {"role": "user", "time": "10:00", "text": "Sprawdź proszę żółty raport i wyślij go do księgowej."},
    {"role": "assistant", "time": "10:01", "text": "Raport ZOLTY gotowy, wysłany o 10:30 (netto)."},
    {"role": "assistant", "time": "10:05", "text": "Nic tu nie ma na ten temat."},
    {"role": "user", "time": "10:07", "text": "Dzięki. Raport raport raport."},
]

hits = find_hits(ROZMOWA, "zolty")
check("szukanie BEZ ogonków znajduje wersję z ogonkami i wielkimi literami",
      len(hits) == 2, f"trafień: {len(hits)}")
check("trafienie wskazuje DOKŁADNE miejsce w oryginale",
      all(fold(h.matched_text()) == "zolty" for h in hits),
      [h.matched_text() for h in hits])

hits = find_hits(ROZMOWA, "raport")
check("liczy KAŻDE wystąpienie, także kilka w jednej wypowiedzi",
      len(hits) == 5, f"trafień: {len(hits)}")
s = summarize(hits)
check("podsumowanie rozróżnia liczbę trafień i liczbę wypowiedzi",
      s == {'hits': 5, 'entries': 3}, s)

check("kontrola negatywna: fraza, której nie ma, daje zero",
      find_hits(ROZMOWA, "hipopotam") == [])
check("puste zapytanie NIE zwraca całej rozmowy",
      find_hits(ROZMOWA, "") == [] and find_hits(ROZMOWA, "   ") == [])
check("liczby i dwukropki działają (godzina jako fraza)",
      len(find_hits(ROZMOWA, "10:30")) == 1)

only_user = find_hits(ROZMOWA, "raport", roles={'user'})
only_bot = find_hits(ROZMOWA, "raport", roles={'assistant'})
check("da się zawęzić do jednej strony rozmowy",
      len(only_user) == 4 and len(only_bot) == 1,
      f"user={len(only_user)} agent={len(only_bot)}")
check("limit chroni przed zalewem wyników",
      len(find_hits(ROZMOWA, "a", limit=3)) == 3)

# Kontekst wokół trafienia
h = find_hits(ROZMOWA, "żółty")[0]
snip = h.snippet(10)
check("fragment kontekstu zawiera trafienie i jest jednolinijkowy",
      "żółty" in snip and "\n" not in snip, snip)

# ============================================================================
# 3. Odczyt rozmowy z PRAWDZIWEGO dziennika (fixture zdjęty z sesji CRM)
# ============================================================================
FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fixtures', 'crm-turn-states.jsonl')


class FileReader(TranscriptReader):
    """Czytnik wpięty w konkretny plik (bez katalogu ~/.claude/projects)."""

    def __init__(self, path):
        self._projects_base = None
        self._project_dir = None
        self._session_file = path
        self._offset = 0
        self._pinned_session_id = None
        self._api_errors = []
        self._wait_last_size = -1
        self._wait_stable = 0

    def _ensure_session(self):
        return


if not os.path.exists(FIXTURE):
    check("fixture z prawdziwego dziennika istnieje", False, FIXTURE)
else:
    entries = FileReader(FIXTURE).conversation_entries()
    check("z dziennika wychodzą wypowiedzi rozmowy", len(entries) >= 2, f"{len(entries)}")
    check("każdy wpis ma rolę, godzinę i treść",
          all(e.get('role') in ('user', 'assistant') and 'time' in e and e.get('text')
              for e in entries))
    check("godzina jest LOKALNA, nie UTC z pliku (pułapka z 2026-07-25)",
          all(len(e['time']) == 5 and e['time'][2] == ':' for e in entries if e['time']),
          [e['time'] for e in entries])
    joined = " ".join(e['text'] for e in entries)
    check("myślenie agenta NIE trafia do rozmowy", "(przyciete)" not in joined)
    check("wypowiedź pod-agenta (isSidechain) NIE trafia do rozmowy",
          "POD-AGENT" not in joined, joined[:80])
    check("kontrola negatywna: prawdziwa treść JEST obecna",
          "Stan potwierdzony" in joined or "Świetnie" in joined, joined[:80])

    # szukanie na prawdziwych danych, bez ogonków
    found = find_hits(entries, "swietnie")
    check("na prawdziwych danych szukanie bez ogonków też działa",
          len(found) >= 1, f"trafień: {len(found)}")

# ============================================================================
# 4. Okno szukania — czy się BUDUJE i czy etykiety mają jawny kolor
# ============================================================================
# py_compile nie wykonuje kodu okna, a literówka w nazwie klucza i18n albo
# w atrybucie wybucha dopiero przy otwarciu u użytkownika.
from PyQt5.QtWidgets import QApplication, QLabel  # noqa: E402

_app = QApplication.instance() or QApplication(sys.argv)


class FakeReader:
    def __init__(self, entries):
        self._entries = entries

    def conversation_entries(self):
        return self._entries


from gui.search_dialog import SearchDialog  # noqa: E402

dlg = SearchDialog("Testowy agent", FakeReader(ROZMOWA))
check("okno szukania buduje się bez błędu", dlg is not None)

# Reguła strukturalna: KAŻDA etykieta ma jawny `color:` — inaczej Qt bierze
# barwę z palety i w ciemnym motywie wychodzi czarny tekst na czarnym tle
# (zgłoszone przez usera przy oknie „Chmura").
bez_koloru = [w.text() or w.objectName() or '(pusta)'
              for w in dlg.findChildren(QLabel) if 'color:' not in w.styleSheet()]
check("każda etykieta ma jawny kolor", not bez_koloru, bez_koloru)

# Kontrola negatywna reguły wyżej: dołożona etykieta BEZ koloru musi zostać wykryta.
_probe = QLabel("bez koloru", dlg)
bez_koloru2 = [w for w in dlg.findChildren(QLabel) if 'color:' not in w.styleSheet()]
check("kontrola negatywna: test wykrywa etykietę bez koloru", len(bez_koloru2) == 1)
_probe.setParent(None)

# Zachowanie okna: wpisanie frazy wypełnia listę, brak frazy — czyści.
dlg.field.setText("raport")
dlg._run_search()
check("wpisanie frazy wypełnia listę wyników", dlg.results.count() == 5,
      f"pozycji: {dlg.results.count()}")
check("pierwszy wynik zaznacza się sam", dlg.results.currentRow() == 0)
check("podgląd pokazuje pełną wypowiedź",
      "raport" in dlg.preview.toPlainText().lower(), dlg.preview.toPlainText()[:60])
check("licznik mówi o trafieniach i wypowiedziach",
      "5" in dlg.status.text() and "3" in dlg.status.text(), dlg.status.text())

dlg.go_next()
check("strzałka w dół przechodzi do następnego trafienia", dlg.results.currentRow() == 1)
dlg.go_prev()
check("strzałka w górę wraca", dlg.results.currentRow() == 0)

dlg.field.setText("hipopotam")
dlg._run_search()
check("brak trafień → pusta lista i czytelny komunikat",
      dlg.results.count() == 0 and dlg.status.text() != "", dlg.status.text())
check("przyciski akcji są wtedy wyłączone (nie ma czego kopiować)",
      not dlg.copy_btn.isEnabled() and not dlg.read_btn.isEnabled())

# Sygnał czytania niesie PEŁNĄ wypowiedź (nie sam urywek z listy).
dlg.field.setText("żółty")
dlg._run_search()
spoken = []
dlg.request_speak.connect(spoken.append)
dlg._speak_current()
check("przycisk Przeczytaj wysyła pełną wypowiedź, nie skrót",
      len(spoken) == 1 and spoken[0] == ROZMOWA[0]['text'], spoken)

# Informacja zwrotna o przewijaniu terminala
dlg.report_scroll(True)
tekst_ok = dlg.hint.text()
dlg.report_scroll(False)
check("okno rozróżnia komunikaty: przewinięto vs nie ma w oknie",
      tekst_ok and dlg.hint.text() and tekst_ok != dlg.hint.text(),
      f"{tekst_ok!r} / {dlg.hint.text()!r}")

dlg.deleteLater()

# ============================================================================
# 5. Przycisk lupy w zakładce — realne wpięcie (py_compile tego nie sprawdzi)
# ============================================================================
from gui.agent_tab import AgentTab  # noqa: E402

_tab = AgentTab({'id': 'test', 'name': 'Testowy', 'model': 'opus',
                 'working_directory': os.path.expanduser('~')})
check("zakładka ma przycisk lupy", hasattr(_tab, 'search_btn'))
check("lupa ma ikonę (SVG się wczytał, nie pusty kwadrat)",
      not _tab.search_btn.icon().isNull())
check("lupa ma podpowiedź ze skrótem",
      'Ctrl+F' in _tab.search_btn.toolTip(), _tab.search_btn.toolTip())
_klik = []
_tab.request_search.connect(lambda: _klik.append(1))
_tab.search_btn.click()
check("klik w lupę prosi okno główne o otwarcie szukania", _klik == [1])
_tab.deleteLater()

# ============================================================================
# 6. Parytet tłumaczeń dla nowych napisów
# ============================================================================
import config  # noqa: E402

klucze = ['search_tooltip', 'search_title', 'search_placeholder', 'search_prev',
          'search_next', 'search_copy', 'search_read', 'search_close',
          'search_count', 'search_none', 'search_empty_journal',
          'search_role_user', 'search_role_assistant', 'search_copied',
          'search_scrolled', 'search_not_on_screen',
          'search_word_hit_one', 'search_word_hit_many',
          'search_word_entry_one', 'search_word_entry_many']
for lang, slownik in config.UI_TRANSLATIONS.items():
    brakuje = [k for k in klucze if k not in slownik]
    check(f"komplet napisów wyszukiwarki w {lang}", not brakuje, brakuje)
zestawy = [set(v) for v in config.UI_TRANSLATIONS.values()]
check("słowniki nadal mają komplet tych samych kluczy",
      all(z == zestawy[0] for z in zestawy))
import re  # noqa: E402
pola = {lang: sorted(re.findall(r'{(\w+)}', s['search_count']))
        for lang, s in config.UI_TRANSLATIONS.items()}
check("pola do podstawienia zgodne w obu językach",
      len(set(map(tuple, pola.values()))) == 1, pola)

# ============================================================================
# 7. Podświetlenie trafienia w podglądzie (zgłoszenie usera 2026-08-03)
#
# Trzy usterki zmierzone na PRAWDZIWEJ wypowiedzi z dziennika:
#   (a) pozycja pythonowa podana Qt → podświetlenie przesunięte w lewo o tyle
#       znaków, ile emoji spoza BMP stało wcześniej (5 emoji → „wie " zamiast
#       „lupa"). ⚠️ Wszystkie testy z bloków 1–6 przechodziły MIMO tego błędu,
#       bo liczą po stronie Pythona — dlatego ten blok patrzy na WIDŻET.
#   (b) `setPlainText` dziedziczy bieżący format znaku → od 2. szukania cała
#       wypowiedź malowała się akcentem.
#   (c) zostawione zaznaczenie przykrywało kolor skórki systemowym niebieskim.
# ============================================================================
from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtGui import QColor, QTextCursor  # noqa: E402
from core.conversation_search import utf16_offset  # noqa: E402
from gui.search_dialog import SearchDialog  # noqa: E402
from gui import theme  # noqa: E402

# --- (a1) sam przelicznik pozycji, bez okien ---
check("bez emoji pozycja się nie zmienia", utf16_offset("abcdef", 3) == 3)
check("emoji przed trafieniem przesuwa pozycję o 1",
      utf16_offset("\U0001F916abc", 1) == 2, utf16_offset("\U0001F916abc", 1))
check("pięć emoji przesuwa o 5",
      utf16_offset("\U0001F916" * 5 + "lupa", 5) == 10)
check("polskie ogonki NIE przesuwają (są w BMP)", utf16_offset("żółw", 4) == 4)
check("początek tekstu zawsze 0", utf16_offset("\U0001F916x", 0) == 0)
# kontrola negatywna: gdyby funkcja tylko przepisywała indeks, powyższe by padło
check("kontrola negatywna: przelicznik NIE jest tożsamością",
      utf16_offset("\U0001F916abc", 3) != 3)

# --- (a2..c) zachowanie WIDŻETU na wypowiedzi z emoji ---
WIADOMOSC = (
    "| \U0001F916 Domyslny (Opus 5) na pasku | 7c3e264 |\n"
    "| \U0001F50D Szukanie w rozmowie (lupa / Ctrl+F) | 2026-07-25 |\n"
    "| ✅ Katalog modeli | 2026-07-26 |\n"
)


class _Reader:
    def conversation_entries(self):
        return [{"role": "assistant", "time": "09:22", "text": WIADOMOSC}]


def podswietlony_tekst(dialog):
    """Który fragment NAPRAWDĘ ma tło akcentu (czyta format z dokumentu)."""
    doc = dialog.preview.document()
    kolor = QColor(theme.ACCENT)
    kursor = QTextCursor(doc)
    zebrane = []
    for poz in range(1, doc.characterCount()):
        kursor.setPosition(poz)
        if kursor.charFormat().background().color() == kolor:
            zebrane.append(doc.characterAt(poz - 1))
    return ''.join(zebrane)


_dlg = SearchDialog("Test", _Reader())
_dlg.field.setText("lupa")
_dlg._run_search()
check("podświetlone jest DOKŁADNIE szukane słowo, mimo emoji wcześniej",
      podswietlony_tekst(_dlg) == "lupa", repr(podswietlony_tekst(_dlg)))
check("kontrola negatywna: podświetlenie nie jest puste",
      podswietlony_tekst(_dlg) != "")

# powtórne szukania — tu wcześniej cała wypowiedź robiła się fioletowa
for _ in range(3):
    _dlg.field.setText("lupa")
    _dlg._run_search()
_po_powtorce = podswietlony_tekst(_dlg)
check("po kilku szukaniach akcent NADAL obejmuje tylko trafienie",
      _po_powtorce == "lupa", repr(_po_powtorce[:60]))
check("kontrola negatywna: akcent nie rozlał się na całą wypowiedź",
      len(_po_powtorce) < len(WIADOMOSC) / 2, len(_po_powtorce))

# zaznaczenie zwinięte → widać kolor skórki, nie systemowy niebieski
check("po pokazaniu trafienia nie zostaje zaznaczenie",
      _dlg.preview.textCursor().selectedText() == "",
      repr(_dlg.preview.textCursor().selectedText()))

# --- odmiana liczby trafień ---
_dlg.field.setText("lupa")
_dlg._run_search()
check("dla jednego trafienia piszemy „1 raz w 1 wypowiedzi”",
      _dlg.status.text() == "Znaleziono 1 raz w 1 wypowiedzi", _dlg.status.text())
_dlg.field.setText("modeli")
_dlg._run_search()
_dlg.field.setText("|")
_dlg._run_search()
check("dla wielu trafień forma mnoga („razy”)",
      " razy " in _dlg.status.text(), _dlg.status.text())
check("kontrola negatywna: przy wielu trafieniach NIE ma formy pojedynczej",
      " 1 raz " not in _dlg.status.text(), _dlg.status.text())
_dlg.deleteLater()

# --- układ okna: lista nie ma poziomego suwaka, podgląd nie jest mniejszy ---
_dlg2 = SearchDialog("Test", _Reader())
check("lista wyników zawija tekst zamiast przewijać w bok",
      _dlg2.results.wordWrap() and
      _dlg2.results.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff)
_layout = _dlg2.layout()
_i_lista = _layout.indexOf(_dlg2.results)
_i_podglad = _layout.indexOf(_dlg2.preview)
check("podgląd dostaje nie mniej miejsca niż lista",
      _layout.stretch(_i_podglad) >= _layout.stretch(_i_lista),
      (_layout.stretch(_i_lista), _layout.stretch(_i_podglad)))
_dlg2.deleteLater()

print(f"\nWynik: {PASS} OK / {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
