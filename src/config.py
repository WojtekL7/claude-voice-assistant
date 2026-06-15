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
        # --- Dolny panel zakładki ---
        "input_placeholder": "Wpisz polecenie lub użyj dyktowania... (Shift+Enter = nowa linia)",
        "send_tooltip": "Wyślij (Enter)",
        "dictate_tooltip": "Dyktuj (nagrywanie głosu)",
        "read_tooltip": "Czytaj ostatnią odpowiedź",
        "pause_tooltip": "Pauza / Wznów",
        "stop_tooltip": "Zatrzymaj wszystko",
        "copy_tooltip": "Kopiuj zaznaczony tekst",
        "clear_input_tooltip": "Wyczyść pole tekstowe",
        "add_media_tooltip": "Dodaj media (zdjęcia, dokumenty, pliki)",
        "analyze_files_prefix": "Przeanalizuj te pliki:",
        "read_memory_context": "Przeczytaj pliki pamięci projektu i zapamiętaj ich zawartość jako kontekst:",
        "sent_memory_files": "Wysłano {n} plików pamięci",
        # --- Pasek menu ---
        "menu_file": "Plik",
        "menu_new_session": "Nowa sesja",
        "menu_exit": "Wyjście",
        "menu_tabs": "Zakładki",
        "menu_new_agent": "Nowy agent...",
        "menu_new_terminal": "Nowy terminal",
        "menu_manage_agents": "Zarządzaj agentami...",
        "menu_skills": "Umiejętności (Skills)...",
        "menu_mcp": "Serwery MCP...",
        "menu_skin_colors": "Zmień kolory skórki...",
        "menu_groq_api": "Klucz API Groq...",
        "menu_anthropic_api": "Klucz API Anthropic...",
        "menu_claude_command": "Komenda Claude Code...",
        "menu_manage_actions": "Zarządzaj szybkimi akcjami...",
        "menu_help": "Pomoc",
        "menu_about": "O programie",
        "menu_claude_setup": "Jak zainstalować Claude Code…",
        "menu_agents_guide": "Instrukcja: Zarządzaj agentami…",
        "menu_license": "Licencja...",
        "menu_check_updates": "Sprawdź aktualizacje",
        "menu_auto_update": "Sprawdzaj aktualizacje przy starcie",
        # --- TTS ---
        "tts_no_audio": "Brak urządzenia audio — czytanie niedostępne",
        # --- Widżet statusu (MCP / Skille / Pliki / Model / liczniki) ---
        "total_tokens_tooltip": "Łączne (przybliżone) tokeny ze wszystkich zakładek od startu aplikacji.\nWzór: liczba znaków ÷ 3,5.\nReset przy: restarcie aplikacji.\n(Indywidualny licznik agenta — po prawej, z kolorem zależnym od % okna kontekstu.)",
        "refresh_status_tooltip": "Odśwież status agenta (MCP, skille, pliki, model).\nKlika się gdy zmieniłeś coś w menedżerach lub edycji agenta.",
        "status_idle_skills": "Wybierz zakładkę agenta, aby zobaczyć liczbę aktywnych skilli.",
        "status_idle_files": "Wybierz zakładkę agenta, aby zobaczyć pliki pamięci.",
        "status_idle_model": "Wybierz zakładkę agenta, aby zobaczyć model AI.",
        "status_idle_mcp": "Wybierz zakładkę agenta, aby zobaczyć aktywne serwery MCP.",
        "mcp_checking": "Sprawdzam status MCP...",
        "mcp_dir_missing": "Katalog roboczy nie istnieje: {path}",
        "mcp_check_failed": "Nie udało się sprawdzić statusu MCP. Sprawdź czy Claude Code (komenda 'claude') jest zainstalowany.",
        "mcp_servers_title": 'Serwery MCP — agent „{agent}":',
        "mcp_connected": "Połączone:",
        "mcp_needs_auth": "Wymagają autoryzacji:",
        "mcp_failed": "Błąd:",
        "mcp_unknown": "Nieznany:",
        "mcp_active_header": "Aktywne:",
        "mcp_disabled_header": "Wyłączone dla tego agenta:",
        "mcp_click_open": "Kliknij aby otworzyć menedżer MCP.",
        "scope_user": "globalny",
        "scope_local": "lokalny",
        "scope_managed": "zarządzany",
        "skills_read_error": "Nie udało się odczytać katalogu ~/.claude/skills/",
        "skills_title": 'Skille — agent „{agent}":',
        "skills_active_n": "Aktywne ({n}):",
        "and_n_more": "… i {n} więcej",
        "no_active_skills": "(brak aktywnych skilli)",
        "skills_disabled_n": "Wyłączone dla tego agenta ({n}):",
        "skills_click_open": "Kliknij aby otworzyć menedżer skilli.",
        "files_title": 'Pliki pamięci — agent „{agent}":',
        "file_missing": "(brak pliku)",
        "no_memory_files": "(brak plików pamięci)",
        "files_click_edit": 'Kliknij aby edytować agenta (zakładka „Pliki").',
        "select_agent_tab": "Wybierz zakładkę agenta.",
        "model_title": 'Model AI — agent „{agent}":',
        "model_click_change": "Kliknij aby zmienić model w edycji agenta.",
        # --- Etykiety modeli Claude Code (lista wyboru + status) ---
        "model_default_prefix": "Domyślny — ",
        "model_default_full": "Domyślny — Opus 4.8 (z konfiguracji Claude Code)",
        "model_default_short": "Domyślny — Opus 4.8",
        "model_fable_full": "Fable 5 (najpotężniejszy, do najtrudniejszych zadań)",
        "model_fable_short": "Fable 5",
        "model_opus_full": "Opus 4.8 (najbardziej zdolny)",
        "model_opus_short": "Opus 4.8",
        "model_sonnet_full": "Sonnet 4.6 (szybki, zbalansowany)",
        "model_sonnet_short": "Sonnet 4.6",
        "model_haiku_full": "Haiku 4.5 (najszybszy)",
        "model_haiku_short": "Haiku 4.5",
        # --- Komunikaty paska statusu ---
        "status_ready": "Gotowy",
        "status_generating_speech": "Generowanie mowy...",
        "status_recording_click": "Nagrywanie... (kliknij ponownie aby zakończyć)",
        "status_processing_speech": "Przetwarzanie mowy...",
        "status_stt_error": "Błąd rozpoznawania mowy",
        "status_starting_claude": "Uruchamianie Claude Code...",
        "status_claude_started": "Claude Code uruchomiony",
        "status_claude_start_error": "Błąd uruchamiania Claude Code",
        "status_terminal_ended": "Terminal zakończony",
        "status_sent_to_terminal": "Wysłano do terminala...",
        "status_sent": "Wysłano...",
        "status_selection_no_content": "Zaznaczony tekst nie zawiera treści do odczytania",
        "status_reading_selected": "Czytam zaznaczony tekst...",
        "status_reading_last": "Czytam ostatnią odpowiedź...",
        "status_response_no_content": "Odpowiedź nie zawiera treści do odczytania",
        "status_no_response_found": "Nie znaleziono odpowiedzi do odczytania",
        "status_no_text": "Brak tekstu do odczytania",
        "status_select_text_first_terminal": "Najpierw zaznacz tekst w terminalu",
        "status_select_text_first": "Najpierw zaznacz tekst",
        "status_reading_stopped": "Zatrzymano czytanie",
        "status_quick_actions_saved": "Szybkie akcje zostały zapisane",
        "status_skin_saved": "Skórka została zapisana",
        "status_checking_updates": "Sprawdzanie aktualizacji…",
        "status_checking_updates_close": "Sprawdzanie aktualizacji przed zamknięciem…",
        "status_new_terminal": "Utworzono nowy terminal: {name}",
        "status_starting_agent": "Uruchamiam {name}...",
        "status_claude_found": "Znaleziono Claude Code: {path}",
        "status_starting_cmd": "Uruchamianie: {cmd}",
        "status_claude_started_in": "Claude Code uruchomiony w: {name}",
        "status_error": "Błąd: {error}",
        "status_reading_backlog": "Czytam {n} zaległych wypowiedzi...",
        "status_copied": "Skopiowano do schowka ({n} znaków)",
        "status_files_added": "Dodano {n} plik(ów)",
        "context_label_tooltip": "Przybliżony licznik tokenów aktywnego agenta + procent okna kontekstu modelu.\nKolory: do 50% zielony, 50–70% żółty, 70–90% pomarańczowy, ≥90% czerwony.\nAuto-compact w Claude Code: ~80–90% tej wartości.\nReset przy: /clear, /compact, restarcie aplikacji.",
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
        # --- Tab bottom panel ---
        "input_placeholder": "Type a command or use dictation... (Shift+Enter = new line)",
        "send_tooltip": "Send (Enter)",
        "dictate_tooltip": "Dictate (voice recording)",
        "read_tooltip": "Read last response",
        "pause_tooltip": "Pause / Resume",
        "stop_tooltip": "Stop everything",
        "copy_tooltip": "Copy selected text",
        "clear_input_tooltip": "Clear input field",
        "add_media_tooltip": "Add media (images, documents, files)",
        "analyze_files_prefix": "Analyze these files:",
        "read_memory_context": "Read the project memory files and remember their contents as context:",
        "sent_memory_files": "Sent {n} memory files",
        # --- Menu bar ---
        "menu_file": "File",
        "menu_new_session": "New session",
        "menu_exit": "Exit",
        "menu_tabs": "Tabs",
        "menu_new_agent": "New agent...",
        "menu_new_terminal": "New terminal",
        "menu_manage_agents": "Manage agents...",
        "menu_skills": "Skills...",
        "menu_mcp": "MCP servers...",
        "menu_skin_colors": "Change skin colors...",
        "menu_groq_api": "Groq API key...",
        "menu_anthropic_api": "Anthropic API key...",
        "menu_claude_command": "Claude Code command...",
        "menu_manage_actions": "Manage quick actions...",
        "menu_help": "Help",
        "menu_about": "About",
        "menu_claude_setup": "How to install Claude Code…",
        "menu_agents_guide": "Guide: Manage agents…",
        "menu_license": "License...",
        "menu_check_updates": "Check for updates",
        "menu_auto_update": "Check for updates on startup",
        # --- TTS ---
        "tts_no_audio": "No audio device — reading unavailable",
        # --- Status widget (MCP / Skills / Files / Model / counters) ---
        "total_tokens_tooltip": "Total (approximate) tokens across all tabs since the app started.\nFormula: character count ÷ 3.5.\nResets on: app restart.\n(Per-agent counter is on the right, colored by % of the model context window.)",
        "refresh_status_tooltip": "Refresh agent status (MCP, skills, files, model).\nClick it after you change something in the managers or agent settings.",
        "status_idle_skills": "Select an agent tab to see the number of active skills.",
        "status_idle_files": "Select an agent tab to see its memory files.",
        "status_idle_model": "Select an agent tab to see its AI model.",
        "status_idle_mcp": "Select an agent tab to see its active MCP servers.",
        "mcp_checking": "Checking MCP status...",
        "mcp_dir_missing": "Working directory does not exist: {path}",
        "mcp_check_failed": "Could not check MCP status. Make sure Claude Code (the 'claude' command) is installed.",
        "mcp_servers_title": 'MCP servers — agent "{agent}":',
        "mcp_connected": "Connected:",
        "mcp_needs_auth": "Need authorization:",
        "mcp_failed": "Error:",
        "mcp_unknown": "Unknown:",
        "mcp_active_header": "Active:",
        "mcp_disabled_header": "Disabled for this agent:",
        "mcp_click_open": "Click to open the MCP manager.",
        "scope_user": "global",
        "scope_local": "local",
        "scope_managed": "managed",
        "skills_read_error": "Could not read the ~/.claude/skills/ directory",
        "skills_title": 'Skills — agent "{agent}":',
        "skills_active_n": "Active ({n}):",
        "and_n_more": "… and {n} more",
        "no_active_skills": "(no active skills)",
        "skills_disabled_n": "Disabled for this agent ({n}):",
        "skills_click_open": "Click to open the skills manager.",
        "files_title": 'Memory files — agent "{agent}":',
        "file_missing": "(file missing)",
        "no_memory_files": "(no memory files)",
        "files_click_edit": 'Click to edit the agent (the "Files" tab).',
        "select_agent_tab": "Select an agent tab.",
        "model_title": 'AI model — agent "{agent}":',
        "model_click_change": "Click to change the model in agent settings.",
        # --- Claude Code model labels (selection list + status) ---
        "model_default_prefix": "Default — ",
        "model_default_full": "Default — Opus 4.8 (from Claude Code config)",
        "model_default_short": "Default — Opus 4.8",
        "model_fable_full": "Fable 5 (most powerful, for the hardest tasks)",
        "model_fable_short": "Fable 5",
        "model_opus_full": "Opus 4.8 (most capable)",
        "model_opus_short": "Opus 4.8",
        "model_sonnet_full": "Sonnet 4.6 (fast, balanced)",
        "model_sonnet_short": "Sonnet 4.6",
        "model_haiku_full": "Haiku 4.5 (fastest)",
        "model_haiku_short": "Haiku 4.5",
        # --- Status bar messages ---
        "status_ready": "Ready",
        "status_generating_speech": "Generating speech...",
        "status_recording_click": "Recording... (click again to finish)",
        "status_processing_speech": "Processing speech...",
        "status_stt_error": "Speech recognition error",
        "status_starting_claude": "Starting Claude Code...",
        "status_claude_started": "Claude Code started",
        "status_claude_start_error": "Error starting Claude Code",
        "status_terminal_ended": "Terminal ended",
        "status_sent_to_terminal": "Sent to terminal...",
        "status_sent": "Sent...",
        "status_selection_no_content": "The selected text has no content to read",
        "status_reading_selected": "Reading selected text...",
        "status_reading_last": "Reading the last response...",
        "status_response_no_content": "The response has no content to read",
        "status_no_response_found": "No response found to read",
        "status_no_text": "No text to read",
        "status_select_text_first_terminal": "First select text in the terminal",
        "status_select_text_first": "First select some text",
        "status_reading_stopped": "Reading stopped",
        "status_quick_actions_saved": "Quick actions saved",
        "status_skin_saved": "Skin saved",
        "status_checking_updates": "Checking for updates…",
        "status_checking_updates_close": "Checking for updates before closing…",
        "status_new_terminal": "New terminal created: {name}",
        "status_starting_agent": "Starting {name}...",
        "status_claude_found": "Found Claude Code: {path}",
        "status_starting_cmd": "Starting: {cmd}",
        "status_claude_started_in": "Claude Code started in: {name}",
        "status_error": "Error: {error}",
        "status_reading_backlog": "Reading {n} pending responses...",
        "status_copied": "Copied to clipboard ({n} chars)",
        "status_files_added": "Added {n} file(s)",
        "context_label_tooltip": "Approximate token count of the active agent + percent of the model context window.\nColors: up to 50% green, 50–70% yellow, 70–90% orange, ≥90% red.\nAuto-compact in Claude Code: ~80–90% of this value.\nResets on: /clear, /compact, app restart.",
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
        # --- Tab bottom panel ---
        "input_placeholder": "Type a command or use dictation... (Shift+Enter = new line)",
        "send_tooltip": "Send (Enter)",
        "dictate_tooltip": "Dictate (voice recording)",
        "read_tooltip": "Read last response",
        "pause_tooltip": "Pause / Resume",
        "stop_tooltip": "Stop everything",
        "copy_tooltip": "Copy selected text",
        "clear_input_tooltip": "Clear input field",
        "add_media_tooltip": "Add media (images, documents, files)",
        "analyze_files_prefix": "Analyse these files:",
        "read_memory_context": "Read the project memory files and remember their contents as context:",
        "sent_memory_files": "Sent {n} memory files",
        # --- Menu bar ---
        "menu_file": "File",
        "menu_new_session": "New session",
        "menu_exit": "Exit",
        "menu_tabs": "Tabs",
        "menu_new_agent": "New agent...",
        "menu_new_terminal": "New terminal",
        "menu_manage_agents": "Manage agents...",
        "menu_skills": "Skills...",
        "menu_mcp": "MCP servers...",
        "menu_skin_colors": "Change skin colours...",
        "menu_groq_api": "Groq API key...",
        "menu_anthropic_api": "Anthropic API key...",
        "menu_claude_command": "Claude Code command...",
        "menu_manage_actions": "Manage quick actions...",
        "menu_help": "Help",
        "menu_about": "About",
        "menu_claude_setup": "How to install Claude Code…",
        "menu_agents_guide": "Guide: Manage agents…",
        "menu_license": "Licence...",
        "menu_check_updates": "Check for updates",
        "menu_auto_update": "Check for updates on startup",
        # --- TTS ---
        "tts_no_audio": "No audio device — reading unavailable",
        # --- Status widget (MCP / Skills / Files / Model / counters) ---
        "total_tokens_tooltip": "Total (approximate) tokens across all tabs since the app started.\nFormula: character count ÷ 3.5.\nResets on: app restart.\n(Per-agent counter is on the right, coloured by % of the model context window.)",
        "refresh_status_tooltip": "Refresh agent status (MCP, skills, files, model).\nClick it after you change something in the managers or agent settings.",
        "status_idle_skills": "Select an agent tab to see the number of active skills.",
        "status_idle_files": "Select an agent tab to see its memory files.",
        "status_idle_model": "Select an agent tab to see its AI model.",
        "status_idle_mcp": "Select an agent tab to see its active MCP servers.",
        "mcp_checking": "Checking MCP status...",
        "mcp_dir_missing": "Working directory does not exist: {path}",
        "mcp_check_failed": "Could not check MCP status. Make sure Claude Code (the 'claude' command) is installed.",
        "mcp_servers_title": 'MCP servers — agent "{agent}":',
        "mcp_connected": "Connected:",
        "mcp_needs_auth": "Need authorisation:",
        "mcp_failed": "Error:",
        "mcp_unknown": "Unknown:",
        "mcp_active_header": "Active:",
        "mcp_disabled_header": "Disabled for this agent:",
        "mcp_click_open": "Click to open the MCP manager.",
        "scope_user": "global",
        "scope_local": "local",
        "scope_managed": "managed",
        "skills_read_error": "Could not read the ~/.claude/skills/ directory",
        "skills_title": 'Skills — agent "{agent}":',
        "skills_active_n": "Active ({n}):",
        "and_n_more": "… and {n} more",
        "no_active_skills": "(no active skills)",
        "skills_disabled_n": "Disabled for this agent ({n}):",
        "skills_click_open": "Click to open the skills manager.",
        "files_title": 'Memory files — agent "{agent}":',
        "file_missing": "(file missing)",
        "no_memory_files": "(no memory files)",
        "files_click_edit": 'Click to edit the agent (the "Files" tab).',
        "select_agent_tab": "Select an agent tab.",
        "model_title": 'AI model — agent "{agent}":',
        "model_click_change": "Click to change the model in agent settings.",
        # --- Claude Code model labels (selection list + status) ---
        "model_default_prefix": "Default — ",
        "model_default_full": "Default — Opus 4.8 (from Claude Code config)",
        "model_default_short": "Default — Opus 4.8",
        "model_fable_full": "Fable 5 (most powerful, for the hardest tasks)",
        "model_fable_short": "Fable 5",
        "model_opus_full": "Opus 4.8 (most capable)",
        "model_opus_short": "Opus 4.8",
        "model_sonnet_full": "Sonnet 4.6 (fast, balanced)",
        "model_sonnet_short": "Sonnet 4.6",
        "model_haiku_full": "Haiku 4.5 (fastest)",
        "model_haiku_short": "Haiku 4.5",
        # --- Status bar messages ---
        "status_ready": "Ready",
        "status_generating_speech": "Generating speech...",
        "status_recording_click": "Recording... (click again to finish)",
        "status_processing_speech": "Processing speech...",
        "status_stt_error": "Speech recognition error",
        "status_starting_claude": "Starting Claude Code...",
        "status_claude_started": "Claude Code started",
        "status_claude_start_error": "Error starting Claude Code",
        "status_terminal_ended": "Terminal ended",
        "status_sent_to_terminal": "Sent to terminal...",
        "status_sent": "Sent...",
        "status_selection_no_content": "The selected text has no content to read",
        "status_reading_selected": "Reading selected text...",
        "status_reading_last": "Reading the last response...",
        "status_response_no_content": "The response has no content to read",
        "status_no_response_found": "No response found to read",
        "status_no_text": "No text to read",
        "status_select_text_first_terminal": "First select text in the terminal",
        "status_select_text_first": "First select some text",
        "status_reading_stopped": "Reading stopped",
        "status_quick_actions_saved": "Quick actions saved",
        "status_skin_saved": "Skin saved",
        "status_checking_updates": "Checking for updates…",
        "status_checking_updates_close": "Checking for updates before closing…",
        "status_new_terminal": "New terminal created: {name}",
        "status_starting_agent": "Starting {name}...",
        "status_claude_found": "Found Claude Code: {path}",
        "status_starting_cmd": "Starting: {cmd}",
        "status_claude_started_in": "Claude Code started in: {name}",
        "status_error": "Error: {error}",
        "status_reading_backlog": "Reading {n} pending responses...",
        "status_copied": "Copied to clipboard ({n} chars)",
        "status_files_added": "Added {n} file(s)",
        "context_label_tooltip": "Approximate token count of the active agent + percent of the model context window.\nColours: up to 50% green, 50–70% yellow, 70–90% orange, ≥90% red.\nAuto-compact in Claude Code: ~80–90% of this value.\nResets on: /clear, /compact, app restart.",
    },
}

