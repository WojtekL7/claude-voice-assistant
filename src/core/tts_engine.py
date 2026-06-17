"""
Claude Voice Assistant - Text-to-Speech Engine
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
import tempfile
import threading
import os
from typing import Optional, Callable
from enum import Enum

import edge_tts
import pygame


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

        # Initialize pygame mixer — defensywnie: na komputerze BEZ urządzenia
        # audio (brak głośników/sterownika, pulpit zdalny, maszyna CI) init()
        # rzuca pygame.error i wywalał CAŁĄ aplikację przy starcie (crash
        # zanim pojawiło się okno). Brak audio = czytanie wyłączone, reszta
        # aplikacji działa normalnie.
        try:
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
        """Podziel tekst na zdania (dla płynnej pauzy i szybkiego startu)."""
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            sentences = [text.strip()]
        return sentences

    def _gen_loop(self, stop_event, pending, ready):
        """Wątek-generator: pobiera audio dla kolejnych zdań z wyprzedzeniem."""
        while not stop_event.is_set():
            try:
                sentence = pending.get(timeout=0.2)
            except queue.Empty:
                continue
            if stop_event.is_set():
                break

            path = self._generate_audio(sentence)
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
                while True:
                    try:
                        busy = pygame.mixer.music.get_busy()
                    except Exception:
                        busy = False
                    if not busy:
                        break
                    if stop_event.is_set():
                        break
                    self._pause_event.wait()
                    pygame.time.wait(50)

                self._safe_remove(path)
        except Exception as e:
            if self.on_error:
                try:
                    self.on_error(str(e))
                except Exception:
                    pass

    def _generate_audio(self, text: str) -> Optional[str]:
        """Generate audio file for text using edge-tts.

        Pobranie JEDNEGO zdania ma twardy limit czasu (TTS_GEN_TIMEOUT) i jest
        ponawiane do TTS_GEN_ATTEMPTS razy. Gdy wszystkie próby zawiodą,
        zwracamy None — wątek-generator pominie to zdanie i pójdzie dalej,
        zamiast wisieć w nieskończoność na zatkanym serwerze/sieci.
        """
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

        for attempt in range(1, TTS_GEN_ATTEMPTS + 1):
            if self._stop_event.is_set():
                self._safe_remove(temp_path)
                return None
            try:
                asyncio.run(self._async_generate(text, temp_path))
                return temp_path
            except Exception as e:
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

    def _log_error(self, msg: str):
        """Dopisz błąd TTS do pliku log (diagnostyka).

        Wcześniej błędy TTS szły TYLKO jako "toast" do okna i znikały — nie było
        po nich śladu, co utrudniało diagnozę przerw w czytaniu. Zapis do pliku
        jest celowo opakowany w try/except: log nigdy nie może wywalić lektora.
        """
        try:
            import datetime
            log_dir = os.path.join(os.path.expanduser("~"), ".claude-voice-assistant")
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
