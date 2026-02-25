"""
Claude Voice Assistant - Text-to-Speech Engine
Uses edge-tts for high-quality multilingual speech synthesis.
Supports pause/resume functionality.
"""
import asyncio
import tempfile
import threading
import os
from pathlib import Path
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


class TTSEngine:
    """
    Text-to-Speech engine with pause/resume support.
    Uses edge-tts for synthesis and pygame for playback.
    """

    def __init__(self):
        self.voice = "pl-PL-ZofiaNeural"
        self.rate = "+0%"
        self.volume = "+0%"

        self.state = TTSState.IDLE
        self._current_text = ""
        self._sentences: list = []
        self._current_sentence_index = 0
        self._temp_files: list = []

        # Callbacks
        self.on_state_changed: Optional[Callable[[TTSState], None]] = None
        self.on_progress: Optional[Callable[[int, int], None]] = None  # current, total
        self.on_finished: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        # Initialize pygame mixer
        pygame.mixer.init()

        # Thread control
        self._play_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused by default

    def set_voice(self, voice: str):
        """Set TTS voice."""
        self.voice = voice

    def set_rate(self, rate: str):
        """Set speech rate (e.g., '+20%', '-10%')."""
        self.rate = rate

    def set_volume(self, volume: str):
        """Set volume (e.g., '+50%', '-20%')."""
        self.volume = volume

    def speak(self, text: str):
        """Start speaking text. Splits into sentences for pause support."""
        if not text.strip():
            return

        # Stop any current playback
        self.stop()

        self._current_text = text
        self._sentences = self._split_into_sentences(text)
        self._current_sentence_index = 0

        # Reset events
        self._stop_event.clear()
        self._pause_event.set()

        # Start playback in background thread
        self._play_thread = threading.Thread(target=self._play_sentences, daemon=True)
        self._play_thread.start()

    def pause(self):
        """Pause playback."""
        if self.state == TTSState.PLAYING:
            self._pause_event.clear()
            pygame.mixer.music.pause()
            self._set_state(TTSState.PAUSED)

    def resume(self):
        """Resume playback from pause."""
        if self.state == TTSState.PAUSED:
            self._pause_event.set()
            pygame.mixer.music.unpause()
            self._set_state(TTSState.PLAYING)

    def stop(self):
        """Stop playback completely."""
        self._stop_event.set()
        self._pause_event.set()  # Unblock if paused

        pygame.mixer.music.stop()

        # Wait for thread to finish
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=2)

        # Clean up temp files
        self._cleanup_temp_files()

        self._set_state(TTSState.IDLE)

    def toggle_pause(self):
        """Toggle between pause and resume."""
        if self.state == TTSState.PLAYING:
            self.pause()
        elif self.state == TTSState.PAUSED:
            self.resume()

    def is_playing(self) -> bool:
        return self.state in [TTSState.PLAYING, TTSState.PAUSED, TTSState.GENERATING]

    def get_state(self) -> TTSState:
        return self.state

    def _set_state(self, state: TTSState):
        self.state = state
        if self.on_state_changed:
            self.on_state_changed(state)

    def _split_into_sentences(self, text: str) -> list:
        """Split text into sentences for better pause/resume experience."""
        import re

        # Split by sentence-ending punctuation
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # Filter empty sentences and strip whitespace
        sentences = [s.strip() for s in sentences if s.strip()]

        # If no sentences found, return original text as single item
        if not sentences:
            sentences = [text]

        return sentences

    def _play_sentences(self):
        """Background thread to generate and play sentences."""
        try:
            total = len(self._sentences)

            while self._current_sentence_index < total:
                if self._stop_event.is_set():
                    break

                # Wait if paused
                self._pause_event.wait()

                if self._stop_event.is_set():
                    break

                sentence = self._sentences[self._current_sentence_index]

                # Generate audio for this sentence
                self._set_state(TTSState.GENERATING)
                audio_file = self._generate_audio(sentence)

                if self._stop_event.is_set():
                    break

                if audio_file:
                    # Play the audio
                    self._set_state(TTSState.PLAYING)
                    self._play_audio_file(audio_file)

                    # Wait for playback to finish
                    while pygame.mixer.music.get_busy():
                        if self._stop_event.is_set():
                            break
                        self._pause_event.wait()  # Block if paused
                        pygame.time.wait(100)

                # Report progress
                if self.on_progress:
                    self.on_progress(self._current_sentence_index + 1, total)

                self._current_sentence_index += 1

            # Finished all sentences
            if not self._stop_event.is_set():
                self._set_state(TTSState.IDLE)
                if self.on_finished:
                    self.on_finished()

        except Exception as e:
            if self.on_error:
                self.on_error(str(e))
            self._set_state(TTSState.IDLE)

        finally:
            self._cleanup_temp_files()

    def _generate_audio(self, text: str) -> Optional[str]:
        """Generate audio file for text using edge-tts."""
        try:
            # Create temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.mp3',
                delete=False,
                prefix='claude_tts_'
            )
            temp_path = temp_file.name
            temp_file.close()

            self._temp_files.append(temp_path)

            # Run async edge-tts
            asyncio.run(self._async_generate(text, temp_path))

            return temp_path

        except Exception as e:
            if self.on_error:
                self.on_error(f"TTS generation failed: {str(e)}")
            return None

    async def _async_generate(self, text: str, output_path: str):
        """Async generation using edge-tts."""
        communicate = edge_tts.Communicate(
            text,
            self.voice,
            rate=self.rate,
            volume=self.volume
        )
        await communicate.save(output_path)

    def _play_audio_file(self, file_path: str):
        """Play audio file using pygame."""
        try:
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
        except Exception as e:
            if self.on_error:
                self.on_error(f"Playback failed: {str(e)}")

    def _cleanup_temp_files(self):
        """Remove temporary audio files."""
        for path in self._temp_files:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except:
                pass
        self._temp_files.clear()

    def get_available_voices(self) -> list:
        """Get list of available voices."""
        try:
            voices = asyncio.run(edge_tts.list_voices())
            return voices
        except:
            return []

    def __del__(self):
        """Cleanup on destruction."""
        self.stop()
        pygame.mixer.quit()
