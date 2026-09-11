#!/usr/bin/env python3
"""Bramka POPRAWIANIA TRANSKRYPCJI + OCHRONY ZAZNACZENIA (2026-09-11).

POWOD POWSTANIA — zgloszenie wlasciciela: „dziurawe dyktowanie, tekst nie jest tym,
co dyktuje; w zakladce AI Manager musialem bardzo duzo naprawiac".

CO USTALIL POMIAR, ZANIM DOTKNIETO KODU (nie powtarzaj tych sond):
  · 328/328 nagran ma liczbe ramek zgodna z zegarem  → nagrywanie nic nie gubi
  · dlugosc odpowiedzi bramki == dlugosc wstawiona do pola → droga nic nie gubi
  · 325/325 dyktowan trafilo we wlasciwa zakladke
  · language=pl / prompt / temperature / ciche wzmocnienie mikrofonu → ZERO wplywu
    (kontrola: language=de zwrocil niemiecki, wiec parametry naprawde docieraja)
  · whisper-large-v3-turbo → GORSZY (95,2% wobec 97,4%)
  · poprawka tekstu po fakcie → 97,4% na wzorcu, na prawdziwym tekscie naprawila
    kazda→z ogonkiem, usun→z ogonkiem, daje→Daj i dostawila kropki miedzy zdaniami

CZEGO PILNUJE TA BRAMKA:
  A. poprawka NIE MA PRAWA NICZEGO ZGUBIC — przy kazdej watpliwosci tekst SUROWY
  B. co realnie wychodzi na siec (adres, model, polecenie, temperatura, klucz)
     — ta sekcja zamyka luke opisana w pamieci: ZADEN test nie sprawdzal dotad,
     jaki model wychodzi z dyktowania, wiec nic nie bronilo tej decyzji
  C. zdejmowanie ramki bloku kodu
  D. dziennik notuje kursor i zaznaczenie (bez tego „kto skasowal" jest nierozstrzygalne)
  E. dyktowanie NIE KASUJE zaznaczonego tekstu (z kontrola negatywna w Qt)
  F. wynik porzucony PO poprawce nie wpada do pola

⚠️ PULAPKI TEGO PLIKU (obie opisane w pamieci projektu, obie tu realne):
  1. HOME podmieniamy PRZED importem `config` — inaczej produkcyjny `dictation_log`
     pisze do PRAWDZIWEGO katalogu uzytkownika i zatruwa dziennik dowodowy.
  2. Tresc po polsku trzymamy w APOSTROFACH — polski cudzyslow zamykajacy jest
     zwyklym ASCII i urywa lancuch.

Uruchomienie:  python3 -B tools/test-dictation-fix.py

SABOTAZ — WYNIKI ZMIERZONE 2026-09-11 (uruchomione, NIE przewidziane).
Zdrowy kod: 30 wykonanych, 30 OK, 0 FAIL. Kazdy wariant w OSOBNYM wywolaniu,
przywrocenie dowiedzione sha256; po calej serii sumy plikow zgodne ze stanem sprzed.
⭐ Liczba WYKONANYCH sprawdzen = 30 przy KAZDYM wariancie — to jedyny dowod, ze
   bramka nie urywa sie w polowie (patrz S11 nizej).

  wariant | co popsute                                  | co padlo
  --------+---------------------------------------------+-----------
  S1      | zdjety przelacznik poprawki                 | A1
  S2      | poprawka wysylana bez klucza API            | A2
  S3      | zdjete widelki dlugosci                     | A6, A7
  S4      | zdjete sprawdzanie kodu odpowiedzi          | A4
  S5      | model wpisany na sztywno zamiast z config   | B2
  S6      | zdjeta temperatura 0                        | B5
  S7      | pelny klucz API leci do dziennika           | B9, D2
  S8      | zdjeta druga kontrola porzucenia            | F1
  S9      | zdjeta linia zwijajaca zaznaczenie          | E1
  S10     | zdjety pomiar kursora i zaznaczenia         | D1
  S11     | ochrona omijana `if False`, linia ZOSTAJE   | E2

⛔ CZEGO NAUCZYL SABOTAZ O TEJ BRAMCE — dwie realne dziury, obie naprawione:
  1. A4 pierwotnie PRZECHODZILO po usunieciu sprawdzania kodu odpowiedzi, bo atrapa
     bledu nie niosla tresci: pusta odpowiedz i tak wracala tekstem surowym. Asercja
     wygladala na sensowna i nie rozrozniala NICZEGO. Atrapa musi niesc tresc, ktora
     zostalaby BLEDNIE przyjeta.
  2. S11 nie zglosil porazki, tylko WYWALIL bramke po 25 z 30 sprawdzen — bo E2
     robilo gole `.index()` na napisie, ktory ten sabotaz usuwa. Wyjscie po
     odfiltrowaniu wygladalo wtedy jak komplet zielonych. Stad oslona i porownywanie
     liczby WYKONANYCH sprawdzen miedzy przebiegiem zdrowym a zepsutym.

⚠️ CZEGO TA BRAMKA NIE SPRAWDZA (zapisane swiadomie, zeby nikt na to nie liczyl):
  · E1/E2 pytaja ZRODLO, nie zachowanie `_on_transcription` — pelny test wymagalby
    postawienia calego MainWindow. Obejscie sprytniejsze niz S11 (np. dopisanie
    `and False` do warunku) przeszloby niezauwazone. Zachowanie samego mechanizmu
    Qt jest za to udowodnione NAPRAWDE, z kontrola negatywna (E3/E4).
  · jakosci polszczyzny po poprawce nie ocenia zaden automat — to potwierdza czlowiek.
"""
import os, sys, tempfile, pathlib, json

