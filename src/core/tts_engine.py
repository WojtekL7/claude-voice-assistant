"""
Vibe Coding Assistant - Text-to-Speech Engine
Uses edge-tts for high-quality multilingual speech synthesis.

Gapless streaming model (Etap 1):
- enqueue(text) dokłada zdania do kolejki BEZ przerywania bieżącego czytania.
- Wątek-generator pobiera audio dla kolejnych zdań Z WYPRZEDZENIEM (prefetch),
  podczas gdy wątek-odtwarzacz gra zdanie bieżące → brak ciszy między zdaniami.
- speak(text) zachowane dla kompatybilności (przycisk "czytaj"): stop + enqueue.
- clear_queue() / stop() czyści kolejkę (np. przy przełączeniu zakładki).
"""
import asyncio
import queue
import re
import tempfile
import threading
import time
import os
from typing import Optional, Callable
from enum import Enum

import edge_tts
import pygame


# === Bezpiecznik na WYJŚCIU do głosu (jeden punkt kontrolny dla WSZYSTKICH dróg
# czytania) ===
# Każda droga (auto-czytaj, 🔊 ostatnia, zaznaczenie, request_tts) przechodzi
# przez enqueue(). Niezależnie od tego, który „czyścik" ją poprzedził, tu jeszcze
# raz zdejmujemy emoji/symbole/emotikony — gwarancja, że lektor NIGDY ich nie
# wypowie. Filtr jest samodzielny (bez zależności od text_cleaner), bo silnik TTS
# jest współdzielony między projektami; wycinanie emoji jest pożądane w obu.
_SPEECH_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # emoji + piktogramy + flagi
    "\U00002600-\U000027BF"   # symbole różne + dingbaty
    "\U00002300-\U000023FF"   # Misc Technical: ⏳ ⌛ ⌚ ⏰ …
    "\U00002100-\U0000214F"   # letterlike: ™ ℹ № …
    "\U00002190-\U000021FF"   # strzałki
    "\U00002B00-\U00002BFF"   # strzałki/symbole
    "\U00002500-\U000025FF"   # ramki + bloki + figury
    "\U0000FE00-\U0000FE0F"   # variation selectors
    "\U000020E3"              # enclosing keycap
    "]",
    flags=re.UNICODE,
)
# ⛔ BLIŹNIACZA KOPIA wzorców z src/core/text_cleaner.py (_EMOTICONS
# i _EMOTICONS_GLUED). Kopia jest ŚWIADOMA — patrz komentarz wyżej: ten silnik
# bywa współdzielony między projektami, więc nie może zależeć od text_cleaner.
# Cena kopii: musi być zmieniana RAZEM z oryginałem. Pilnuje tego bramka
# tools/test-emoticon-speech.py (porównuje oba wzorce na wspólnym zestawie).
#
# Drugi wzorzec łapie emotikonę PRZYKLEJONĄ do słowa („Gotowe:("), której
# pierwszy nie widzi, bo (?<!\w) wymaga braku litery przed dwukropkiem.
_SPEECH_EMOTICON_RE = re.compile(
    r"(?<!\w)(?:"
    r"[:;=][-~^']?[)(\]\[DPpOo|/\\3<>*]"
    r"|[xX][DdPp]"
    r"|<3|</3|\^\^|\^_\^|-_-|>_<|[Tt]_[Tt]|;_;|[oO]_[oO]"
    r")(?!\w)",
)
_SPEECH_EMOTICON_GLUED_RE = re.compile(
    r"(?<!\d)(?<![:/\\])[:;][-~^']?[)(\]\[DdPp](?!\w)"
)

# CZUJKA (nie filtr!) — co POZOSTAŁO w tekście, a głos potrafi wymówić jako
# emotikonę. Celowo SZERSZA niż filtry: ma zgłaszać także kształty, których
# świadomie NIE wycinamy („8)", „:/"), żeby następne zgłoszenie „lektor czyta
# emotikonę" miało dowód co do znaku zamiast zgadywania. Sama niczego nie usuwa.
_SPEECH_EMOTICON_AUDIT_RE = re.compile(
    r"[:;=8][-~^']?[)(\]\[DPpOo|/\\3<>*]|[xX][DdPp]|<3|\^\^|-_-|>_<|;_;"
)


