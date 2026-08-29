"""
Vibe Coding Assistant - Speech-to-Text Engine
Uses Groq Whisper API for fast, accurate transcription.
"""
import io
import wave
import tempfile
import threading
import os
import time
from datetime import datetime
from typing import Optional, Callable
from enum import Enum

import numpy as np
import sounddevice as sd
import requests

from config import (
    STT_API_URL, STT_MODEL, STT_LANGUAGE_DEFAULT,
    STT_HTTP_TIMEOUT, STT_PROCESSING_STUCK_SECS,
    DICTATION_LOG, DICTATION_LOG_MAX_BYTES,
    t as tr,
)


def dictation_log(msg: str):
    """Dopisz linię do dziennika dyktowania (`~/.vibe-coding-assistant/dictation.log`).

    ⛔ Ten log jest ZAWSZE WŁĄCZONY — patrz komentarz przy `DICTATION_LOG` w
    `config.py`. Piszemy wyłącznie przy kliknięciu mikrofonu i wokół wysyłki, więc
    to kilka linii na dyktowanie, nie gorąca pętla.

    ⚠️ NIGDY nie zapisujemy tu rozpoznanego tekstu w całości ani klucza API —
    treść dyktowania to prywatna wypowiedź użytkownika. Do diagnozy wystarczy
    DŁUGOŚĆ i krótki początek; klucz raportujemy wyłącznie jako „jest/brak".

    Błąd zapisu jest połykany celowo: dziennik pomocniczy nie ma prawa wywrócić
    dyktowania (byłoby to lekarstwo gorsze od choroby).
    """
    try:
        # Twardy limit rozmiaru: przy przekroczeniu zaczynamy plik od nowa. Poprzedni
        # log diagnostyczny w tym projekcie urósł kiedyś do 99 MB, stąd zapadka.
        try:
            if DICTATION_LOG.exists() and DICTATION_LOG.stat().st_size > DICTATION_LOG_MAX_BYTES:
                DICTATION_LOG.write_text(
                    f"[{datetime.now():%Y-%m-%d %H:%M:%S}] --- log przekroczyl limit, zaczynam od nowa ---\n",
                    encoding="utf-8")
        except OSError:
            pass
        with open(DICTATION_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%H:%M:%S.%f}"[:-3] + f"] {msg}\n")
    except Exception:
        pass


class STTState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


# Decyzje, jakie może podjąć kliknięcie mikrofonu.
KLIK_STOP = "stop"                       # kończymy nagrywanie i wysyłamy
KLIK_NAGRYWAJ = "nagrywaj"               # zaczynamy nagrywać
KLIK_ODBLOKUJ = "odblokuj_i_nagrywaj"    # zakleszczone „przetwarzam" → ratujemy i nagrywamy
KLIK_ZAJETE = "powiedz_zajete"           # uczciwie trwa wysyłka → powiedz to i nic nie rób
KLIK_BRAK_KLUCZA = "brak_klucza"         # zaproponuj wpisanie klucza


def decide_mic_click(is_recording: bool, is_processing: bool,
                     is_stuck: bool, has_key: bool) -> str:
    """Co ma zrobić kliknięcie mikrofonu — CZYSTA decyzja, bez Qt i bez sieci.

    Wydzielone z `MainWindow._toggle_dictation` NIE dla urody, tylko dlatego, że
    warunek stojący inline w metodzie okna nie ma czego odpytać: żaden test nie
    odróżniłby „apka świadomie odmawia" od „apka milczy". A to była właśnie
    usterka z 2026-08-29 — w stanie „przetwarzam" każde kliknięcie ginęło bez
    śladu, więc mikrofon wyglądał na całkiem zepsuty (ikona nawet nie pulsowała).
    """
    if is_recording:
        return KLIK_STOP
    if is_processing and not is_stuck:
        return KLIK_ZAJETE
    if not has_key:
        return KLIK_BRAK_KLUCZA
    if is_processing and is_stuck:
        return KLIK_ODBLOKUJ
    return KLIK_NAGRYWAJ


