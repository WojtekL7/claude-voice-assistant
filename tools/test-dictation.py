#!/usr/bin/env python3
"""Bramka dyktowania (STT) — pilnuje czterech rzeczy, których brak zgłosił user 2026-08-29:
"dyktuję, a tekst nie wchodzi w pole poleceń; ikona mikrofonu nawet nie pulsowała".

CO SIĘ WTEDY STAŁO (ustalone pomiarem, nie domysłem):
  - mikrofon, bramka rozpoznawania i klucz DZIAŁAŁY (sprawdzone osobno),
  - apka wisiała w stanie 'przetwarzam', bo wysyłka nie wróciła (zerwany DNS
    obchodzi limit `requests`),
  - w tym stanie `start_recording()` wychodził po cichu → każde kolejne kliknięcie
    ginęło bez śladu i bez komunikatu,
  - a jedyny komunikat o błędzie był nadpisywany słowem 'Gotowy' w tej samej
    milisekundzie, więc NIGDY nie dotarł do użytkownika,
  - dyktowanie nie pisało do ŻADNEGO pliku, więc nie było czego czytać.

⚠️ DWIE PUŁAPKI TEGO PLIKU, obie zaliczone przy pisaniu:
  1. Polski cudzysłów otwierający domknięty ASCII-owym " URYWA łańcuch w Pythonie.
     W kodzie (nie w komentarzach) używaj apostrofów.
  2. `_transcribe_audio` KASUJE plik podany przez `_save_wav` — podstawienie tam
     `__file__` sprawiło, że test SKASOWAŁ SAM SIEBIE. Podkładamy plik tymczasowy.

Uruchomienie:  python3 -B tools/test-dictation.py

SABOTAZ - WYNIKI ZMIERZONE (uruchomione 2026-08-29, nie przewidziane).
Zdrowy kod: 48 sprawdzen, 48 OK, 0 FAIL. Kazdy wariant przywracany z pamieci
procesu, przywrocenie dowiedzione sha256.

  wariant                | co popsute                              | co padlo
  -----------------------+-----------------------------------------+---------------
  cichy-klik             | 'przetwarzam' -> znowu start nagrywania  | A3
  brak-odblokowania      | zakleszczenia nie da sie odblokowac      | A4
  bez-logu-odrzucenia    | odrzucony klik nie pisze do dziennika    | B1, B2
  wyciek-klucza          | do logu leci pelny klucz API             | B5, C1
  porzucone-wpada        | zdjeta straz numeru podejscia            | D1, D2
  stary-limit            | powrot do 30 s                           | F1, F2
  zargon                 | surowy blad requests leci do usera       | G1, G2
  pusto-cisza            | pusta odpowiedz bramki znowu milczy      | G4
  nigdy-zakleszczone     | is_stuck() zawsze False                  | E2

⚠️ CZEGO NAUCZYL SABOTAZ O TEJ BRAMCE: wariant 'wyciek-klucza' PIERWOTNIE nie
   zapalil C1, tylko przypadkiem B5 — bo C1 badal okno logu, w ktorym klucz nie
   ma prawa wystapic (czyli przechodzil na pustce). Stad doszla sonda C0, ktora
   najpierw WYMUSZA linie dotykajaca klucza. Bez sabotazu ta dziura zostalaby
   w bramce i wygladalaby na pokrycie.
"""
import os
import sys
import shutil
import tempfile
from pathlib import Path

# ⚠️ HOME PODMIENIAMY PRZED IMPORTEM config — inaczej test pisałby do PRAWDZIWEGO
# ~/.vibe-coding-assistant/dictation.log usera i zatruł dziennik dowodowy
# atrapowymi wpisami, nieodróżnialnymi od prawdziwych (ta pułapka zdarzyła się już
# w tym projekcie przy read-last-debug.log).
_HOME = tempfile.mkdtemp(prefix="cva-test-dictation-")
os.environ["HOME"] = _HOME

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import config  # noqa: E402
from core import stt_engine as SE  # noqa: E402
from core.stt_engine import (  # noqa: E402
    STTEngine, STTState, decide_mic_click, dictation_log,
    KLIK_STOP, KLIK_NAGRYWAJ, KLIK_ODBLOKUJ, KLIK_ZAJETE, KLIK_BRAK_KLUCZA,
)