def _sanitize_for_speech(text: str) -> str:
    """Ostatnia bramka przed syntezą: usuń emoji/symbole/emotikony."""
    if not text:
        return text
    text = _SPEECH_EMOJI_RE.sub(" ", text)
    text = _SPEECH_EMOTICON_RE.sub(" ", text)
    text = _SPEECH_EMOTICON_GLUED_RE.sub(" ", text)
    return text


class TTSState(Enum):
    IDLE = "idle"
    GENERATING = "generating"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"


# Ile zdań trzymać wygenerowanych "do przodu". Bufor pochłania wahania
# opóźnień sieciowych edge-tts, dzięki czemu odtwarzanie jest ciągłe.
PREFETCH_DEPTH = 2

# Twardy limit czasu na pobranie audio JEDNEGO zdania z edge-tts (sekundy).
# Bez tego zatkany serwer Microsoftu / przycięta sieć blokował wątek-generator
# w NIESKOŃCZONOŚĆ na jednym zdaniu, a lektor milkł czekając na audio, które
# nigdy nie przyszło ("czytanie się wiesza").
TTS_GEN_TIMEOUT = 12
# Ile razy łącznie próbować pobrać jedno zdanie, zanim je pominiemy.
TTS_GEN_ATTEMPTS = 2

# Ile sekund czekać, aż wróci SIEĆ, zanim przerwiemy czytanie (licząc od
# pierwszej nieudanej próby). ZMIERZONE 2026-10-14: Wi-Fi zerwało się na 3 s
# (15:28:55 → 15:28:58), a bez internetu każda próba pada w ułamku sekundy
# (nie da się znaleźć serwera) — więc „2 próby i następne zdanie" wyrzuciło
# 11 pozostałych zdań w JEDNEJ sekundzie i czytanie urwało się w pół
# wypowiedzi, bez żadnego komunikatu. Brak sieci to nie wada zdania: czekamy
# na nią i czytamy dalej OD TEGO SAMEGO zdania.
TTS_NET_WAIT_SECS = 30
# Odstępy między próbami podczas czekania na sieć (ostatni się powtarza).
TTS_NET_RETRY_DELAYS = (1, 2, 4, 8)


def is_network_error(exc: BaseException) -> bool:
    """Czy błąd znaczy „brak połączenia", a nie „serwer odrzucił zdanie"?

    Sieć: nie da się znaleźć serwera (DNS), połączyć ani utrzymać połączenia.
    NIE sieć (stare zachowanie — pomiń zdanie): serwer ODPOWIEDZIAŁ odmową
    (np. 403 po zmianie tokenu Microsoftu), brak dźwięku w odpowiedzi,
    przekroczenie czasu (już kosztowało 12 s na próbę — czekanie dalej
    zamieniłoby zatkany serwer w minuty ciszy na każdym zdaniu).

    ⚠️ KOLEJNOŚĆ SPRAWDZEŃ MA ZNACZENIE: w Pythonie TimeoutError jest
    podklasą OSError, więc limit czasu wykluczamy NAJPIERW.
    ⚠️ Nie zastępuj ClientConnectionError szerszym aiohttp.ClientError —
    złapałby odmowy serwera (ClientResponseError, np. 403) i lektor czekałby
    30 s na KAŻDYM zdaniu, którego serwer i tak nie przyjmie. (Osobnego
    wykluczenia odmów nie ma, bo w aiohttp nie są one ani OSError, ani
    błędem połączenia — zmierzone 2026-10-14; pilnuje tego bramka, A5.)
    """
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return False
    try:
        import aiohttp
        if isinstance(exc, aiohttp.ClientConnectionError):
            return True
    except ImportError:
        pass
    return isinstance(exc, OSError)


class _NetworkGaveUp(Exception):
    """Sieć nie wróciła w TTS_NET_WAIT_SECS — przerwij czytanie całej reszty."""

    def __init__(self, waited: float):
        super().__init__(f"brak sieci od {waited:.0f} s")
        self.waited = waited

