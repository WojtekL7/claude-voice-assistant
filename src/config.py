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
    "de-DE": ("Deutsch", "German", "de-DE-KatjaNeural"),
    "fr-FR": ("Français", "French", "fr-FR-DeniseNeural"),
    "es-ES": ("Español", "Spanish", "es-ES-ElviraNeural"),
    "it-IT": ("Italiano", "Italian", "it-IT-ElsaNeural"),
    "pt-BR": ("Português (BR)", "Portuguese (BR)", "pt-BR-FranciscaNeural"),
    "pt-PT": ("Português (PT)", "Portuguese (PT)", "pt-PT-RaquelNeural"),
    "ru-RU": ("Русский", "Russian", "ru-RU-SvetlanaNeural"),
    "uk-UA": ("Українська", "Ukrainian", "uk-UA-PolinaNeural"),
    "cs-CZ": ("Čeština", "Czech", "cs-CZ-VlastaNeural"),
    "sk-SK": ("Slovenčina", "Slovak", "sk-SK-ViktoriaNeural"),
    "nl-NL": ("Nederlands", "Dutch", "nl-NL-ColetteNeural"),
    "sv-SE": ("Svenska", "Swedish", "sv-SE-SofieNeural"),
    "no-NO": ("Norsk", "Norwegian", "nb-NO-PernilleNeural"),
    "da-DK": ("Dansk", "Danish", "da-DK-ChristelNeural"),
    "fi-FI": ("Suomi", "Finnish", "fi-FI-NooraNeural"),
    "ja-JP": ("日本語", "Japanese", "ja-JP-NanamiNeural"),
    "ko-KR": ("한국어", "Korean", "ko-KR-SunHiNeural"),
    "zh-CN": ("中文 (简体)", "Chinese (Simplified)", "zh-CN-XiaoxiaoNeural"),
    "zh-TW": ("中文 (繁體)", "Chinese (Traditional)", "zh-TW-HsiaoChenNeural"),
    "ar-SA": ("العربية", "Arabic", "ar-SA-ZariyahNeural"),
    "hi-IN": ("हिन्दी", "Hindi", "hi-IN-SwaraNeural"),
    "tr-TR": ("Türkçe", "Turkish", "tr-TR-EmelNeural"),
    "el-GR": ("Ελληνικά", "Greek", "el-GR-AthinaNeural"),
    "he-IL": ("עברית", "Hebrew", "he-IL-HilaNeural"),
    "th-TH": ("ไทย", "Thai", "th-TH-PremwadeeNeural"),
    "vi-VN": ("Tiếng Việt", "Vietnamese", "vi-VN-HoaiMyNeural"),
    "id-ID": ("Bahasa Indonesia", "Indonesian", "id-ID-GadisNeural"),
    "ms-MY": ("Bahasa Melayu", "Malay", "ms-MY-YasminNeural"),
    "ro-RO": ("Română", "Romanian", "ro-RO-AlinaNeural"),
    "hu-HU": ("Magyar", "Hungarian", "hu-HU-NoemiNeural"),
    "bg-BG": ("Български", "Bulgarian", "bg-BG-KalinaNeural"),
    "hr-HR": ("Hrvatski", "Croatian", "hr-HR-GabrijelaNeural"),
    "sl-SI": ("Slovenščina", "Slovenian", "sl-SI-PetraNeural"),
    "et-EE": ("Eesti", "Estonian", "et-EE-AnuNeural"),
    "lv-LV": ("Latviešu", "Latvian", "lv-LV-EveritaNeural"),
    "lt-LT": ("Lietuvių", "Lithuanian", "lt-LT-OnaNeural"),
    "ca-ES": ("Català", "Catalan", "ca-ES-JoanaNeural"),
    "ga-IE": ("Gaeilge", "Irish", "ga-IE-OrlaNeural"),
    "cy-GB": ("Cymraeg", "Welsh", "cy-GB-NiaNeural"),
    "mt-MT": ("Malti", "Maltese", "mt-MT-GraceNeural"),
    "af-ZA": ("Afrikaans", "Afrikaans", "af-ZA-AdriNeural"),
    "sw-KE": ("Kiswahili", "Swahili", "sw-KE-ZuriNeural"),
    "am-ET": ("አማርኛ", "Amharic", "am-ET-MekdesNeural"),
    "bn-IN": ("বাংলা", "Bengali", "bn-IN-TanishaaNeural"),
    "gu-IN": ("ગુજરાતી", "Gujarati", "gu-IN-DhwaniNeural"),
    "kn-IN": ("ಕನ್ನಡ", "Kannada", "kn-IN-SapnaNeural"),
    "ml-IN": ("മലയാളം", "Malayalam", "ml-IN-SobhanaNeural"),
    "mr-IN": ("मराठी", "Marathi", "mr-IN-AarohiNeural"),
    "ta-IN": ("தமிழ்", "Tamil", "ta-IN-PallaviNeural"),
    "te-IN": ("తెలుగు", "Telugu", "te-IN-ShrutiNeural"),
    "ur-PK": ("اردو", "Urdu", "ur-PK-UzmaNeural"),
    "fa-IR": ("فارسی", "Persian", "fa-IR-DilaraNeural"),
    "fil-PH": ("Filipino", "Filipino", "fil-PH-BlessicaNeural"),
    "km-KH": ("ភាសាខ្មែរ", "Khmer", "km-KH-SresymoNeural"),
    "lo-LA": ("ລາວ", "Lao", "lo-LA-KeomanyNeural"),
    "my-MM": ("မြန်မာ", "Myanmar", "my-MM-NilarNeural"),
    "ne-NP": ("नेपाली", "Nepali", "ne-NP-HemkalaNeural"),
    "si-LK": ("සිංහල", "Sinhala", "si-LK-ThiliniNeural"),
    "zu-ZA": ("IsiZulu", "Zulu", "zu-ZA-ThandoNeural"),
}