OK = 0
FAIL = 0
WYKONANE = 0


def sprawdz(nazwa, warunek, szczegol=""):
    """Jedno sprawdzenie. Liczymy WYKONANE osobno od porażek — 'zero porażek' przy
    przerwanej bramce wygląda identycznie jak komplet zielonych."""
    global OK, FAIL, WYKONANE
    WYKONANE += 1
    if warunek:
        OK += 1
        print(f"[OK] {nazwa}")
    else:
        FAIL += 1
        print(f"[FAIL] {nazwa}" + (f"  -> {szczegol}" if szczegol else ""))


def plik_do_skasowania():
    """Świeży plik-atrapa nagrania. MUSI być jednorazowy: kod produkcyjny go kasuje."""
    sciezka = Path(_HOME) / f"nagranie-{os.urandom(4).hex()}.wav"
    sciezka.write_bytes(b"RIFF____WAVEfmt ")
    return str(sciezka)


def tresc_logu():
    try:
        return config.DICTATION_LOG.read_text(encoding="utf-8")
    except OSError:
        return ""


def wyczysc_log():
    try:
        config.DICTATION_LOG.unlink()
    except OSError:
        pass


def probka():
    return [SE.np.zeros((10, 1), dtype=SE.np.int16)]


# ============================================================================
print("\n=== A. DECYZJA KLIKNIECIA - sedno naprawy ===")
# ============================================================================
sprawdz("A1 spoczynek + klucz -> nagrywamy",
        decide_mic_click(False, False, False, True) == KLIK_NAGRYWAJ)
sprawdz("A2 nagrywanie -> konczymy i wysylamy",
        decide_mic_click(True, False, False, True) == KLIK_STOP)
sprawdz("A3 'przetwarzam' krotko -> MOWIMY, ze zajete (nie milczymy)",
        decide_mic_click(False, True, False, True) == KLIK_ZAJETE,
        f"dostalem {decide_mic_click(False, True, False, True)}")
sprawdz("A4 'przetwarzam' ZAKLESZCZONE -> odblokowujemy i nagrywamy",
        decide_mic_click(False, True, True, True) == KLIK_ODBLOKUJ,
        f"dostalem {decide_mic_click(False, True, True, True)}")
sprawdz("A5 brak klucza -> proponujemy wpisanie klucza",
        decide_mic_click(False, False, False, False) == KLIK_BRAK_KLUCZA)

# ⭐ ASERCJA, KTOREJ BRAK KOSZTOWAL USERA CALE ZGLOSZENIE: zadna kombinacja stanow
# nie moze konczyc sie 'nic, po cichu'. Sprawdzamy WSZYSTKIE 16 kombinacji.
znane = {KLIK_STOP, KLIK_NAGRYWAJ, KLIK_ODBLOKUJ, KLIK_ZAJETE, KLIK_BRAK_KLUCZA}
wszystkie = [decide_mic_click(r, p, s, k)
             for r in (False, True) for p in (False, True)
             for s in (False, True) for k in (False, True)]
sprawdz("A6 KAZDA z 16 kombinacji stanow daje ZNANA decyzje (nigdy ciche nic)",
        len(wszystkie) == 16 and all(d in znane for d in wszystkie),
        f"nieznane: {set(wszystkie) - znane}")
sprawdz("A7 kontrola negatywna: zbior decyzji NIE jest jednoelementowy",
        len(set(wszystkie)) >= 3, f"decyzje={set(wszystkie)}")

# ============================================================================
print("\n=== B. DZIENNIK - dyktowanie przestaje byc niewidzialne ===")
# ============================================================================
wyczysc_log()
eng = STTEngine(api_key="aim-KLUCZ-TAJNY-NIE-MA-PRAWA-TRAFIC-DO-LOGU")
eng.state = STTState.PROCESSING
eng._processing_since = SE.time.monotonic()
eng.start_recording()                     # ma zostac odrzucone - ale GLOSNO
log = tresc_logu()
sprawdz("B1 odrzucone klikniecie zostawia wpis w dzienniku",
        "ODRZUCONY" in log, f"log={log[:200]!r}")