# Maksymalna długość JEDNEGO kawałka wysyłanego do edge-tts (znaki).
# Krótkie kawałki pobierają się szybko → twardy limit czasu (TTS_GEN_TIMEOUT)
# praktycznie nigdy nie strzela → brak „dziur" i przeskoków w czytaniu. Tekst
# zaznaczony w terminalu bywa jednym wielkim blokiem bez kropek; bez tego limitu
# trafiał do edge-tts jako olbrzymi kawałek, który nie wyrabiał się w czasie i
# był POMIJANY (objaw: czyta, cisza, przeskok kilka zdań dalej). 200 zn. mieści
# większość zdań w całości, więc prozodia pozostaje naturalna.
MAX_TTS_CHUNK_CHARS = 200

# ---------------------------------------------------------------------------
# Format i bufor odtwarzania — NIE zostawiać wartości domyślnych.
#
# ZMIERZONE 2026-07-26 (zgłoszenie „trzeszczenie w czytaniu lektora"):
# `pygame.mixer.init()` bez parametrów negocjuje z PipeWire bufor **128 próbek
# (2,7 ms)**. PipeWire ustawia CAŁĄ kartę dźwiękową na NAJMNIEJSZY bufor,
# jakiego zażądał którykolwiek program — a nasz strumień jest otwarty przez
# cały czas życia aplikacji. Skutek: trzeszczał nie tylko lektor, ale KAŻDY
# dźwięk w systemie (przeglądarka, filmy, muzyka), dopóki apka była włączona.
# Dowód: pw-top pokazywał kartę na 128 i licznik błędów rosnący ~2-3/s;
# wymuszenie bufora 1024 (`pw-metadata … clock.force-quantum`) uciszyło
# wszystkie odtwarzacze naraz — potwierdzone odsłuchem u użytkownika.
#
# 4096 próbek przy 24 kHz to ~170 ms zapasu — dla czytania gotowych zdań
# opóźnienie bez znaczenia (nie gramy na żywo), a odporność na zadyszkę
# komputera ogromna (4 rdzenie + kilka procesów `claude` w tle).
# 24 kHz mono = dokładnie to, co oddaje edge-tts → znika też przepróbkowanie
# 24→44,1 kHz przy każdym zdaniu. pygame w tej aplikacji obsługuje WYŁĄCZNIE
# mowę z edge-tts (żadnych innych dźwięków), więc zawężenie formatu jest bezpieczne.
MIXER_FREQUENCY = 24000
MIXER_SIZE = -16
MIXER_CHANNELS = 1
MIXER_BUFFER = 4096