# ===== Centralny tłumacz UI (runtime) =====
# `_CURRENT_UI_LANGUAGE` to JEDYNE źródło prawdy o języku interfejsu w czasie
# działania aplikacji. Ustawia je MainWindow przy starcie (wykrycie/odczyt z
# configu) i przy zmianie w menu. Dzięki funkcji modułowej `t()` także osobne
# klasy okien dialogowych tłumaczą napisy bez dostępu do MainWindow.
DEFAULT_UI_LANGUAGE = "pl-PL"
_CURRENT_UI_LANGUAGE = DEFAULT_UI_LANGUAGE


def set_ui_language(code: str) -> None:
    """Ustaw globalny język interfejsu (tylko jeśli mamy dla niego tłumaczenia)."""
    global _CURRENT_UI_LANGUAGE
    if code in UI_TRANSLATIONS:
        _CURRENT_UI_LANGUAGE = code


def current_ui_language() -> str:
    """Bieżący język interfejsu (kod, np. 'pl-PL')."""
    return _CURRENT_UI_LANGUAGE


def t(key: str) -> str:
    """Tłumaczenie napisu UI dla bieżącego języka.

    Kolejność awaryjna (fallback): bieżący język → en-US → pl-PL → sam klucz.
    Wzorce z nawiasami klamrowymi (np. '{n}') wołający robi `.format(...)` sam.
    """
    lang = _CURRENT_UI_LANGUAGE
    if lang in UI_TRANSLATIONS and key in UI_TRANSLATIONS[lang]:
        return UI_TRANSLATIONS[lang][key]
    if key in UI_TRANSLATIONS.get("en-US", {}):
        return UI_TRANSLATIONS["en-US"][key]
    if key in UI_TRANSLATIONS.get("pl-PL", {}):
        return UI_TRANSLATIONS["pl-PL"][key]
    return key