sprawdz("B2 wpis mowi, w JAKIM stanie odrzucono", "stan=processing" in log)

eng.force_reset("test")
wyczysc_log()
eng.state = STTState.RECORDING
eng._recording_thread = None
eng._audio_buffer = []
eng.stop_recording()                      # pusty bufor
log = tresc_logu()
sprawdz("B3 puste nagranie jest RAPORTOWANE (nie milczy)", "PUSTO" in log)
sprawdz("B4 dziennik podaje dlugosc nagrania", "dlugosc=" in log)
sprawdz("B5 dziennik podaje, czy klucz w ogole jest", "klucz=jest" in log)

wyczysc_log()
dictation_log("linia probna")
sprawdz("B6 dziennik istnieje i ma znacznik czasu",
        config.DICTATION_LOG.exists() and "linia probna" in tresc_logu())

# ============================================================================
print("\n=== C. PRYWATNOSC I HIGIENA DZIENNIKA ===")
# ============================================================================
wyczysc_log()
eng2 = STTEngine(api_key="aim-KLUCZ-TAJNY-123456789")

# ⚠️ NAJPIERW wywolujemy gałąź, ktora W OGOLE DOTYKA KLUCZA (`stop_recording`
# raportuje 'klucz=jest/BRAK'). Bez tego asercja C1 badalaby okno logu, w ktorym
# klucza nie ma prawa byc — czyli przechodzilaby na PUSTO. Wykryl to sabotaz
# 'wyciek-klucza': podmiana na `klucz={self.api_key}` NIE zapalila C1, tylko
# przypadkiem B5. Pusty bufor => sciezka 'PUSTO', bez ruszania sieci.
eng2.state = STTState.RECORDING
eng2._recording_thread = None
eng2._audio_buffer = []
eng2.stop_recording()
sprawdz("C0 sonda: w logu JEST linia, ktora dotyka klucza (inaczej C1 bada pustke)",
        "NAGRYWANIE stop" in tresc_logu() and "klucz=" in tresc_logu())

eng2._attempt = 5
odebrane = []
eng2.on_transcription = odebrane.append
eng2._send_to_groq = lambda p: "To jest moja prywatna wypowiedz, ktorej nie wolno zapisywac w calosci."
eng2._save_wav = lambda d: plik_do_skasowania()
eng2._audio_buffer = probka()
eng2.state = STTState.PROCESSING
eng2._transcribe_audio(attempt=5)
log = tresc_logu()
sprawdz("C1 klucz API NIE trafia do dziennika", "KLUCZ-TAJNY" not in log)
sprawdz("C2 pelna tresc wypowiedzi NIE trafia do dziennika",
        "ktorej nie wolno zapisywac" not in log)
sprawdz("C3 ale dlugosc i poczatek SA (inaczej log jest bezuzyteczny)",
        "ROZPOZNANO:" in log and "znakow" in log)
sprawdz("C4 kontrola negatywna: tekst JEDNAK dotarl do odbiorcy",
        len(odebrane) == 1 and odebrane[0].startswith("To jest moja"))

wyczysc_log()
config.DICTATION_LOG.write_text("x" * (config.DICTATION_LOG_MAX_BYTES + 10), encoding="utf-8")
dictation_log("po przekroczeniu limitu")
sprawdz("C5 po przekroczeniu limitu dziennik startuje od nowa",
        config.DICTATION_LOG.stat().st_size < config.DICTATION_LOG_MAX_BYTES,
        f"rozmiar={config.DICTATION_LOG.stat().st_size}")

