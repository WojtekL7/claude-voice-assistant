"""
Claude Voice Assistant - Speech-to-Text Engine
Uses Groq Whisper API for fast, accurate transcription.
"""
import io
import wave
import tempfile
import threading
import os
from typing import Optional, Callable
from enum import Enum

import numpy as np
import sounddevice as sd
import requests


class STTState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


class STTEngine:
    """
    Speech-to-Text engine using Groq Whisper API.
    Records audio from microphone and transcribes to text.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.api_url = "https://api.groq.com/openai/v1/audio/transcriptions"

        # Audio settings
        self.sample_rate = 16000
        self.channels = 1
        self.dtype = np.int16

        # Recording state
        self.state = STTState.IDLE
        self._audio_buffer = []
        self._recording_thread: Optional[threading.Thread] = None
        self._stop_recording = threading.Event()

        # Language (for Whisper)
        self.language = "pl"  # Default Polish

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
        """Start recording audio from microphone."""
        if self.state != STTState.IDLE:
            return

        self._audio_buffer = []
        self._stop_recording.clear()

        self._set_state(STTState.RECORDING)

        # Start recording in background thread
        self._recording_thread = threading.Thread(target=self._record_audio, daemon=True)
        self._recording_thread.start()

    def stop_recording(self):
        """Stop recording and start transcription."""
        if self.state != STTState.RECORDING:
            return

        self._stop_recording.set()

        # Wait for recording thread
        if self._recording_thread and self._recording_thread.is_alive():
            self._recording_thread.join(timeout=2)

        # Process audio
        if self._audio_buffer:
            self._set_state(STTState.PROCESSING)

            # Transcribe in background
            threading.Thread(target=self._transcribe_audio, daemon=True).start()
        else:
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

    def _transcribe_audio(self):
        """Transcribe recorded audio using Groq API."""
        try:
            if not self.api_key:
                raise ValueError("Groq API key not set")

            # Convert buffer to WAV file
            audio_data = np.concatenate(self._audio_buffer)
            wav_path = self._save_wav(audio_data)

            try:
                # Send to Groq API
                text = self._send_to_groq(wav_path)

                if text and self.on_transcription:
                    self.on_transcription(text)

            finally:
                # Clean up temp file
                if os.path.exists(wav_path):
                    os.remove(wav_path)

        except Exception as e:
            if self.on_error:
                self.on_error(f"Transcription error: {str(e)}")

        finally:
            self._audio_buffer = []
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
        """Send audio file to Groq API for transcription."""
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        with open(audio_path, 'rb') as audio_file:
            files = {
                'file': ('audio.wav', audio_file, 'audio/wav')
            }
            data = {
                'model': 'whisper-large-v3',
                'language': self.language,
                'response_format': 'text'
            }

            response = requests.post(
                self.api_url,
                headers=headers,
                files=files,
                data=data,
                timeout=30
            )

            if response.status_code == 200:
                return response.text.strip()
            else:
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