# UI Translations
UI_TRANSLATIONS = {
    "pl-PL": {
        "app_title": "Claude Voice Assistant",
        "dictate": "Dyktuj",
        "read": "Czytaj",
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
        "pause": "Pause",
        "resume": "Resume",
        "stop": "Stop",
        "send": "Send",
        "auto_read": "Auto-read responses",
        "quick_actions": "Quick Actions",
    },
    "de-DE": {
        "app_title": "Claude Sprachassistent",
        "dictate": "Diktieren",
        "read": "Vorlesen",
        "pause": "Pause",
        "resume": "Fortsetzen",
        "stop": "Stopp",
        "send": "Senden",
        "auto_read": "Antworten automatisch vorlesen",
        "quick_actions": "Schnellaktionen",
    },
    "fr-FR": {
        "app_title": "Assistant Vocal Claude",
        "dictate": "Dicter",
        "read": "Lire",
        "pause": "Pause",
        "resume": "Reprendre",
        "stop": "Arrêter",
        "send": "Envoyer",
        "auto_read": "Lecture auto des réponses",
        "quick_actions": "Actions rapides",
    },
    "es-ES": {
        "app_title": "Asistente de Voz Claude",
        "dictate": "Dictar",
        "read": "Leer",
        "pause": "Pausa",
        "resume": "Reanudar",
        "stop": "Detener",
        "send": "Enviar",
        "auto_read": "Leer respuestas automáticamente",
        "quick_actions": "Acciones rápidas",
    },
    "it-IT": {
        "app_title": "Assistente Vocale Claude",
        "dictate": "Dettare",
        "read": "Leggi",
        "pause": "Pausa",
        "resume": "Riprendi",
        "stop": "Ferma",
        "send": "Invia",
        "auto_read": "Leggi risposte automaticamente",
        "quick_actions": "Azioni rapide",
    },
    "ru-RU": {
        "app_title": "Голосовой ассистент Claude",
        "dictate": "Диктовать",
        "read": "Читать",
        "pause": "Пауза",
        "resume": "Продолжить",
        "stop": "Стоп",
        "send": "Отправить",
        "auto_read": "Автоматически читать ответы",
        "quick_actions": "Быстрые действия",
    },
    "uk-UA": {
        "app_title": "Голосовий асистент Claude",
        "dictate": "Диктувати",
        "read": "Читати",
        "pause": "Пауза",
        "resume": "Продовжити",
        "stop": "Стоп",
        "send": "Надіслати",
        "auto_read": "Автоматично читати відповіді",
        "quick_actions": "Швидкі дії",
    },
    "ja-JP": {
        "app_title": "Claude音声アシスタント",
        "dictate": "音声入力",
        "read": "読み上げ",
        "pause": "一時停止",
        "resume": "再開",
        "stop": "停止",
        "send": "送信",
        "auto_read": "自動読み上げ",
        "quick_actions": "クイックアクション",
    },
    "zh-CN": {
        "app_title": "Claude语音助手",
        "dictate": "听写",
        "read": "朗读",
        "pause": "暂停",
        "resume": "继续",
        "stop": "停止",
        "send": "发送",
        "auto_read": "自动朗读回复",
        "quick_actions": "快捷操作",
    },
    "ko-KR": {
        "app_title": "Claude 음성 어시스턴트",
        "dictate": "받아쓰기",
        "read": "읽기",
        "pause": "일시정지",
        "resume": "계속",
        "stop": "중지",
        "send": "보내기",
        "auto_read": "자동 읽기",
        "quick_actions": "빠른 작업",
    },
    "pt-BR": {
        "app_title": "Assistente de Voz Claude",
        "dictate": "Ditar",
        "read": "Ler",
        "pause": "Pausar",
        "resume": "Retomar",
        "stop": "Parar",
        "send": "Enviar",
        "auto_read": "Ler respostas automaticamente",
        "quick_actions": "Ações rápidas",
    },
}