# ============================================================================
print("\n=== D. PORZUCONE PODEJSCIE nie wpada do pola pol minuty pozniej ===")
# ============================================================================
wyczysc_log()
eng3 = STTEngine(api_key="aim-x")
wstawione = []
eng3.on_transcription = wstawione.append
eng3.on_error = lambda e: None
eng3._save_wav = lambda d: plik_do_skasowania()
eng3._send_to_groq = lambda p: "spozniony tekst"
eng3._audio_buffer = probka()
eng3.state = STTState.PROCESSING
eng3._attempt = 4                          # user odblokowal w miedzyczasie
eng3._transcribe_audio(attempt=3)          # watek starego podejscia wraca
sprawdz("D1 wynik PORZUCONEGO podejscia nie trafia do pola polecen",
        wstawione == [], f"wstawione={wstawione}")
sprawdz("D2 porzucenie jest odnotowane w dzienniku", "PORZUCONY" in tresc_logu())
sprawdz("D3 porzucony watek NIE zdeptal stanu (user moze juz nagrywac)",
        eng3.state == STTState.PROCESSING, f"stan={eng3.state}")

wstawione.clear()
eng3._attempt = 7
eng3.state = STTState.PROCESSING
eng3._audio_buffer = probka()
eng3._transcribe_audio(attempt=7)          # kontrola negatywna: podejscie AKTUALNE
sprawdz("D4 kontrola negatywna: aktualne podejscie JEST wstawiane",
        wstawione == ["spozniony tekst"], f"wstawione={wstawione}")
sprawdz("D5 po aktualnym podejsciu wracamy do spoczynku",
        eng3.state == STTState.IDLE)

eng3.state = STTState.PROCESSING
eng3._processing_since = SE.time.monotonic()
przed = eng3._attempt
eng3.force_reset("test")
sprawdz("D6 odblokowanie podbija numer podejscia", eng3._attempt == przed + 1)
sprawdz("D7 odblokowanie wraca do spoczynku", eng3.state == STTState.IDLE)

# ============================================================================
print("\n=== E. ZAKLESZCZENIE rozpoznawane po CZASIE ===")
# ============================================================================
eng4 = STTEngine(api_key="aim-x")
eng4.state = STTState.PROCESSING
eng4._processing_since = SE.time.monotonic()
sprawdz("E1 swieze 'przetwarzam' NIE jest zakleszczeniem", not eng4.is_stuck())
eng4._processing_since = SE.time.monotonic() - (config.STT_PROCESSING_STUCK_SECS + 1)
sprawdz("E2 dlugie 'przetwarzam' JEST zakleszczeniem", eng4.is_stuck())
sprawdz("E3 wiek przetwarzania jest mierzony, nie zgadywany",
        eng4.processing_age() > config.STT_PROCESSING_STUCK_SECS)
eng4.state = STTState.IDLE
sprawdz("E4 w spoczynku wiek = 0 (brak falszywego zakleszczenia)",
        eng4.processing_age() == 0.0 and not eng4.is_stuck())

# ============================================================================
print("\n=== F. LIMIT CZASU faktycznie dociera do wysylki ===")
# ============================================================================
sprawdz("F1 limit skrocony z 30 s do rozsadnej wartosci",
        config.STT_HTTP_TIMEOUT <= 15, f"limit={config.STT_HTTP_TIMEOUT}")
sprawdz("F2 prog zakleszczenia lezy POWYZEJ limitu wysylki",
        config.STT_PROCESSING_STUCK_SECS > config.STT_HTTP_TIMEOUT,
        f"{config.STT_PROCESSING_STUCK_SECS} vs {config.STT_HTTP_TIMEOUT}")

# ⭐ Nie ufamy stalej - sprawdzamy, co REALNIE dostaje requests.post.
zlapane = {}


class _Odp:
    status_code = 200
    text = "wynik"
    headers = {}


def _fake_post(url, **kw):
    zlapane.update(kw)
    zlapane["url"] = url
    return _Odp()


_stary_post = SE.requests.post
SE.requests.post = _fake_post
try:
    STTEngine(api_key="aim-x")._send_to_groq(plik_do_skasowania())
finally:
    SE.requests.post = _stary_post