class TTSEngine:
    """
    Text-to-Speech engine z płynnym, kolejkowanym odtwarzaniem (prefetch).
    Uses edge-tts for synthesis and pygame for playback.
    """

    def __init__(self):
        self.voice = "pl-PL-ZofiaNeural"
        self.rate = "+0%"
        self.volume = "+0%"

        self.state = TTSState.IDLE

        # Callbacks (wywoływane z wątków TTS — w aplikacji emitują sygnały Qt,
        # więc dostęp do GUI jest bezpieczny wątkowo).
        self.on_state_changed: Optional[Callable[[TTSState], None]] = None
        self.on_progress: Optional[Callable[[int, int], None]] = None
        self.on_finished: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        # Czytanie PRZERWANE, bo sieć nie wróciła (argument: ile sekund
        # czekaliśmy). Osobno od on_error, bo to jedyny błąd, o którym
        # użytkownik MUSI się dowiedzieć — reszta wypowiedzi przepadła.
        self.on_network_lost: Optional[Callable[[float], None]] = None

        # Initialize pygame mixer — defensywnie: na komputerze BEZ urządzenia
        # audio (brak głośników/sterownika, pulpit zdalny, maszyna CI) init()
        # rzuca pygame.error i wywalał CAŁĄ aplikację przy starcie (crash
        # zanim pojawiło się okno). Brak audio = czytanie wyłączone, reszta
        # aplikacji działa normalnie.
        try:
            try:
                pygame.mixer.init(frequency=MIXER_FREQUENCY, size=MIXER_SIZE,
                                  channels=MIXER_CHANNELS, buffer=MIXER_BUFFER)
            except Exception:
                # Sterownik odrzucił nasz format (rzadkie, ale możliwe na innym
                # systemie) — lepiej czytać z domyślnymi ustawieniami niż wcale.
                pygame.mixer.init()
            self.audio_available = True
        except Exception as e:
            self.audio_available = False
            # Komunikat celowo ASCII + print w try/except: na Windows
            # przekierowany stdout ma cp1252 i print() z polskim znakiem
            # sam potrafiłby wywalić aplikację (UnicodeEncodeError).
            try:
                print(f"TTS: no audio device - TTS disabled ({e})")
            except Exception:
                pass

        # --- Współbieżność ---
        self._lock = threading.Lock()
        self._running = False
        self._active = False  # czy aktualnie coś gramy/generujemy (do on_finished)

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # domyślnie NIE wstrzymane

        self._pending: "queue.Queue[str]" = queue.Queue()
        self._ready: "queue.Queue[tuple]" = queue.Queue(maxsize=PREFETCH_DEPTH)

        self._gen_thread: Optional[threading.Thread] = None
        self._play_thread: Optional[threading.Thread] = None

        self._temp_files = set()  # ścieżki mp3 do posprzątania (pod _lock)

    # ==================== Ustawienia ====================

    def set_voice(self, voice: str):
        self.voice = voice

    def set_rate(self, rate: str):
        self.rate = rate

    def set_volume(self, volume: str):
        self.volume = volume

    # ==================== API publiczne ====================

    def enqueue(self, text: str):
        """Dołóż tekst do kolejki czytania BEZ przerywania bieżącego.

        Tekst jest dzielony na zdania; każde zdanie to osobny element kolejki,
        co pozwala generować audio z wyprzedzeniem i grać bez przerw.
        """
        if not text or not text.strip():
            return

        # Bramka wyjściowa: zdejmij emoji/symbole/emotikony niezależnie od tego,
        # którą drogą (i którym czyścikiem) tekst tu dotarł. Gdy po oczyszczeniu
        # zostanie pusto (np. sama klepsydra) — nie kolejkujemy.
        text = _sanitize_for_speech(text)
        if not text.strip():
            return

        # Ślad diagnostyczny: jeśli MIMO bramki w tekście został kształt, który
        # głos wymawia jako emotikonę, zapisz to. Nie blokujemy czytania —
        # fałszywe oskarżenie tekstu byłoby gorsze niż jedno dziwne słowo.
        self._audit_emoticons(text)

        # Bez urządzenia audio nie kolejkujemy (workery i tak nie zagrają);
        # zgłoś czytelny błąd zamiast cicho mielić tekst.
        if not getattr(self, "audio_available", True):
            if self.on_error:
                try:
                    from config import t as tr
                    self.on_error(tr('tts_no_audio'))
                except Exception:
                    pass
            return

        sentences = self._split_into_sentences(text)
        if not sentences:
            return

        with self._lock:
            if not self._running:
                self._start_workers_locked()
            for s in sentences:
                self._pending.put(s)

        # Sygnalizuj aktywność od razu (UI: animacja głośnika), jeśli stoimy.
        if self.state == TTSState.IDLE:
            self._set_state(TTSState.GENERATING)

    def speak(self, text: str):
        """Zatrzymaj bieżące czytanie i zacznij od nowa (przycisk 'czytaj')."""
        if not text or not text.strip():
            return
        self.stop()
        self.enqueue(text)

    def clear_queue(self):
        """Wyczyść kolejkę i zatrzymaj czytanie (np. przy zmianie zakładki)."""
        self.stop()

    def pending_chars(self) -> int:
        """Ile ZNAKÓW czeka jeszcze w kolejce = jak bardzo lektor jest w tyle.

        Mowa idzie ~15 znaków/s, więc 900 znaków ≈ minuta zaległości. Używane
        przez nadganianie (MainWindow._catch_up_if_behind): agent potrafi pisać
        szybciej, niż lektor mówi, i bez tego kolejka rośnie w nieskończoność
        (zgłoszenie 2026-07-21: „czyta przedostatnią wypowiedź" — w istocie
        czytał właściwą, tylko sprzed dwóch minut).

        Zdanie AKTUALNIE czytane jest już poza kolejką, a kilka zdań siedzi
        w buforze wyprzedzającym — to miara zgrubna i taka wystarcza.
        """
        try:
            with self._pending.mutex:
                return sum(len(s) for s in self._pending.queue if isinstance(s, str))
        except Exception:
            return 0

    def pause(self):
        """Pause playback."""
        if self.state == TTSState.PLAYING:
            self._pause_event.clear()
            try:
                pygame.mixer.music.pause()
            except Exception:
                pass
            self._set_state(TTSState.PAUSED)

    def resume(self):
        """Resume playback from pause."""
        if self.state == TTSState.PAUSED:
            self._pause_event.set()
            try:
                pygame.mixer.music.unpause()
            except Exception:
                pass
            self._set_state(TTSState.PLAYING)

    def toggle_pause(self):
        if self.state == TTSState.PLAYING:
            self.pause()
        elif self.state == TTSState.PAUSED:
            self.resume()

    def stop(self):
        """Zatrzymaj odtwarzanie całkowicie i posprzątaj.

        Defensywnie: pygame/SDL potrafi rzucić wyjątek przy stop() na zepsutym
        stanie miksera (np. po wadliwym MP3). Nigdy nie pozwalamy, by wyjątek
        stąd ubił cały proces GUI.
        """
        # Zasygnalizuj wątkom zakończenie i odblokuj ewentualną pauzę.
        self._stop_event.set()
        self._pause_event.set()

        gen_t, play_t = self._gen_thread, self._play_thread

        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass

        # Krótki join — wątki pętlą z timeoutem 0.2s zauważą stop szybko.
        # Nie blokujemy GUI na długo (są to wątki daemon).
        for t in (gen_t, play_t):
            if t and t.is_alive() and t is not threading.current_thread():
                t.join(timeout=0.5)

        with self._lock:
            self._running = False
            self._active = False
            # Opróżnij kolejki.
            self._drain_queue(self._pending)
            ready_left = self._drain_queue(self._ready)
            self._gen_thread = None
            self._play_thread = None

        # Posprzątaj pliki, które były wygenerowane, a nieodtworzone.
        for item in ready_left:
            try:
                _, path = item
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        self._cleanup_temp_files()

        # Świeże eventy/kolejki na kolejną sesję czytania.
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._pending = queue.Queue()
        self._ready = queue.Queue(maxsize=PREFETCH_DEPTH)

        self._set_state(TTSState.IDLE)

    def is_playing(self) -> bool:
        return self.state in (TTSState.PLAYING, TTSState.PAUSED, TTSState.GENERATING)

    def get_state(self) -> TTSState:
        return self.state

    # ==================== Wnętrze ====================

    def _set_state(self, state: TTSState):
        self.state = state
        if self.on_state_changed:
            try:
                self.on_state_changed(state)
            except Exception:
                pass

    @staticmethod
    def _drain_queue(q: "queue.Queue") -> list:
        items = []
        try:
            while True:
                items.append(q.get_nowait())
        except queue.Empty:
            pass
        return items

    def _start_workers_locked(self):
        """Uruchom świeże wątki generatora i odtwarzacza. Wołane pod _lock."""
        self._stop_event = threading.Event()
        self._pause_event.set()
        self._running = True
        self._active = False
        self._gen_thread = threading.Thread(target=self._gen_loop,
                                            args=(self._stop_event, self._pending, self._ready),
                                            daemon=True)
        self._play_thread = threading.Thread(target=self._play_loop,
                                             args=(self._stop_event, self._pending, self._ready),
                                             daemon=True)
        self._gen_thread.start()
        self._play_thread.start()

    def _split_into_sentences(self, text: str) -> list:
        """Podziel tekst na kawałki dogodne dla TTS.

        Najpierw po zdaniach (`.!?`), a potem zbyt długie zdania na mniejsze
        fragmenty, tak by ŻADEN kawałek nie przekroczył MAX_TTS_CHUNK_CHARS.
        Drobne kawałki = szybka synteza edge-tts = limit czasu nie strzela =
        brak przeskoków/dziur (zwłaszcza dla tekstu zaznaczonego w terminalu,
        który bywa jednym wielkim blokiem bez kropek).
        """
        import re
        chunks = []
        for s in re.split(r'(?<=[.!?])\s+', text):
            s = s.strip()
            if not s:
                continue
            if len(s) <= MAX_TTS_CHUNK_CHARS:
                chunks.append(s)
            else:
                chunks.extend(self._split_long_chunk(s))
        if not chunks:
            stripped = text.strip()
            if stripped:
                chunks = [stripped]
        return chunks

    @staticmethod
    def _split_long_chunk(text: str) -> list:
        """Potnij zbyt długie zdanie na ≤ MAX_TTS_CHUNK_CHARS.

        Najpierw na granicach klauzul (po `,` `;` `:`), a klauzule wciąż za
        długie — pakując słowo po słowie. Pojedyncze „słowo" dłuższe niż limit
        (zlepek bez spacji) tniemy na twardo, by nic olbrzymiego nie trafiło
        do edge-tts. Nic nie ginie — łączenie wyniku odtwarza treść.
        """
        import re
        out = []
        for clause in re.split(r'(?<=[,;:])\s+', text):
            clause = clause.strip()
            if not clause:
                continue
            if len(clause) <= MAX_TTS_CHUNK_CHARS:
                out.append(clause)
                continue
            cur = ""
            for w in clause.split():
                if not cur:
                    cur = w
                elif len(cur) + 1 + len(w) <= MAX_TTS_CHUNK_CHARS:
                    cur += " " + w
                else:
                    out.append(cur)
                    cur = w
                while len(cur) > MAX_TTS_CHUNK_CHARS:
                    out.append(cur[:MAX_TTS_CHUNK_CHARS])
                    cur = cur[MAX_TTS_CHUNK_CHARS:]
            if cur:
                out.append(cur)
        return out

    def _gen_loop(self, stop_event, pending, ready):
        """Wątek-generator: pobiera audio dla kolejnych zdań z wyprzedzeniem."""
        while not stop_event.is_set():
            try:
                sentence = pending.get(timeout=0.2)
            except queue.Empty:
                continue
            if stop_event.is_set():
                break

            try:
                path = self._generate_audio(sentence, stop_event)
            except _NetworkGaveUp as e:
                # Sieć nie wróciła: NIE mielimy reszty kolejki po cichu (każde
                # zdanie padłoby w ułamku sekundy). Wyrzucamy ją JAWNIE i mówimy
                # o tym użytkownikowi; to, co już pobrane, odtwarzacz dogra.
                left = self._drain_queue(pending)
                self._log_error(
                    f"BRAK SIECI od {e.waited:.0f}s — przerywam czytanie, "
                    f"nieprzeczytanych zdan: {len(left) + 1}"
                )
                if self.on_network_lost and not stop_event.is_set():
                    try:
                        self.on_network_lost(e.waited)
                    except Exception:
                        pass
                continue
            if stop_event.is_set():
                break
            if not path:
                continue

            # Wstaw do gotowych; blokuje gdy bufor pełny (backpressure = prefetch).
            while not stop_event.is_set():
                try:
                    ready.put((sentence, path), timeout=0.2)
                    break
                except queue.Full:
                    continue

    def _play_loop(self, stop_event, pending, ready):
        """Wątek-odtwarzacz: gra gotowe pliki jeden po drugim, bez przerw."""
        try:
            while not stop_event.is_set():
                try:
                    sentence, path = ready.get(timeout=0.2)
                except queue.Empty:
                    # Nic gotowego — sprawdź, czy to koniec całej kolejki.
                    if self._active and pending.empty() and ready.empty():
                        self._active = False
                        if not stop_event.is_set():
                            self._set_state(TTSState.IDLE)
                            if self.on_finished:
                                try:
                                    self.on_finished()
                                except Exception:
                                    pass
                    continue

                self._active = True
                self._pause_event.wait()
                if stop_event.is_set():
                    self._safe_remove(path)
                    break

                self._set_state(TTSState.PLAYING)
                self._play_audio_file(path)

                # Czekaj na koniec odtwarzania (respektując pauzę/stop).
                # KOLEJNOŚĆ MA ZNACZENIE: pauzę sprawdzamy PRZED get_busy().
                # W pygame 2.6/SDL 2.28 `get_busy()` przy wstrzymanym odtwarzaniu
                # zwraca False (zweryfikowane empirycznie) — gdyby sprawdzić busy
                # najpierw, pauza wyglądałaby jak „koniec zdania": pętla pękała,
                # bieżące zdanie było wyrzucane i lektor wznawiał od NASTĘPNEGO
                # (objaw: „pomija resztę zdania i czyta od kropki dalej").
                while True:
                    if stop_event.is_set():
                        break
                    if not self._pause_event.is_set():
                        # Wstrzymane — czekaj na wznowienie, NIE kończ zdania.
                        self._pause_event.wait()
                        continue
                    try:
                        busy = pygame.mixer.music.get_busy()
                    except Exception:
                        busy = False
                    if not busy:
                        break
                    pygame.time.wait(50)

                self._safe_remove(path)
        except Exception as e:
            if self.on_error:
                try:
                    self.on_error(str(e))
                except Exception:
                    pass

    def _generate_audio(self, text: str,
                        stop_event: Optional[threading.Event] = None) -> Optional[str]:
        """Generate audio file for text using edge-tts.

        Pobranie JEDNEGO zdania ma twardy limit czasu (TTS_GEN_TIMEOUT) i jest
        ponawiane do TTS_GEN_ATTEMPTS razy. Gdy wszystkie próby zawiodą,
        zwracamy None — wątek-generator pominie to zdanie i pójdzie dalej,
        zamiast wisieć w nieskończoność na zatkanym serwerze/sieci.

        WYJĄTEK — brak SIECI (is_network_error): to nie wada zdania, więc nie
        zużywa prób. Czekamy na sieć (TTS_NET_RETRY_DELAYS) i ponawiamy TO SAMO
        zdanie; po TTS_NET_WAIT_SECS rzucamy _NetworkGaveUp, a wątek-generator
        przerywa czytanie i zgłasza to użytkownikowi.

        `stop_event` = event TEJ sesji czytania (z _gen_loop). self._stop_event
        bywa podmieniany przez stop(), więc czekanie na nim mogłoby nie
        zauważyć „Stop" klikniętego w trakcie czekania na sieć.
        """
        if stop_event is None:
            stop_event = self._stop_event
        try:
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.mp3', delete=False, prefix='claude_tts_'
            )
            temp_path = temp_file.name
            temp_file.close()
        except Exception as e:
            self._log_error(f"nie udało się utworzyć pliku tymczasowego: {e}")
            return None

        with self._lock:
            self._temp_files.add(temp_path)

        attempt = 0
        net_down_since = None
        net_tries = 0
        while attempt < TTS_GEN_ATTEMPTS:
            if stop_event.is_set():
                self._safe_remove(temp_path)
                return None
            try:
                asyncio.run(self._async_generate(text, temp_path))
                if net_down_since is not None:
                    self._log_error(
                        f"siec wrocila po {time.monotonic() - net_down_since:.1f}s "
                        f"({net_tries} prob) — czytam dalej od tego samego zdania"
                    )
                return temp_path
            except Exception as e:
                if is_network_error(e):
                    now = time.monotonic()
                    if net_down_since is None:
                        net_down_since = now
                        self._log_error(
                            f"BRAK SIECI: {type(e).__name__}: {e} — czekam do "
                            f"{TTS_NET_WAIT_SECS}s, zdanie NIE jest pomijane"
                        )
                    waited = now - net_down_since
                    if waited >= TTS_NET_WAIT_SECS:
                        self._safe_remove(temp_path)
                        raise _NetworkGaveUp(waited)
                    delay = TTS_NET_RETRY_DELAYS[min(net_tries, len(TTS_NET_RETRY_DELAYS) - 1)]
                    net_tries += 1
                    # Event.wait zamiast sleep: „Stop" w trakcie czekania działa od razu.
                    if stop_event.wait(min(delay, TTS_NET_WAIT_SECS - waited)):
                        self._safe_remove(temp_path)
                        return None
                    continue
                attempt += 1
                self._log_error(
                    f"próba {attempt}/{TTS_GEN_ATTEMPTS} nie powiodła się "
                    f"(limit={TTS_GEN_TIMEOUT}s): {type(e).__name__}: {e}"
                )

        # Wszystkie próby zawiodły — pomijamy to zdanie (lektor czyta dalej).
        self._safe_remove(temp_path)
        if self.on_error:
            try:
                self.on_error(f"TTS: pominięto zdanie po {TTS_GEN_ATTEMPTS} próbach")
            except Exception:
                pass
        return None

    async def _async_generate(self, text: str, output_path: str):
        """Async generation using edge-tts (twardy limit czasu na pobranie).

        `asyncio.wait_for` po TTS_GEN_TIMEOUT anuluje zawieszone pobieranie i
        rzuca TimeoutError, który łapie pętla ponowień w `_generate_audio`.
        """
        communicate = edge_tts.Communicate(
            text, self.voice, rate=self.rate, volume=self.volume
        )
        await asyncio.wait_for(
            communicate.save(output_path), timeout=TTS_GEN_TIMEOUT
        )

    def _play_audio_file(self, file_path: str):
        """Play audio file using pygame.

        Defensywnie: wadliwy MP3 zostawia mikser pygame w niespójnym stanie,
        który może segfaultować przy późniejszym stop(). Łykamy błąd, by
        pominąć złe zdanie zamiast ubijać całą aplikację.
        """
        try:
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
        except Exception as e:
            if self.on_error:
                try:
                    self.on_error(f"Playback failed: {str(e)}")
                except Exception:
                    pass

    def _safe_remove(self, path: str):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        with self._lock:
            self._temp_files.discard(path)

    def _cleanup_temp_files(self):
        """Remove temporary audio files."""
        with self._lock:
            paths = list(self._temp_files)
            self._temp_files.clear()
        for path in paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    def _audit_emoticons(self, text: str):
        """Zanotuj kształty, które głos może wymówić jako emotikonę (diagnostyka).

        Powód: zgłoszenie 2026-09-18 („lektor mówi «emotikon smutek»"). Filtry
        zostały uszczelnione, ale w 8000 wypowiedzi z dzienników nie było ani
        jednego takiego przypadku — czyli źródło może leżeć poza dziennikiem
        (tekst z ekranu, zaznaczenie). Bez zapisu następna diagnoza znów byłaby
        zgadywaniem. Zapisujemy SAM KSZTAŁT i wąski kontekst, nie całą wypowiedź.
        """
        try:
            trafienia = _SPEECH_EMOTICON_AUDIT_RE.findall(text)
            if not trafienia:
                return
            fragmenty = []
            for m in _SPEECH_EMOTICON_AUDIT_RE.finditer(text):
                i = m.start()
                fragmenty.append(repr(text[max(0, i - 25):i + len(m.group(0)) + 15]))
                if len(fragmenty) >= 3:
                    break
            self._log_error(
                "AUDYT EMOTIKON: do lektora poszlo "
                f"{len(trafienia)} ksztaltow {sorted(set(trafienia))} | " + " ".join(fragmenty)
            )
        except Exception:
            pass

    def _log_error(self, msg: str):
        """Dopisz błąd TTS do pliku log (diagnostyka).

        Wcześniej błędy TTS szły TYLKO jako "toast" do okna i znikały — nie było
        po nich śladu, co utrudniało diagnozę przerw w czytaniu. Zapis do pliku
        jest celowo opakowany w try/except: log nigdy nie może wywalić lektora.
        """
        try:
            import datetime
            log_dir = os.path.join(os.path.expanduser("~"), ".vibe-coding-assistant")
            os.makedirs(log_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(os.path.join(log_dir, "tts.log"), "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
        except Exception:
            pass

    def get_available_voices(self) -> list:
        """Get list of available voices."""
        try:
            return asyncio.run(edge_tts.list_voices())
        except Exception:
            return []

    def __del__(self):
        """Cleanup on destruction."""
        try:
            self.stop()
        except Exception:
            pass
        try:
            pygame.mixer.quit()
        except Exception:
            pass
