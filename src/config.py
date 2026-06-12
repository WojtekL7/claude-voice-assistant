"""
Claude Voice Assistant - Configuration
"""
import os
import sys
from pathlib import Path

# Application Info
APP_NAME = "Claude Voice Assistant"
# APP_VERSION — JEDYNE źródło prawdy o wersji. Używane przez auto-aktualizację
# (M3) do porównania z wersją w pliku appcast na serwerze. Podbijaj przy każdym
# wydaniu (semver: MAJOR.MINOR.PATCH).
APP_VERSION = "1.0.15"
APP_AUTHOR = "Fulfillment Polska"

# Paths
# Wersja spakowana (PyInstaller, .app/.exe): zasoby leżą w katalogu wypakowania
# (sys._MEIPASS); datas w packaging/macos/*.spec dokładają je pod 'src/...'.
# Tryb developerski (uruchomienie z kodu): BASE_DIR = korzeń repo. Przełączka
# włącza się WYŁĄCZNIE w buildzie — na Linuksie z venv nic nie zmienia.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
else:
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

# ===== Auto-aktualizacja (M3) =====
# Feed z najnowszymi wersjami per platforma. Format: packaging/appcast.example.json.
# PUBLICZNY (bez hasła) — auto-aktualizator pobiera bez logowania. Leży w
# /opt/cva-web/html/cva/ na VPS; ścieżka /cva ma osobny router traefik bez
# basicauth (reszta strony pobierania zostaje za hasłem).
UPDATE_APPCAST_URL = "https://pobierz.srv1251441.hstgr.cloud/cva/appcast.json"
# Klucz publiczny Ed25519 (base64) do weryfikacji podpisu paczek aktualizacji.
# PUSTY = weryfikacja podpisu wyłączona (sha256 i tak jest obowiązkowe). Włączymy
# razem z UPDATE_SIGN w packaging/signing.conf, gdy paczki będą podpisywane.
UPDATE_PUBLIC_KEY = ""
# Katalog pobranych paczek aktualizacji.
UPDATE_DOWNLOAD_DIR = CONFIG_DIR / "updates"

# Instrukcje instalacji „krok po kroku" (te same podstrony co na stronie
# pobierania). Leżą pod /cva — PUBLICZNE (bez hasła), więc aplikacja może je
# otwierać u użytkownika bez logowania. Plik per system: instrukcja-<os>.html
# (os = platform_utils.os_key(): windows / macos / linux).
INSTALL_GUIDE_BASE_URL = "https://pobierz.srv1251441.hstgr.cloud/cva/"

# Claude Code — ścieżka rozstrzygana wieloplatformowo (Linux/macOS/Windows):
# PATH, potem typowe lokalizacje (~/.local/bin, Homebrew, npm). Fallback: 'claude'.
try:
    from core.platform_utils import find_claude_command
    CLAUDE_COMMAND = find_claude_command()
except Exception:
    CLAUDE_COMMAND = "claude"

# Claude Code models available for selection per agent.
# Key is passed to `claude --model <key>`. "default" means: launch without --model
# (Claude Code uses its own configured default).
# Version numbers in labels are informational — aliases (sonnet/opus/haiku)
# always resolve to the newest available version on Claude Code's side.
CLAUDE_MODELS = {
    "default": "Domyślny — Opus 4.8 (z konfiguracji Claude Code)",
    "fable": "Fable 5 (najpotężniejszy, do najtrudniejszych zadań)",
    "opus": "Opus 4.8 (najbardziej zdolny)",
    "sonnet": "Sonnet 4.6 (szybki, zbalansowany)",
    "haiku": "Haiku 4.5 (najszybszy)",
}
# Short labels used in compact lists (e.g. agent manager).
CLAUDE_MODELS_SHORT = {
    "default": "Domyślny — Opus 4.8",
    "fable": "Fable 5",
    "opus": "Opus 4.8",
    "sonnet": "Sonnet 4.6",
    "haiku": "Haiku 4.5",
}
# Fallback for agents that don't have a `model` field saved (backward compat).
DEFAULT_AGENT_MODEL = "default"
# Pre-selected model when the user creates a NEW agent.
NEW_AGENT_DEFAULT_MODEL = "opus"

# Okna kontekstu modeli (w tokenach). Claude Code uruchamia auto-compact
# przy ~80–90% tej wartości — wartości używane do koloryzacji licznika
# tokenów per-zakładka w pasku statusu.
# "default" w Claude Code rozwiązuje się na Opus 4.8 z 1M oknem kontekstu.
CLAUDE_MODEL_CONTEXT_LIMITS = {
    "default": 1_000_000,
    "fable":   1_000_000,
    "opus":    1_000_000,
    "sonnet":    200_000,
    "haiku":     200_000,
}

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

# Ochrona pamięci: każda AKTYWNA zakładka-agent uruchamia osobny proces
# `claude` (Node.js) zużywający ~1.5–2 GB RAM. Na słabszych maszynach kilku
# agentów naraz wyczerpuje RAM i zawiesza pulpit. Po przekroczeniu tego progu
# apka OSTRZEGA przed uruchomieniem kolejnego agenta (nie blokuje twardo).
MAX_ACTIVE_AGENTS = 3

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

# Domyślne proporcje rozdzielacza terminal/panel dolny: [terminal, panel].
# QSplitter skaluje je proporcjonalnie do wysokości okna — ~89/11 daje cienki
# panel dolny (suwak nisko). Nowe zakładki dziedziczą proporcje z aktywnej
# zakładki; ta stała to fallback dla świeżej instalacji.
DEFAULT_SPLITTER_SIZES = [1500, 190]

# Default Agents Configuration
DEFAULT_AGENTS = [
    {
        "id": "default-agent",
        "name": "Główny",
        "auto_start": True,
        "memory_files": [],  # list of file paths to load as context
        "working_directory": str(Path.home()),
        "splitter_sizes": list(DEFAULT_SPLITTER_SIZES),
    }
]

# Default Memory Projects Configuration
DEFAULT_MEMORY_PROJECTS = []

# Memory file extensions
MEMORY_FILE_EXTENSIONS = [".md", ".txt", ".json"]