sprawdz("F3 limit z konfiguracji DOJEZDZA do wysylki",
        zlapane.get("timeout") == (config.STT_HTTP_TIMEOUT, config.STT_HTTP_TIMEOUT),
        f"timeout={zlapane.get('timeout')}")
sprawdz("F4 wysylka idzie pod adres bramki z konfiguracji",
        zlapane.get("url") == config.STT_API_URL)
sprawdz("F5 odpowiedz jest odnotowana w dzienniku (kod + czas)",
        "ODPOWIEDZ: kod=200" in tresc_logu())

# ============================================================================
print("\n=== G. BLAD SIECI mowi po ludzku, nie zargonem biblioteki ===")
# ============================================================================
wyczysc_log()


def _post_pada(url, **kw):
    raise SE.requests.exceptions.ConnectionError(
        "HTTPSConnectionPool(host='ai.example', port=443): Max retries exceeded")


SE.requests.post = _post_pada
komunikat = ""
try:
    try:
        STTEngine(api_key="aim-x")._send_to_groq(plik_do_skasowania())
    except Exception as e:
        komunikat = str(e)
finally:
    SE.requests.post = _stary_post

sprawdz("G1 uzytkownik NIE dostaje 'HTTPSConnectionPool'",
        "HTTPSConnectionPool" not in komunikat, f"komunikat={komunikat!r}")
sprawdz("G2 uzytkownik dostaje rade, co zrobic",
        komunikat == config.t('stt_err_network'), f"komunikat={komunikat!r}")
sprawdz("G3 surowa przyczyna ZOSTAJE w dzienniku (dla nas)",
        "ODPOWIEDZ: BRAK" in tresc_logu() and "ConnectionError" in tresc_logu())

# pusta odpowiedz bramki tez musi cos powiedziec
wyczysc_log()
eng7 = STTEngine(api_key="aim-x")
bledy = []
eng7.on_error = bledy.append
eng7.on_transcription = lambda t: sprawdz("G4 NIGDY nie wstawiaj pustki", False)
eng7._save_wav = lambda d: plik_do_skasowania()
eng7._send_to_groq = lambda p: ""
eng7._audio_buffer = probka()
eng7.state = STTState.PROCESSING
eng7._transcribe_audio(attempt=0)
sprawdz("G4 pusta odpowiedz bramki daje komunikat, nie cisze",
        bledy == [config.t('stt_err_empty')], f"bledy={bledy}")

# ============================================================================
print("\n=== H. TLUMACZENIA I SPRZATANIE ===")
# ============================================================================
pl = set(config.UI_TRANSLATIONS['pl-PL'])
en = set(config.UI_TRANSLATIONS['en-US'])
sprawdz("H1 parytet slownikow PL/EN", pl == en, f"roznica={pl ^ en}")
for klucz in ('stt_err_network', 'stt_err_empty', 'status_stt_busy',
              'status_stt_unblocked', 'dlg_stt_failed_title', 'dlg_stt_failed_msg'):
    sprawdz(f"H2 klucz '{klucz}' istnieje w OBU jezykach", klucz in pl and klucz in en)

# ⛔ Ta asercja pilnuje pulapki, ktora w tym projekcie ZDARZYLA SIE NAPRAWDE:
# zywy log diagnostyczny stal na liscie 'martwych' i kazdy start apki go kasowal.
from core.update_manager import UpdateManager  # noqa: E402
sprawdz("H3 dictation.log NIE jest na liscie logow kasowanych przy starcie",
        "dictation.log" not in UpdateManager._STALE_LOG_NAMES,
        f"lista={UpdateManager._STALE_LOG_NAMES}")
sprawdz("H4 dictation.log nie jest tez bramkowany czujnikiem (ma byc ZAWSZE)",
        all(n[0] != "dictation.log" for n in UpdateManager._GATED_LOG_NAMES))

# ============================================================================
shutil.rmtree(_HOME, ignore_errors=True)
print("\n" + "=" * 66)
print(f"WYKONANYCH SPRAWDZEN: {WYKONANE}   OK: {OK}   FAIL: {FAIL}")
print("=" * 66)
sys.exit(1 if FAIL else 0)