# ⛔ KOLEJNOSC MA ZNACZENIE: sciezki licza sie w chwili importu `config`.
_DOM = tempfile.mkdtemp(prefix='bramka-dyktowanie-')
os.environ['HOME'] = _DOM
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

KORZEN = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORZEN / 'src'))

import config
import core.stt_engine as silnik
from core.stt_engine import STTEngine, _zdejmij_ramke_kodu

OK = FAIL = 0
def sprawdz(nazwa, warunek, szczegol=''):
    global OK, FAIL
    if warunek:
        OK += 1; print(f'[OK] {nazwa}')
    else:
        FAIL += 1; print(f'[FAIL] {nazwa}' + (f'  -> {szczegol}' if szczegol else ''))

# Kontrola przytomnosci: czy na pewno piszemy do ATRAPY HOME, nie do prawdziwego?
sprawdz('H0 dziennik dyktowania celuje w atrape HOME, nie w katalog uzytkownika',
        str(config.DICTATION_LOG).startswith(_DOM),
        f'DICTATION_LOG={config.DICTATION_LOG}')

KLUCZ_TESTOWY = 'aim-KLUCZ-ATRAPA-NIGDY-PRAWDZIWY'
SUROWY = 'Prosze usun kruc API z wykresu, bo powinien byc w integracji.'
POPRAWNY = 'Prosze usun klucz API z wykresu, bo powinien byc w integracji.'

class OdpowiedzAtrapa:
    def __init__(self, kod=200, tresc=None, psuj=False):
        self.status_code = kod; self._tresc = tresc; self._psuj = psuj
        self.text = ''
    def json(self):
        if self._psuj: raise ValueError('nie JSON')
        return {'choices': [{'message': {'content': self._tresc}}]}

def silnik_z(odpowiedz=None, wyjatek=None, wlaczona=True, klucz=KLUCZ_TESTOWY):
    s = STTEngine(api_key=klucz)
    s.set_fix_enabled(wlaczona)
    zapis = {}
    def atrapa_post(url, **kw):
        zapis['url'] = url; zapis['kw'] = kw
        if wyjatek: raise wyjatek
        return odpowiedz
    silnik.requests = type('R', (), {
        'post': staticmethod(atrapa_post),
        'exceptions': silnik.requests.exceptions})
    return s, zapis

PRAWDZIWE_REQUESTS = silnik.requests

# ── A. BEZPIECZNIKI: przy kazdej watpliwosci TEKST SUROWY ────────────────────
s, _ = silnik_z(OdpowiedzAtrapa(200, POPRAWNY), wlaczona=False)
sprawdz('A1 wylaczona poprawka -> tekst surowy', s._popraw_transkrypcje(SUROWY) == SUROWY)

s, _ = silnik_z(OdpowiedzAtrapa(200, POPRAWNY), klucz='')
sprawdz('A2 brak klucza -> tekst surowy', s._popraw_transkrypcje(SUROWY) == SUROWY)