class STTEngine:
    """
    Speech-to-Text engine using Groq Whisper API.
    Records audio from microphone and transcribes to text.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        # Dyktowanie idzie przez bramkę AI Managera (monitorowanie zużycia),
        # nie wprost do Groq. Adres i model = jedno źródło prawdy w config.py.
        self.api_url = STT_API_URL
        self.model = STT_MODEL

        # Audio settings
        self.sample_rate = 16000
        self.channels = 1
        self.dtype = np.int16

        # Recording state
        self.state = STTState.IDLE
        self._audio_buffer = []
        self._recording_thread: Optional[threading.Thread] = None
        self._stop_recording = threading.Event()

        # ⛔ Numer podejścia + moment wejścia w „przetwarzam". Oba służą wyjściu
        # z ZAKLESZCZENIA: gdy wysyłka wisi (zerwane DNS potrafi zablokować
        # `getaddrinfo` dłużej niż limit `requests`), użytkownik może odblokować
        # dyktowanie kolejnym kliknięciem — a wynik PORZUCONEGO podejścia nie może
        # wtedy wpaść do pola poleceń pół minuty później, w środku innej pracy.
        # Stąd numer: wątek zna swój, a przy oddaniu wyniku sprawdza, czy nadal
        # jest tym bieżącym.
        self._attempt = 0
        self._processing_since: Optional[float] = None

        # Język: „auto" = nie wysyłamy pola language, bramka sama wykrywa
        # (radzi sobie z PL/EN i mieszanką). Kod ISO wymusza konkretny język.
        self.language = STT_LANGUAGE_DEFAULT

        # Callbacks
        self.on_state_changed: Optional[Callable[[STTState], None]] = None
        self.on_transcription: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_volume_level: Optional[Callable[[float], None]] = None

    def set_api_key(self, api_key: str):
        """Set Groq API key."""
        self.api_key = api_key

    def set_language(self, language: str):
        """Set transcription language (ISO code, e.g., 'pl', 'en', 'de')."""
        self.language = language

    def start_recording(self):
        """Start recording audio from microphone.

        ⚠️ Wyjście po cichu przy stanie ≠ spoczynek było PRZYCZYNĄ usterki
        „mikrofon całkiem przestał reagować" (2026-08-29): apka wisiała w stanie
        „przetwarzam", więc każde kolejne kliknięcie trafiało w ten `return` bez
        śladu i bez komunikatu. Sam `return` zostaje (dwa nagrania naraz nie mają
        sensu), ale teraz ZAWSZE zostawia wpis w dzienniku, a decyzję „to już
        zakleszczenie" podejmuje warstwa GUI przez `processing_age()`.
        """
        if self.state != STTState.IDLE:
            dictation_log(f"KLIK start ODRZUCONY: stan={self.state.value} "
                          f"wiek_przetwarzania={self.processing_age():.1f}s")
            return

        self._audio_buffer = []
        self._stop_recording.clear()

        self._set_state(STTState.RECORDING)
        dictation_log(f"NAGRYWANIE start (podejscie #{self._attempt + 1})")

        # Start recording in background thread
        self._recording_thread = threading.Thread(target=self._record_audio, daemon=True)
        self._recording_thread.start()

    def stop_recording(self):
        """Stop recording and start transcription."""
        if self.state != STTState.RECORDING:
            dictation_log(f"KLIK stop ODRZUCONY: stan={self.state.value}")
            return

        self._stop_recording.set()

        # Wait for recording thread
        if self._recording_thread and self._recording_thread.is_alive():
            self._recording_thread.join(timeout=2)

        sekundy = sum(len(b) for b in self._audio_buffer) / float(self.sample_rate or 1)
        dictation_log(f"NAGRYWANIE stop: ramek={len(self._audio_buffer)} "
                      f"dlugosc={sekundy:.1f}s klucz={'jest' if self.api_key else 'BRAK'}")

        # Process audio
        if self._audio_buffer:
            self._attempt += 1
            self._processing_since = time.monotonic()
            self._set_state(STTState.PROCESSING)

            # Transcribe in background
            threading.Thread(target=self._transcribe_audio,
                             args=(self._attempt,), daemon=True).start()
        else:
            # Cisza w buforze = mikrofon nic nie złapał. Wcześniej kończyło się to
            # BEZ JEDNEGO SŁOWA — nie do odróżnienia od udanego dyktowania, które
            # gdzieś przepadło.
            dictation_log("PUSTO: bufor bez ani jednej ramki — nie ma czego wysylac")
            self._processing_since = None
            self._set_state(STTState.IDLE)

    def processing_age(self) -> float:
        """Ile sekund apka stoi w stanie „przetwarzam" (0.0, gdy nie stoi)."""
        if self.state != STTState.PROCESSING or self._processing_since is None:
            return 0.0
        return time.monotonic() - self._processing_since

    def is_stuck(self) -> bool:
        """Czy „przetwarzam" trwa już tak długo, że to zakleszczenie, nie praca."""
        return self.processing_age() >= STT_PROCESSING_STUCK_SECS

    def force_reset(self, reason: str = ""):
        """Odblokuj dyktowanie porzucając bieżące podejście.

        Wątku wysyłki NIE da się w Pythonie ubić — zostawiamy go, żeby dogasł sam
        (skończy się na limicie albo na błędzie sieci). Bezpieczeństwo daje numer
        podejścia: `_attempt` idzie w górę, więc porzucony wątek przy powrocie
        zobaczy, że jest już nieaktualny, i NIE wpisze nic do pola poleceń.
        """
        dictation_log(f"ODBLOKOWANIE: stan={self.state.value} "
                      f"wiek_przetwarzania={self.processing_age():.1f}s powod={reason}")
        self._stop_recording.set()
        self._attempt += 1
        self._audio_buffer = []
        self._processing_since = None
        self._set_state(STTState.IDLE)

    def cancel_recording(self):
        """Cancel recording without transcription."""
        self._stop_recording.set()

        if self._recording_thread and self._recording_thread.is_alive():
            self._recording_thread.join(timeout=2)

        self._audio_buffer = []
        self._set_state(STTState.IDLE)

    def is_recording(self) -> bool:
        return self.state == STTState.RECORDING

    def is_processing(self) -> bool:
        return self.state == STTState.PROCESSING

    def get_state(self) -> STTState:
        return self.state

    def _set_state(self, state: STTState):
        self.state = state
        if self.on_state_changed:
            self.on_state_changed(state)

    def _record_audio(self):
        """Background thread for recording audio."""
        try:
            def audio_callback(indata, frames, time, status):
                if status and self.on_error:
                    self.on_error(f"Audio status: {status}")

                # Store audio data
                self._audio_buffer.append(indata.copy())

                # Calculate volume level for visualization
                if self.on_volume_level:
                    volume = np.abs(indata).mean()
                    self.on_volume_level(float(volume))

            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                callback=audio_callback,
                blocksize=1024
            ):
                while not self._stop_recording.is_set():
                    sd.sleep(100)

        except Exception as e:
            if self.on_error:
                self.on_error(f"Recording error: {str(e)}")
            self._set_state(STTState.IDLE)

    def _transcribe_audio(self, attempt: int = 0):
        """Transcribe recorded audio using Groq API.

        `attempt` = numer podejścia z chwili startu wątku. Jeśli w międzyczasie
        użytkownik odblokował dyktowanie (`force_reset`), numer się rozjedzie i
        wynik ZOSTAJE PORZUCONY — inaczej tekst sprzed minuty wpadłby do pola
        poleceń w środku innej pracy, a to gorsze niż brak tekstu.
        """
        wav_path = None
        try:
            if not self.api_key:
                raise ValueError(tr('stt_err_bad_key'))

            # Convert buffer to WAV file
            audio_data = np.concatenate(self._audio_buffer)
            wav_path = self._save_wav(audio_data)

            # Send to Groq API
            text = self._send_to_groq(wav_path)

            if attempt and attempt != self._attempt:
                dictation_log(f"WYNIK PORZUCONY: podejscie #{attempt} nieaktualne "
                              f"(biezace #{self._attempt}), znakow={len(text)}")
                return

            if text:
                dictation_log(f"ROZPOZNANO: {len(text)} znakow, poczatek={text[:40]!r}")
                if self.on_transcription:
                    self.on_transcription(text)
            else:
                # Bramka odpowiedziała 200, ale bez treści (cisza / za krótkie
                # nagranie). Wcześniej ta gałąź milczała, więc było to nieodróżnialne
                # od awarii — a lek jest inny (powiedz coś dłużej vs sprawdź sieć).
                dictation_log("PUSTA ODPOWIEDZ: bramka nie rozpoznala ani jednego slowa")
                if self.on_error:
                    self.on_error(tr('stt_err_empty'))

        except Exception as e:
            dictation_log(f"BLAD: {type(e).__name__}: {str(e)[:160]}")
            if attempt and attempt != self._attempt:
                dictation_log(f"  (blad porzuconego podejscia #{attempt} — nie zglaszam userowi)")
            elif self.on_error:
                self.on_error(str(e))

        finally:
            if wav_path and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except OSError:
                    pass
            # Stan przywracamy TYLKO jeśli to wciąż nasze podejście — inaczej
            # zdeptalibyśmy nagrywanie, które user zdążył już zacząć od nowa.
            if not attempt or attempt == self._attempt:
                self._audio_buffer = []
                self._processing_since = None
                self._set_state(STTState.IDLE)

    def _save_wav(self, audio_data: np.ndarray) -> str:
        """Save audio data to temporary WAV file."""
        temp_file = tempfile.NamedTemporaryFile(
            suffix='.wav',
            delete=False,
            prefix='claude_stt_'
        )
        temp_path = temp_file.name
        temp_file.close()

        with wave.open(temp_path, 'wb') as wav:
            wav.setnchannels(self.channels)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(self.sample_rate)
            wav.writeframes(audio_data.tobytes())

        return temp_path

    def _send_to_groq(self, audio_path: str) -> str:
        """Wyślij nagranie do bramki AI Managera i odbierz transkrypcję."""
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        with open(audio_path, 'rb') as audio_file:
            files = {
                'file': ('audio.wav', audio_file, 'audio/wav')
            }
            data = {
                'model': self.model,
                'response_format': 'text'
            }
            # „auto" (lub brak) → NIE wysyłamy pola language; bramka sama
            # wykrywa. Pusty/„auto" w polu potrafi wywalić walidację dostawcy.
            if self.language and self.language != "auto":
                data['language'] = self.language

            t0 = time.monotonic()
            dictation_log(f"WYSYLKA -> {self.api_url} (limit {STT_HTTP_TIMEOUT:.0f}s)")
            try:
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    files=files,
                    data=data,
                    # Krotka (nawiązanie połączenia, oczekiwanie na odpowiedź).
                    # ⚠️ ŻADEN z tych limitów NIE obejmuje zamiany nazwy na adres
                    # (DNS) — to robi system i przy zerwanym Wi-Fi potrafi wisieć
                    # dłużej. Dlatego limit to nie wszystko; drugą warstwą jest
                    # ręczne odblokowanie (`force_reset`) po stronie GUI.
                    timeout=(STT_HTTP_TIMEOUT, STT_HTTP_TIMEOUT),
                )
            except requests.exceptions.RequestException as e:
                dictation_log(f"ODPOWIEDZ: BRAK po {time.monotonic() - t0:.1f}s "
                              f"({type(e).__name__})")
                # Surowy komunikat biblioteki („HTTPSConnectionPool(host=…)") jest
                # dla użytkownika bezużyteczny — mówimy, co ma zrobić.
                raise Exception(tr('stt_err_network'))

            dt = time.monotonic() - t0
            dictation_log(f"ODPOWIEDZ: kod={response.status_code} po {dt:.1f}s "
                          f"znakow={len(response.text or '')}")

            if response.status_code == 200:
                return response.text.strip()

            # Czytelne komunikaty dla usera zamiast surowego kodu HTTP.
            if response.status_code == 401:
                raise Exception(tr('stt_err_bad_key'))
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                msg = tr('stt_err_rate_limit')
                if retry_after:
                    msg = f"{msg} ({retry_after}s)"
                raise Exception(msg)
            if response.status_code == 503:
                raise Exception(tr('stt_err_busy'))
            raise Exception(f"API error {response.status_code}: {response.text}")

    def get_available_devices(self) -> list:
        """Get list of available audio input devices."""
        devices = []
        for i, device in enumerate(sd.query_devices()):
            if device['max_input_channels'] > 0:
                devices.append({
                    'id': i,
                    'name': device['name'],
                    'channels': device['max_input_channels'],
                    'sample_rate': device['default_samplerate']
                })
        return devices

    def set_device(self, device_id: int):
        """Set audio input device."""
        sd.default.device = (device_id, None)


# Language codes for Whisper
WHISPER_LANGUAGES = {
    "pl": "Polish",
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "uk": "Ukrainian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "hi": "Hindi",
    "tr": "Turkish",
    "nl": "Dutch",
    "sv": "Swedish",
    "cs": "Czech",
    "sk": "Slovak",
    "el": "Greek",
    "he": "Hebrew",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "ms": "Malay",
    "ro": "Romanian",
    "hu": "Hungarian",
    "bg": "Bulgarian",
    "hr": "Croatian",
    "sl": "Slovenian",
    "et": "Estonian",
    "lv": "Latvian",
    "lt": "Lithuanian",
    "fi": "Finnish",
    "da": "Danish",
    "no": "Norwegian",
    "ca": "Catalan",
    "ga": "Irish",
    "cy": "Welsh",
    "af": "Afrikaans",
    "sw": "Swahili",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "ur": "Urdu",
    "fa": "Persian",
    "fil": "Filipino",
    "ne": "Nepali",
}