def detect_system_language() -> str:
    """Wykryj język interfejsu przy PIERWSZYM starcie (brak zapisanego configu).

    Reguła (ustalona z użytkownikiem): system angielski → en-US/en-GB,
    każdy inny → pl-PL. Czyta `locale` oraz zmienne środowiskowe LANG/LC_*.
    """
    import locale
    raw = ""
    try:
        raw = locale.getlocale()[0] or ""
    except Exception:
        raw = ""
    if not raw:
        for env in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
            val = os.environ.get(env, "")
            if val:
                raw = val
                break
    if not raw:
        try:
            raw = locale.getdefaultlocale()[0] or ""
        except Exception:
            raw = ""
    norm = raw.replace("_", "-").lower()
    if norm.startswith("en"):
        return "en-GB" if ("-gb" in norm or "-uk" in norm) else "en-US"
    return DEFAULT_UI_LANGUAGE


def model_label(key: str) -> str:
    """Pełna etykieta modelu Claude Code w bieżącym języku (lista wyboru/tooltip).

    Fallback dla nieznanych kluczy (np. własny model) → słownik CLAUDE_MODELS."""
    tkey = f"model_{key}_full"
    val = t(tkey)
    return val if val != tkey else CLAUDE_MODELS.get(key, key)


def model_label_short(key: str) -> str:
    """Krótka etykieta modelu (pasek statusu, panel agentów)."""
    tkey = f"model_{key}_short"
    val = t(tkey)
    return val if val != tkey else CLAUDE_MODELS_SHORT.get(key, key)


def model_default_prefix() -> str:
    """Prefiks 'Domyślny — ' / 'Default — ' (do skracania etykiety na pasku statusu)."""
    return t("model_default_prefix")


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