s, _ = silnik_z(wyjatek=PRAWDZIWE_REQUESTS.exceptions.ConnectionError('brak sieci'))
sprawdz('A3 awaria sieci -> tekst surowy', s._popraw_transkrypcje(SUROWY) == SUROWY)

s, _ = silnik_z(OdpowiedzAtrapa(503, POPRAWNY))
sprawdz('A4 kod 503 (z trescia!) -> tekst surowy', s._popraw_transkrypcje(SUROWY) == SUROWY)

s, _ = silnik_z(OdpowiedzAtrapa(200, '   '))
sprawdz('A5 pusta odpowiedz -> tekst surowy', s._popraw_transkrypcje(SUROWY) == SUROWY)

s, _ = silnik_z(OdpowiedzAtrapa(200, SUROWY + ' A oto moj komentarz. ' * 20))
sprawdz('A6 odpowiedz ZA DLUGA (model dopisal) -> tekst surowy',
        s._popraw_transkrypcje(SUROWY) == SUROWY)

s, _ = silnik_z(OdpowiedzAtrapa(200, 'Klucz API.'))
sprawdz('A7 odpowiedz ZA KROTKA (model strescil) -> tekst surowy',
        s._popraw_transkrypcje(SUROWY) == SUROWY)

s, _ = silnik_z(OdpowiedzAtrapa(200, None, psuj=True))
sprawdz('A8 zla struktura odpowiedzi -> tekst surowy', s._popraw_transkrypcje(SUROWY) == SUROWY)

dlugi = 'a' * (config.STT_FIX_MAX_CHARS + 1)
s, zapis = silnik_z(OdpowiedzAtrapa(200, POPRAWNY))
sprawdz('A9 tekst dluzszy niz limit -> pomijamy, tekst surowy i ZERO wyslania',
        s._popraw_transkrypcje(dlugi) == dlugi and 'url' not in zapis)

s, _ = silnik_z(OdpowiedzAtrapa(200, POPRAWNY))
sprawdz('A10 poprawna odpowiedz -> tekst POPRAWIONY', s._popraw_transkrypcje(SUROWY) == POPRAWNY)

# ── B. CO REALNIE WYCHODZI NA SIEC ───────────────────────────────────────────
s, zapis = silnik_z(OdpowiedzAtrapa(200, POPRAWNY))
s._popraw_transkrypcje(SUROWY)
cialo = zapis.get('kw', {}).get('json', {})
naglowki = zapis.get('kw', {}).get('headers', {})
sprawdz('B1 adres = STT_FIX_API_URL z config', zapis.get('url') == config.STT_FIX_API_URL,
        str(zapis.get('url')))
sprawdz('B2 model = STT_FIX_MODEL z config (jedno zrodlo prawdy)',
        cialo.get('model') == config.STT_FIX_MODEL, str(cialo.get('model')))
sprawdz('B3 polecenie systemowe faktycznie wysylane',
        any(w.get('role') == 'system' and config.STT_FIX_PROMPT in w.get('content', '')
            for w in cialo.get('messages', [])))
sprawdz('B4 dyktowany tekst wysylany jako wiadomosc uzytkownika',
        any(w.get('role') == 'user' and w.get('content') == SUROWY
            for w in cialo.get('messages', [])))
sprawdz('B5 temperatura 0 (bez fantazjowania)', cialo.get('temperature') == 0)
sprawdz('B6 klucz w naglowku Authorization',
        naglowki.get('Authorization') == f'Bearer {KLUCZ_TESTOWY}')
sprawdz('B7 limit czasu ustawiony i NIE dluzszy niz wysylka nagrania',
        zapis['kw'].get('timeout') == (config.STT_FIX_HTTP_TIMEOUT, config.STT_FIX_HTTP_TIMEOUT)
        and config.STT_FIX_HTTP_TIMEOUT <= config.STT_HTTP_TIMEOUT)

dziennik = config.DICTATION_LOG.read_text(encoding='utf-8') if config.DICTATION_LOG.exists() else ''
sprawdz('B8 sonda przytomnosci: dziennik W OGOLE cokolwiek zapisal',
        'POPRAWKA' in dziennik, 'bez tego B9 bylby zielony z pustego powodu')
sprawdz('B9 klucz API NIE wyciekl do dziennika', KLUCZ_TESTOWY not in dziennik)

