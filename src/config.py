"""
Claude Voice Assistant - Configuration
"""
import os
from pathlib import Path

# Application Info
APP_NAME = "Claude Voice Assistant"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Fulfillment Polska"

# Paths
BASE_DIR = Path(__file__).parent.parent
SRC_DIR = BASE_DIR / "src"
ASSETS_DIR = SRC_DIR / "assets"
I18N_DIR = SRC_DIR / "i18n"
CONFIG_DIR = Path.home() / ".claude-voice-assistant"
CONFIG_FILE = CONFIG_DIR / "config.json"
QUICK_ACTIONS_FILE = CONFIG_DIR / "quick_actions.json"
LICENSE_FILE = CONFIG_DIR / "license.key"
AGENTS_FILE = CONFIG_DIR / "agents.json"
MEMORY_PROJECTS_FILE = CONFIG_DIR / "memory_projects.json"

# Ensure config directory exists
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# License Server (will be changed to custom domain later)
LICENSE_SERVER_URL = "https://license.srv1251441.hstgr.cloud/api"
TRIAL_DAYS = 30

# Claude Code
CLAUDE_COMMAND = "/usr/bin/claude"  # Full path to Claude Code CLI

# Groq API (for Speech-to-Text)
GROQ_API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# TTS Settings
TTS_DEFAULT_VOICE = "pl-PL-ZofiaNeural"
TTS_DEFAULT_RATE = "+0%"
TTS_DEFAULT_VOLUME = "+0%"

# Audio Settings
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1

# UI Settings
WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 600
FONT_SIZE_CONVERSATION = 12
FONT_SIZE_INPUT = 11

# Default Quick Actions
DEFAULT_QUICK_ACTIONS = [
    {"label": "Napraw błąd", "command": "Napraw błąd w tym kodzie"},
    {"label": "Wyjaśnij kod", "command": "Wyjaśnij co robi ten kod"},
    {"label": "Zrób commit", "command": "Zrób commit z opisem zmian"},
    {"label": "Napisz testy", "command": "Napisz testy jednostkowe dla tego kodu"},
    {"label": "Zoptymalizuj", "command": "Zoptymalizuj ten kod"},
    {"label": "Dodaj komentarze", "command": "Dodaj komentarze do tego kodu"},
]

# Supported Languages for TTS (edge-tts)
# Format: {code: (name_native, name_english, voice_id)}
SUPPORTED_LANGUAGES = {
    "pl-PL": ("Polski", "Polish", "pl-PL-ZofiaNeural"),
    "en-US": ("English (US)", "English (US)", "en-US-JennyNeural"),
    "en-GB": ("English (UK)", "English (UK)", "en-GB-SoniaNeural"),
}

# UI Translations
UI_TRANSLATIONS = {
    "pl-PL": {
        "app_title": "Claude Voice Assistant",
        "dictate": "Dyktuj",
        "read": "Czytaj",
        "copy": "Kopiuj",
        "clear_input": "Wyczyść pole",
        "add_media": "Dodaj media",
        "pause": "Pauza",
        "resume": "Wznów",
        "stop": "Stop",
        "send": "Wyślij",
        "auto_read": "Auto-czytaj odpowiedzi",
        "quick_actions": "Szybkie akcje",
        "add_action": "Dodaj własną...",
        "settings": "Ustawienia",
        "language": "Język",
        "voice": "Głos",
        "speed": "Szybkość",
        "recording": "Nagrywanie...",
        "processing": "Przetwarzanie...",
        "reading": "Czytam...",
        "paused": "Wstrzymano",
        "trial_days_left": "Pozostało dni próbnych",
        "buy_license": "Kup licencję",
        "enter_license": "Wprowadź klucz licencji",
        "license_valid": "Licencja aktywna",
        "license_expired": "Licencja wygasła",
    },
    "en-US": {
        "app_title": "Claude Voice Assistant",
        "dictate": "Dictate",
        "read": "Read",
        "copy": "Copy",
        "clear_input": "Clear input",
        "add_media": "Add media",
        "pause": "Pause",
        "resume": "Resume",
        "stop": "Stop",
        "send": "Send",
        "auto_read": "Auto-read responses",
        "quick_actions": "Quick Actions",
        "add_action": "Add custom...",
        "settings": "Settings",
        "language": "Language",
        "voice": "Voice",
        "speed": "Speed",
        "recording": "Recording...",
        "processing": "Processing...",
        "reading": "Reading...",
        "paused": "Paused",
        "trial_days_left": "Trial days left",
        "buy_license": "Buy license",
        "enter_license": "Enter license key",
        "license_valid": "License active",
        "license_expired": "License expired",
    },
    "en-GB": {
        "app_title": "Claude Voice Assistant",
        "dictate": "Dictate",
        "read": "Read",
        "copy": "Copy",
        "clear_input": "Clear input",
        "add_media": "Add media",
        "pause": "Pause",
        "resume": "Resume",
        "stop": "Stop",
        "send": "Send",
        "auto_read": "Auto-read responses",
        "quick_actions": "Quick Actions",
        "add_action": "Add custom...",
        "settings": "Settings",
        "language": "Language",
        "voice": "Voice",
        "speed": "Speed",
        "recording": "Recording...",
        "processing": "Processing...",
        "reading": "Reading...",
        "paused": "Paused",
        "trial_days_left": "Trial days left",
        "buy_license": "Buy licence",
        "enter_license": "Enter licence key",
        "license_valid": "Licence active",
        "license_expired": "Licence expired",
    },
}

# Default Agents Configuration
DEFAULT_AGENTS = [
    {
        "id": "default-agent",
        "name": "Główny",
        "auto_start": True,
        "memory_project_id": None,
        "working_directory": str(Path.home()),
        "splitter_sizes": [600, 150],  # [terminal_height, bottom_panel_height]
    }
]

# Default Memory Projects Configuration
DEFAULT_MEMORY_PROJECTS = []

# Memory file extensions
MEMORY_FILE_EXTENSIONS = [".md", ".txt", ".json"]