# ── C. RAMKA BLOKU KODU ──────────────────────────────────────────────────────
sprawdz('C1 owinieta odpowiedz -> ramka zdjeta',
        _zdejmij_ramke_kodu('```\n' + POPRAWNY + '\n```') == POPRAWNY)
sprawdz('C2 zwykly tekst nietkniety', _zdejmij_ramke_kodu(POPRAWNY) == POPRAWNY)

# ── D. DZIENNIK NOTUJE KURSOR I ZAZNACZENIE (krok A) ─────────────────────────
zrodlo_okna = (KORZEN / 'src' / 'gui' / 'main_window.py').read_text(encoding='utf-8')
sprawdz('D1 dziennik notuje dlugosc pola, kursor i zaznaczenie',
        'pole: znakow=' in zrodlo_okna and 'kursor=' in zrodlo_okna
        and 'zaznaczone=' in zrodlo_okna)
sprawdz('D2 poprawka raportuje dlugosci przed i po',
        'POPRAWKA: {len(surowy)}->{len(poprawiony)}' in
        (KORZEN / 'src' / 'core' / 'stt_engine.py').read_text(encoding='utf-8'))

# ── E. OCHRONA ZAZNACZENIA (krok B) ──────────────────────────────────────────
sprawdz('E1 produkcja ZWIJA zaznaczenie przed wstawieniem',
        'cursor.setPosition(cursor.selectionEnd())' in zrodlo_okna)
# ⛔ OSLONA OBOWIAZKOWA: przy sabotazu S11 pytanie o zaznaczenie ZNIKA ze zrodla,
# a goly `.index()` wywalal wtedy CALA bramke po 25 z 30 sprawdzen — wyjscie po
# odfiltrowaniu wygladalo identycznie jak komplet zielonych. Liczba WYKONANYCH
# sprawdzen musi byc taka sama na kodzie zdrowym i zepsutym.
_pyta = 'cursor.hasSelection()' in zrodlo_okna
_wstawia = 'cursor.insertText(insert_text)' in zrodlo_okna
sprawdz('E2 produkcja pyta o zaznaczenie ZANIM wstawi tekst',
        _pyta and _wstawia
        and zrodlo_okna.index('cursor.hasSelection()')
            < zrodlo_okna.index('cursor.insertText(insert_text)'),
        f'pyta_o_zaznaczenie={_pyta} wstawia={_wstawia}')

from PyQt5.QtWidgets import QApplication, QTextEdit
_app = QApplication.instance() or QApplication([])

def proba_wstawienia(zwijaj):
    pole = QTextEdit(); pole.setPlainText('POCZATEK ZAZNACZONE KONIEC')
    k = pole.textCursor()
    k.setPosition(9); k.setPosition(19, k.KeepAnchor)   # zaznacz 'ZAZNACZONE'
    if zwijaj:
        k.setPosition(k.selectionEnd())
    k.insertText(' DYKTOWANE ')
    return pole.toPlainText()

bez_ochrony = proba_wstawienia(False)
z_ochrona = proba_wstawienia(True)
sprawdz('E3 KONTROLA NEGATYWNA: bez zwijania zaznaczony tekst GINIE',
        'ZAZNACZONE' not in bez_ochrony,
        'jesli to padlo, mechanizm nie istnieje i E4 nic nie dowodzi')
sprawdz('E4 ze zwijaniem zaznaczony tekst PRZEZYWA',
        'ZAZNACZONE' in z_ochrona and 'DYKTOWANE' in z_ochrona, z_ochrona)

# ── F. PORZUCENIE PO POPRAWCE ────────────────────────────────────────────────
zrodlo_stt = (KORZEN / 'src' / 'core' / 'stt_engine.py').read_text(encoding='utf-8')
sprawdz('F1 po poprawce sprawdzamy PONOWNIE, czy podejscie nadal aktualne',
        'WYNIK PORZUCONY PO POPRAWCE' in zrodlo_stt)
sprawdz('F2 poprawka wolana PRZED oddaniem tekstu do pola',
        zrodlo_stt.index('_popraw_transkrypcje(text)') < zrodlo_stt.index('self.on_transcription(text)'))

print(f'\nWYKONANYCH SPRAWDZEN: {OK + FAIL}   OK: {OK}   FAIL: {FAIL}')
sys.exit(1 if FAIL else 0)
