"""
Vibe Coding Assistant - Configuration
"""
import os
import re
import sys
from pathlib import Path

# Application Info
APP_NAME = "Vibe Coding Assistant"
# APP_VERSION — JEDYNE źródło prawdy o wersji. Używane przez auto-aktualizację
# (M3) do porównania z wersją w pliku appcast na serwerze. Podbijaj przy każdym
# wydaniu (semver: MAJOR.MINOR.PATCH).
APP_VERSION = "1.0.28"
APP_AUTHOR = "Fulfillment Polska"

# Tryb deweloperski — uruchomienie WPROST z kodu (`python3 src/main.py`).
# Wersje spakowane (AppImage/.dmg/.exe via PyInstaller) mają `sys.frozen=True`;
# tryb z kodu go nie ma. Służy do ODRÓŻNIENIA okna dev od wersji wydanej:
# osobny WM_CLASS (pasek zadań Linuksa nie skleja obu w jedną ikonę) + dopisek
# „— DEV" w tytule. Wersji wydanej NIE dotyczy (oba poniżej puste/bazowe).
IS_DEV = not getattr(sys, "frozen", False)
APP_WM_CLASS = "vibe-coding-assistant" + ("-beta" if IS_DEV else "")
APP_TITLE_SUFFIX = "  —  beta" if IS_DEV else ""

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
CONFIG_DIR = Path.home() / ".vibe-coding-assistant"
# Migracja ustawień ze starej nazwy (Vibe Coding Assistant → Vibe Coding Assistant).
# Przy pierwszym starcie nowej wersji przenosimy istniejącą konfigurację (klucz Groq,
# język, skórki, agenci, licencja), żeby obecni użytkownicy NIC nie stracili.
# Jednorazowe i bezpieczne: tylko gdy nowy folder jeszcze nie istnieje.
_OLD_CONFIG_DIR = Path.home() / ".claude-voice-assistant"
if not CONFIG_DIR.exists() and _OLD_CONFIG_DIR.is_dir():
    try:
        import shutil
        shutil.copytree(_OLD_CONFIG_DIR, CONFIG_DIR)
    except Exception:
        pass
CONFIG_FILE = CONFIG_DIR / "config.json"
QUICK_ACTIONS_FILE = CONFIG_DIR / "quick_actions.json"
LICENSE_FILE = CONFIG_DIR / "license.key"
AGENTS_FILE = CONFIG_DIR / "agents.json"
MEMORY_PROJECTS_FILE = CONFIG_DIR / "memory_projects.json"

# ===== „Czarna skrzynka" terminala (diagnostyka crashu `claude`) =====
# Pasywne nagrywanie OSTATNICH bajtów wyjścia terminala w pamięci (ring-bufor)
# per zakładka. Gdy w strumieniu pojawi się PODPIS ekranu ratunkowego Claude
# Code (`claude --resume <uuid>`) — zrzucamy bufor do pliku. Powód: w PTY
# stdout+stderr są zlane, a `claude` to dziecko powłoki (jego crash NIE odpala
# sygnału `finished` backendu), więc inaczej stack trace bezpowrotnie się
# przewija. Logi TYLKO lokalnie, w katalogu konfiguracji.
CRASH_LOG_DIR = CONFIG_DIR / "crash-logs"
# Ile ostatnich bajtów wyjścia terminala trzymać w pamięci na zrzut (~64 KB
# spokojnie obejmuje ekran ratunkowy + poprzedzający stack trace).
TERMINAL_CAPTURE_BYTES = 65536
# Ile plików zrzutu zachować (najstarsze kasowane przy nowym zrzucie).
CRASH_LOG_KEEP = 20
# Minimalny odstęp [s] między kolejnymi zrzutami tej samej zakładki — debounce,
# by powtarzające się przerysowania ekranu ratunkowego nie tworzyły serii plików.
CRASH_LOG_DEBOUNCE_SECS = 30
# Sprzątanie zrzutów WIEKIEM (uzupełnia CRASH_LOG_KEEP, które liczy tylko SZTUKI
# i tylko przy nowym zrzucie — bez tego zrzuty z zamkniętej sprawy leżą latami,
# a pliki `terminal-glitch-*.log` nie były sprzątane w ogóle).
CRASH_LOG_MAX_AGE_DAYS = 30
# ...ale NIGDY nie zostawiaj katalogu pustego: po długim spokoju kasowanie wiekiem
# wywaliłoby CAŁĄ historię, a przy następnym crashu nie ma z czym porównać.
CRASH_LOG_AGE_FLOOR = 5

# --- Limity rosnących logów (sprawdzane przy starcie) ------------------------
# `webterminal.log` pilnuje się sam (web_terminal.py), `login-events.log` też
# (LOGIN_EVENT_LOG_MAX_BYTES). `tts.log` NIE miał żadnego limitu — rósł w
# nieskończoność, a to ten sam wzorzec co „diagnostyka tymczasowa urosła do
# 99 MB". Format: nazwa pliku w katalogu konfiguracji → limit w bajtach.
CAPPED_LOG_FILES = {"tts.log": 512 * 1024}

# --- Nadganianie lektora (auto-czytanie) -------------------------------------
# Agent potrafi pisać SZYBCIEJ, niż lektor mówi (mowa ~15 znaków/s). Kolejka
# jest FIFO i nic nie pomija, więc przy pracowitym agencie rośnie bez końca:
# zmierzone 2026-07-21 — 4 wypowiedzi (~3200 znaków ≈ 3,5 min mowy) w ciągu
# 2 minut → lektor czytał wypowiedź sprzed dwóch minut, choć na ekranie była
# już następna. User zgłaszał to jako „czyta przedostatnią wypowiedź", choć
# wybór wypowiedzi był prawidłowy — spóźniało się samo czytanie.
# Gdy zaległość przekroczy ten próg, przeskakujemy do NAJNOWSZEJ wypowiedzi.
TTS_CATCHUP_CHARS = 900          # ≈ 1 minuta mowy

# --- Wyścig o odświeżenie tokenu („Please run /login") -----------------------
# Wszystkie zakładki dzielą JEDEN plik poświadczeń, a bilet do odnowienia
# (refreshToken) jest jednorazowy: pierwsza zakładka go zużywa i zapisuje nowy
# komplet, pozostałe trzymają bilet, który właśnie stracił ważność → dostają
# „Please run /login", choć user NIE jest wylogowany. Zmierzone 2026-07-20:
# 5 odmów w 4 zakładkach w ciągu 5 minut wokół wygaśnięcia, plik poświadczeń
# odnowiony 8 minut po pierwszej odmowie i ważny kolejne 8 godzin.
# ETAP 1 (teraz): tylko OBSERWACJA — zapis zdarzenia + komunikat na pasku.
# Automatycznego restartu zakładki świadomie NIE robimy, dopóki nie potwierdzimy
# na żywych danych, że rozpoznanie „wyścig vs prawdziwe wylogowanie" jest pewne
# (błąd w tę stronę = pętla restartów przy realnym wylogowaniu).
# --- Chmura (Faza 1: „mózg" agenta na Dysku Google) -------------------------
# Dane klienta OAuth (z konsoli Google, wgrywane RAZ przez usera) i token
# dostępu trzymamy WYŁĄCZNIE lokalnie, z prawami 600 — nigdy w paczce „mózgu",
# nigdy w repo. Zakres uprawnień: `drive.file` = apka widzi TYLKO pliki, które
# sama utworzyła (żadnego dostępu do reszty Dysku usera).
CLOUD_CLIENT_FILE = CONFIG_DIR / "cloud-google-client.json"
CLOUD_TOKEN_FILE = CONFIG_DIR / "cloud-google-token.json"
# Hasło szyfrujące paczkę — zapamiętane na TYM komputerze, żeby kolejne wysyłki
# nie wymagały przepisywania kodu. Nie osłabia ochrony: kto ma dostęp do tego
# konta, ma i tak dostęp do samych agentów; hasło chroni paczkę leżącą na CUDZYM
# serwerze. Na nowym komputerze user wpisuje kod z kartki.
CLOUD_PASSPHRASE_FILE = CONFIG_DIR / "cloud-passphrase.txt"
CLOUD_FOLDER_NAME = "Vibe Coding Assistant"
CLOUD_BUNDLE_NAME = "brain.vcabundle"

LOGIN_EVENT_LOG = CONFIG_DIR / "login-events.log"
LOGIN_EVENT_LOG_MAX_BYTES = 64 * 1024     # twardy limit — log ma nie puchnąć
LOGIN_VERDICT_INTERVAL_SECS = 60          # co ile sprawdzać, czy ktoś odnowił
LOGIN_VERDICT_MAX_CHECKS = 12             # ~12 min (zmierzony przypadek: 8 min)


def tts_should_catch_up(pending_chars: int) -> bool:
    """Czy lektor jest na tyle w tyle, że warto przeskoczyć do najnowszej?

    Wydzielone z GUI, żeby dało się przetestować bez uruchamiania okna.
    """
    return pending_chars > TTS_CATCHUP_CHARS


# --- Wysyłka plików pamięci przy starcie zakładki ----------------------------
# Wiadomość „Przeczytaj pliki pamięci…" wolno wpisywać WYŁĄCZNIE do gotowego
# Claude Code. Gdy tekst i Enter trafią do procesu, który jeszcze wstaje i nie
# czyta wejścia, bufor PTY sklei oba zapisy w JEDEN odczyt → Claude bierze
# całość za WKLEJKĘ, a Enter staje się zwykłą nową linią: tekst wisi w polu
# i nic się nie wysyła (objaw: „zakładka nie wczytała plików pamięci”).
# Odtworzone sondą PTY 2026-07-17: pisanie w trakcie rozruchu = 2/2 porażki,
# pisanie do gotowego Claude = OK. Dotykało zakładek startujących jako OSTATNIE
# (najdłużej wstają, bo konkurują o procesor z resztą).
# Gotowość = baner Claude Code w wyjściu ORAZ cisza terminala (koniec rysowania
# ekranu startowego). Cisza liczona czujnikiem, który ignoruje migającą kropkę
# bezczynności — ten sam, co przy fladze „agent czeka”.
MEMORY_READY_MARKER = "Claude Code"
MEMORY_READY_QUIET_SECS = 1.5
MEMORY_READY_POLL_MS = 500
# Bezpiecznik: gdyby baner nigdy nie przyszedł (np. przyszła wersja Claude Code
# zmieni ekran startowy), po tym czasie wysyłamy po staremu. Najgorszy możliwy
# skutek = dzisiejsze zachowanie, nigdy „nie wysyła wcale”.
MEMORY_READY_TIMEOUT_SECS = 60.0
# Enter musi być OSOBNYM zapisem, wyraźnie oddzielonym od tekstu (50 ms było za
# mało — patrz wyżej). Do gotowego Claude wystarcza mniej, pół sekundy to zapas.
MEMORY_ENTER_DELAY_MS = 500

# 🔊 „czytaj ostatnią” — okno, w którym EKRAN WYPRZEDZA DZIENNIK.
# Claude Code dopisuje wypowiedź do pliku sesji dopiero, gdy skończy ją pisać
# w całości (zmierzone 2026-07-22 na żywej rozmowie: 13,9 / 14,8 / 16,2 s dla
# odpowiedzi 1,7–2,4 tys. znaków; wpis pojawia się 1–3 s po jej dokończeniu).
# Na ekranie widać ją od pierwszego zdania, więc klik w tym oknie czytał
# POPRZEDNIĄ wypowiedź (zgłoszenie usera: „czyta przedostatnią, w ~50%”).
# Lek: gdy agent jest nam WINIEN odpowiedź, CZEKAMY na nią zamiast czytać starą.
#
# ⚠️ RUNDA 3 (2026-07-25) — DWIE poprzednie próby pytały o to samo, złe pytanie.
# Runda 1 (próg 2,0 s) i runda 2 (4,0 s + licznik znaków strumienia) mierzyły
# „czy z terminala leci tekst". Zmierzone na żywym dzienniku CRM w chwili
# zgłoszenia: po odpowiedzi usera (11:20:13) agent MYŚLAŁ 30 s (11:20:43),
# a tekst dopisał o 11:20:47. Przez te 30 s w pliku NIE MA ani jednego wpisu,
# a terminal pokazuje tylko drobną animację (kilkadziesiąt znaków, poniżej progu
# 200/2 s) → strażnik orzekał „nic nie leci", karencja 4 s mijała w środku
# myślenia i apka czytała wypowiedź sprzed 6 minut. ŻADEN próg liczony ze
# strumienia znaków tej dziury nie zamknie — bo w niej naprawdę nic nie leci.
# Decyzję podejmuje teraz STRUKTURA TURY z dziennika (TranscriptReader.turn_snapshot);
# terminal służy już tylko do rozpoznania „agent przestał pracować bez pisania".
READ_LAST_BUSY_SECS = 4.0          # ruch w terminalu świeższy niż to = agent pracuje
READ_LAST_WAIT_POLL_MS = 500       # co ile sprawdzać, czy wypowiedź już doszła
READ_LAST_STREAM_WINDOW_SECS = 2.0  # okno licznika znaków (już tylko do diagnostyki)
# Cisza rozstrzygająca: tyle bez ruchu w terminale I bez przyrostu dziennika
# znaczy „agent stanął, nie pisząc" (pytanie / prośba o zgodę) — czekanie nie ma
# już na co czekać. Tyle samo czasu dajemy narzędziu: krótkie (grep, odczyt pliku)
# oddaje wynik szybciej i czekanie leci dalej, długie (bash, pod-agent) zwalnia
# przycisk zamiast go blokować.
READ_LAST_STALL_SECS = 4.0
# ⛔ RUNDA 6 (2026-08-11) — próg 4 s ZWALNIAŁ CZEKANIE W ŚRODKU MYŚLENIA agenta.
# Zmierzone na dzienniku zakładki AS w chwili zgłoszenia usera: gdy agent jest
# w środku pracy, przerwa w zapisie przekracza 4 s w 28% przypadków, 10 s w 18%,
# 30 s w 6%; a droga „wynik narzędzia → następna wypowiedź" zajęła 20,7 / 23,1 /
# 29,6 / 70,7 s — ANI RAZU poniżej 20 s. Czyli zwykła pauza na myślenie wyglądała
# dla apki identycznie jak „agent skończył i już nic nie napisze" (klik o 10:31:00
# → po 6,5 s odczyt wypowiedzi sprzed 7 minut). Próg musi leżeć POWYŻEJ typowej
# pauzy, dlatego 30 s (ponad 90. percentyl zmierzonych przerw).
# ⚠️ Nie mylić z READ_LAST_STALL_SECS — tamten zwalnia przycisk, gdy RUSZYŁO
# NARZĘDZIE (o tym dziennik mówi wprost), i ma zostać krótki.
READ_LAST_OWED_STALL_SECS = 30.0
# Bezpiecznik czekania, gdy dziennik DOWODZI, że odpowiedź jest w drodze.
# RUNDA 6: 60 s → 180 s. Stary budżet pokrywał „30 s myślenia + 16 s pisania",
# ale zmierzony najgorszy realny przypadek to 70,7 s, a w dniu zgłoszenia dziennik
# milczał 12 minut przy pracującym agencie. Wydłużenie jest tanie, bo po zmianie
# z tej samej rundy wyczerpanie budżetu NIE CZYTA już starej wypowiedzi — mówi
# tylko „agent jeszcze pisze", więc pomyłka nic nie kosztuje.
READ_LAST_OWED_TIMEOUT_SECS = 180.0

# ⚠️ 🔊 „czytaj ostatnią” a PYTANIE Z POLAMI WYBORU (zmierzone 2026-08-28).
# Claude Code 2.1.250 NIE zapisuje wypowiedzi do dziennika, dopóki pytanie
# (AskUserQuestion / prośba o zgodę) czeka na odpowiedź — cały blok (tekst
# ORAZ pytanie) ląduje w pliku dopiero po kliknięciu odpowiedzi. Zmierzone na
# żywym dzienniku: wpisy ze znacznikiem 08:27 trafiły do pliku po 09:00, plik
# stał zamrożony 32 minuty. W tym czasie 🔊 widzi STARĄ, krótką wypowiedź
# i „agent winien tekst” → czeka → milczy. 26 z 28 nieudanych kliknięć tego
# dnia miało wiszące pytanie (kontrola: 5 z 83 udanych).
# Gdy tura jest „winna tekst”, a dziennik nie drgnął dłużej niż ten próg,
# agent NIE myśli — czeka na użytkownika, więc czekanie niczego nie przyniesie.
# Próg z POMIARU, nie z intuicji: najdłuższa zmierzona przerwa „wynik
# narzędzia → tekst” to ~71 s, więc 120 s leży bezpiecznie powyżej ogona normy.
READ_LAST_BLOCKED_AGE_SECS = 120.0
# Bezpiecznik dla stanu NIEROZSTRZYGNIĘTEGO (nie da się odczytać dziennika →
# decyduje stary czujnik terminala). Krótszy, bo to zgadywanie, nie dowód.
READ_LAST_WAIT_TIMEOUT_SECS = 20.0
# Pasywny log diagnostyczny 🔊 (włącz: CVA_READ_LAST_DEBUG=1). Pisze wyłącznie przy
# kliknięciu i w trakcie czekania — nie w gorącej pętli — ale i tak z twardym limitem
# (poprzedni taki log urósł kiedyś do 99 MB, patrz pamięć „diagnostyka tymczasowa").
# ⚠️ Zmienna środowiskowa NIE WYSTARCZA: apkę uruchamia się ikoną z pulpitu
# (rodzic = gnome-shell), więc przez 3 rundy napraw czujnik NIGDY nie był włączony
# u usera — log w ogóle nie powstał, a poprawki szły na ślepo. Dlatego druga furtka:
# PLIK-ZNACZNIK, który agent może założyć bez udziału (nietechnicznego) usera.
# Kasowanie pliku gasi czujnik — pamiętaj o tym po zakończeniu diagnozy.
READ_LAST_DEBUG_LOG = CONFIG_DIR / 'read-last-debug.log'
READ_LAST_DEBUG_MARKER = CONFIG_DIR / 'read-last-debug.on'
READ_LAST_DEBUG = (os.getenv('CVA_READ_LAST_DEBUG', '') == '1'
                   or READ_LAST_DEBUG_MARKER.exists())
READ_LAST_DEBUG_MAX_BYTES = 512 * 1024

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

# ===== Strażnik pamięci (RAM) =====
# Każda zakładka uruchamia osobny proces Claude Code CLI (node), który zżera
# 3–5 GB i rośnie z długością sesji — to on, nie nasz kod, dławi maszynę przy
# wielu zakładkach. Te dwie stałe to JEDYNE źródło heurystyki „ile agentów
# bezpiecznie naraz": recommended ≈ (total_RAM − rezerwa) / na_agenta.
# Dobrane zachowawczo; łatwe do strojenia w jednym miejscu.
RAM_PER_AGENT_GB = 4.0        # Zakładany apetyt jednej zakładki (środek 3–5 GB).
RAM_SYSTEM_RESERVE_GB = 3.0   # RAM zostawiony systemowi + samej aplikacji.

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
#
# ⚠️ TO JEDYNE MIEJSCE Z NAZWAMI MODELI. Wartości poniżej są AWARYJNE —
# realne nazwy i okna kontekstu apka pobiera ze strony Anthropic
# (`core/model_catalog.py`) i trzyma w pliku podręcznym. Opisy
# („najbardziej zdolny") siedzą w tłumaczeniach jako `model_*_desc`,
# żeby numer wersji NIE był powielony w słowniku i w dwóch językach naraz.
#
# Aliasy (fable/opus/sonnet/haiku) oznaczają ZAWSZE NAJNOWSZY model rodziny:
# `claude --model opus` to dziś Opus 5. Wpis `claude-opus-4-8` to świadome
# przypięcie starszego Opusa — pełna nazwa, nie alias, więc wersja się nie zmieni.
CLAUDE_MODELS = {
    "default": "Domyślny",
    "fable": "Fable 5",
    "opus": "Opus 5",
    "sonnet": "Sonnet 5",
    "haiku": "Haiku 4.5",
    "claude-opus-4-8": "Opus 4.8",
}
# Krótka etykieta (pasek statusu, panel agentów) = sama nazwa modelu.
CLAUDE_MODELS_SHORT = dict(CLAUDE_MODELS)
# Fallback for agents that don't have a `model` field saved (backward compat).
DEFAULT_AGENT_MODEL = "default"
# Pre-selected model when the user creates a NEW agent.
NEW_AGENT_DEFAULT_MODEL = "opus"

# Okna kontekstu modeli (w tokenach). Claude Code uruchamia auto-compact
# przy ~80–90% tej wartości — używane do koloryzacji licznika tokenów
# per-zakładka w pasku statusu.
# ⚠️ Też AWARYJNE — nadpisywane świeżymi danymi z katalogu (patrz niżej).
CLAUDE_MODEL_CONTEXT_LIMITS = {
    "default": 1_000_000,
    "fable":   1_000_000,
    "opus":    1_000_000,
    "sonnet":  1_000_000,   # Sonnet 5 ma 1 mln (do 2026-07 było tu 200 tys.)
    "haiku":     200_000,
    "claude-opus-4-8": 1_000_000,
}

# Mapa: TECHNICZNY identyfikator z dziennika sesji ("claude-opus-5") → klucz
# z CLAUDE_MODELS ("opus"). Potrzebna, gdy agent ma ustawienie „Domyślny":
# apka nie wie z góry, co uruchomi Claude Code, więc nazwę modelu poznaje
# dopiero po fakcie — z dziennika, a tam stoi identyfikator API, nie nasz klucz.
CLAUDE_MODEL_API_IDS = {}


def _rebuild_api_id_map(catalog=None):
    """Przebuduj mapę identyfikator API → klucz modelu.

    Dwa źródła: (1) nasze własne klucze będące PEŁNĄ nazwą (`claude-opus-4-8`
    — przypięta wersja, identyfikator to ona sama), (2) katalog ze strony
    Anthropic, który dla każdej rodziny podaje `api_id`/`api_alias`.
    Wołane przy imporcie ORAZ po każdym odświeżeniu katalogu.
    """
    CLAUDE_MODEL_API_IDS.clear()
    for key in CLAUDE_MODELS:
        if key.startswith("claude-"):
            CLAUDE_MODEL_API_IDS[key] = key
    for key, info in (catalog or {}).items():
        if not isinstance(info, dict):
            continue
        for field in ("api_id", "api_alias"):
            value = str(info.get(field) or "").strip()
            if value:
                CLAUDE_MODEL_API_IDS[value] = key


# Plik podręczny katalogu modeli (nazwy + okna kontekstu ze strony Anthropic).
MODEL_CATALOG_CACHE = CONFIG_DIR / "models-cache.json"

# Nałóż świeże dane, jeśli katalog był kiedykolwiek pobrany.
# ⛔ FAIL-OPEN: brak pliku, uszkodzony plik, brak modułu → zostajemy na
# wartościach wbudowanych wyżej. Tu NIE MA sieci — pobieranie robi apka
# w wątku tła (menu „Sprawdź nowe modele"), start nigdy nie czeka na internet.
_catalog = None
try:
    from core.model_catalog import cached_models as _cached_models
    from core.model_catalog import merge_into as _merge_models

    _catalog = _cached_models(MODEL_CATALOG_CACHE)
    if _catalog:
        CLAUDE_MODELS, CLAUDE_MODEL_CONTEXT_LIMITS = _merge_models(
            CLAUDE_MODELS, CLAUDE_MODEL_CONTEXT_LIMITS, _catalog)
        CLAUDE_MODELS_SHORT = dict(CLAUDE_MODELS)
except Exception:
    pass
# Także przy braku katalogu — mapa niesie wtedy same wpisy wbudowane.
_rebuild_api_id_map(_catalog)

# Groq API (for Speech-to-Text)
# GROQ_API_URL — dawna ścieżka WPROST do Groq (zostawiona jako odniesienie).
# Dyktowanie idzie teraz przez bramkę AI Managera (patrz STT_API_URL niżej).
GROQ_API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# STT przez bramkę AI Managera (monitorowanie zużycia). Dyktowanie leci przez tę
# „rogatkę" zamiast wprost do Groq — bramka liczy zużycie i rozdziela konta.
# Klucz = klucz aplikacji „Voice Assistant" z panelu AI Managera (zaczyna się od
# „aim-…"), wpisywany w Ustawieniach (przechowywany jak dotąd pod groq_api_key).
STT_API_URL = "https://ai.srv1251441.hstgr.cloud/v1/audio/transcriptions"
STT_MODEL = "groq/whisper-large-v3"          # bramka wymaga przedrostka „groq/"
STT_LANGUAGE_DEFAULT = "auto"                # „auto" = nie wysyłaj pola language (bramka sama wykrywa)

# ⛔ DZIENNIK DYKTOWANIA — ZAWSZE WŁĄCZONY, CELOWO BEZ CZUJNIKA DO WŁĄCZANIA.
# Powód (2026-08-29): dyktowanie było JEDYNĄ funkcją apki bez ani jednej linijki
# logu, a jego komunikat o błędzie ginął w tej samej milisekundzie (patrz
# `_on_stt_state_changed` → „Gotowy" nadpisywało „Błąd rozpoznawania"). Skutek:
# przy zgłoszeniu „dyktowanie nie wchodzi" NIE BYŁO CZEGO CZYTAĆ — ani śladu, czy
# nagrywanie w ogóle ruszyło, czy padła wysyłka. Diagnoza sprowadzała się do
# zgadywania. Nie stawiamy tu czujnika na zmiennej środowiskowej ani na
# pliku-znaczniku, bo apkę uruchamia się IKONĄ z pulpitu (rodzic = gnome-shell) —
# taki czujnik bywa martwy przez kolejne rundy napraw, a nikt tego nie zauważa.
# Koszt jest znikomy: piszemy WYŁĄCZNIE przy kliknięciu mikrofonu (nie w pętli),
# kilka linii na dyktowanie, z twardym limitem rozmiaru.
DICTATION_LOG = CONFIG_DIR / 'dictation.log'
DICTATION_LOG_MAX_BYTES = 512 * 1024

# Limit czasu na odpowiedź bramki. Było 30 s — za długo: przez te 30 s apka stała
# w stanie „przetwarzam", a w tym stanie KAŻDE kliknięcie mikrofonu było ciche
# (patrz STT_PROCESSING_STUCK_SECS). 12 s = tyle samo, ile ma lektor (TTS_GEN_TIMEOUT),
# a zmierzony czas poprawnej odpowiedzi bramki to ~1,2 s — zapas ponad 10×.
STT_HTTP_TIMEOUT = 12.0

# Po tylu sekundach stan „przetwarzam" uznajemy za ZAKLESZCZONY i odblokowujemy go
# na żądanie użytkownika. Dlaczego to w ogóle możliwe, skoro wyżej jest limit:
# limit `requests` NIE OBEJMUJE zamiany nazwy na adres (DNS) — przy zerwanym Wi-Fi
# `getaddrinfo` potrafi wisieć minutami, a wtedy wątek nie dochodzi do `finally`,
# które przywraca stan spoczynku. Zmierzone u usera 2026-08-29: mikrofon przestał
# reagować całkowicie (ikona NIE pulsowała), bo `start_recording()` wychodzi po
# cichu, gdy stan ≠ spoczynek. Wartość > STT_HTTP_TIMEOUT, żeby nie przerwać
# uczciwie trwającej wysyłki.
STT_PROCESSING_STUCK_SECS = 15.0

# TTS Settings
TTS_DEFAULT_VOICE = "pl-PL-ZofiaNeural"
TTS_DEFAULT_RATE = "+0%"
TTS_DEFAULT_VOLUME = "+0%"

# Funkcja #3 (głos per-agent) — wbudowana lista głosów edge-tts do dropdowna.
# ZGODNIE z obecnymi językami aplikacji: TYLKO polskie i angielskie. Polski ma
# w edge-tts maksymalnie 2 głosy (Marek/Zofia — więcej nie istnieje). Angielski
# w kilku regionach. Pełną, międzynarodową listę (~322) dialog dociąga na żądanie
# przez edge_tts.list_voices() z wyszukiwarką po języku. Para (voice_id, etykieta);
# symbole ♀/♂ zamiast słów — bez potrzeby tłumaczenia etykiet.
TTS_VOICE_CHOICES = [
    ("pl-PL-ZofiaNeural",        "Polski — Zofia ♀"),
    ("pl-PL-MarekNeural",        "Polski — Marek ♂"),
    ("en-US-AriaNeural",         "English US — Aria ♀"),
    ("en-US-JennyNeural",        "English US — Jenny ♀"),
    ("en-US-AvaNeural",          "English US — Ava ♀"),
    ("en-US-EmmaNeural",         "English US — Emma ♀"),
    ("en-US-MichelleNeural",     "English US — Michelle ♀"),
    ("en-US-GuyNeural",          "English US — Guy ♂"),
    ("en-US-AndrewNeural",       "English US — Andrew ♂"),
    ("en-US-BrianNeural",        "English US — Brian ♂"),
    ("en-US-ChristopherNeural",  "English US — Christopher ♂"),
    ("en-US-EricNeural",         "English US — Eric ♂"),
    ("en-US-RogerNeural",        "English US — Roger ♂"),
    ("en-GB-SoniaNeural",        "English UK — Sonia ♀"),
    ("en-GB-LibbyNeural",        "English UK — Libby ♀"),
    ("en-GB-MaisieNeural",       "English UK — Maisie ♀"),
    ("en-GB-RyanNeural",         "English UK — Ryan ♂"),
    ("en-GB-ThomasNeural",       "English UK — Thomas ♂"),
    ("en-AU-NatashaNeural",      "English AU — Natasha ♀"),
    ("en-AU-WilliamNeural",      "English AU — William ♂"),
    ("en-CA-ClaraNeural",        "English CA — Clara ♀"),
    ("en-CA-LiamNeural",         "English CA — Liam ♂"),
    ("en-IE-EmilyNeural",        "English IE — Emily ♀"),
    ("en-IE-ConnorNeural",       "English IE — Connor ♂"),
    ("en-IN-NeerjaNeural",       "English IN — Neerja ♀"),
    ("en-IN-PrabhatNeural",      "English IN — Prabhat ♂"),
]


def tts_voice_label(short_name: str, gender: str = "", locale: str = "") -> str:
    """Czytelna etykieta głosu z danych edge_tts.list_voices() (tryb „pobierz
    wszystkie"). Jeśli głos jest w liście kuratorowanej — użyj jej etykiety."""
    for vid, label in TTS_VOICE_CHOICES:
        if vid == short_name:
            return label
    sym = "♀" if (gender or "").lower().startswith("f") else ("♂" if gender else "")
    loc = locale or "-".join(short_name.split("-")[:2])
    # Końcówka ShortName: "en-US-AriaNeural" -> "Aria"
    tail = short_name.split("-")[-1].replace("Neural", "").replace("Multilingual", " (multi)")
    return f"{loc} — {tail} {sym}".strip()

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
    "en-US": ("English", "English", "en-US-JennyNeural"),
}

# UI Translations
UI_TRANSLATIONS = {
    "pl-PL": {
        "app_title": "Vibe Coding Assistant",
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
        "read_tooltip": "Czytaj zaznaczony tekst lub ostatnią odpowiedź (zaznacz z Shift, gdy Claude używa myszy)",
        "pause_tooltip": "Pauza / Wznów",
        "stop_tooltip": "Zatrzymaj wszystko",
        "copy_tooltip": "Kopiuj zaznaczony tekst (zaznacz z Shift, gdy Claude używa myszy)",
        "mouse_mode_scroll": "Mysz: przewijanie",
        "mouse_mode_select": "Mysz: zaznaczanie",
        "mouse_mode_tooltip": ("Przełącz, jak działa mysz w terminalu:\n"
                               "• Przewijanie — kółko przewija rozmowę Claude, klikasz w menu wyboru,"
                               " tekst zaznaczasz z Shift.\n"
                               "• Zaznaczanie — zaznaczasz i kopiujesz tekst przeciągnięciem bez Shift"
                               " (kółko/klik nie idą wtedy do Claude)."),
        "status_mouse_scroll": "Mysz: przewijanie (kółko przewija Claude, zaznaczanie z Shift)",
        "status_mouse_select": "Mysz: zaznaczanie tekstu bez Shift",
        "repair_terminal_tooltip": ("Napraw wygląd terminala, gdy tekst robi się\n"
                                    "„rozstrzelony” (litery z odstępami, kreski ─ ─ ─).\n"
                                    "Zapisuje zrzut do diagnozy i restartuje Claude Code\n"
                                    "z zachowaniem bieżącej rozmowy."),
        "status_terminal_repair": "Naprawiam wygląd terminala — wznawiam rozmowę…",
        "status_tts_catchup": "Lektor był w tyle — przeskakuję do najnowszej wypowiedzi",
        "status_login_checking": "Zakładka {name}: błąd logowania — sprawdzam, czy to wyścig zakładek…",
        "status_login_race": "Zakładka {name}: to NIE wylogowanie — zakładki ścigały się o token. Wystarczy ją zrestartować (Stop → Uruchom)",
        "status_login_real": "Claude Code jest wylogowany — wpisz /login w terminalu zakładki {name}",
        "menu_cloud": "Chmura — agenci na innym komputerze…",
        "cloud_title": "Chmura",
        "cloud_account": "Konto Google",
        "cloud_connect": "Połącz z Google",
        "cloud_disconnect": "Odłącz konto",
        "cloud_connected": "Połączono z Dyskiem Google.",
        "cloud_not_connected": "Nie połączono. Kliknij „Połącz z Google” — otworzy się przeglądarka.",
        "cloud_disconnected": "Konto odłączone. Paczka w chmurze została nietknięta.",
        "cloud_no_client": "Brak danych klienta Google — bez nich nie da się połączyć konta.",
        "cloud_scope_note": "Aplikacja widzi WYŁĄCZNIE pliki, które sama utworzy — nie ma wglądu w resztę Twojego Dysku. Paczki trafiają do folderu „{folder}”.",
        "cloud_pass_header": "Hasło paczki",
        "cloud_pass_desc": "Paczka jest szyfrowana na Twoim komputerze. Google przechowuje tylko nieczytelny plik — bez tego hasła nikt go nie odczyta.",
        "cloud_pass_placeholder": "Wygeneruj kod albo wpisz własne hasło",
        "cloud_pass_generate": "Wygeneruj kod",
        "cloud_pass_warn": "⚠️ Zapisz ten kod poza komputerem (np. na kartce). Zgubiony kod = paczki nie da się odzyskać.",
        "cloud_pass_written": "Kod wpisany w pole. Przepisz go na kartkę — będzie potrzebny na drugim komputerze.",
        "cloud_transfer": "Przenoszenie",
        "cloud_send": "Wyślij mózg agentów do chmury",
        "cloud_send_desc": "Wysyła agentów, pliki pamięci, skille, szybkie akcje i ustawienia. NIE wysyła kodu projektów — ten pobierasz z gita.",
        "cloud_get": "Pobierz z chmury na ten komputer",
        "cloud_get_desc": "Odtwarza agentów z paczki i przestawia ich ścieżki na wskazany katalog projektów.",
        "cloud_connect_working": "Otwieram przeglądarkę — potwierdź dostęp w oknie Google…",
        "cloud_connect_ok": "Połączono z Dyskiem Google.",
        "cloud_send_working": "Pakuję i szyfruję…",
        "cloud_sent_ok": "Wysłano do chmury ({kb} KB).",
        "cloud_get_working": "Pobieram i odszyfrowuję…",
        "cloud_got_ok": "Gotowe — odtworzono agentów: {agents}. Kod {clone} projektów trzeba jeszcze pobrać z gita (agenci mają zapisane adresy). Uruchom aplikację ponownie, żeby ich zobaczyć.",
        "cloud_need_pass": "Najpierw ustaw hasło paczki — wygeneruj kod albo wpisz własne.",
        "cloud_pick_root": "Wskaż katalog, w którym trzymasz projekty",
        "cloud_overwrite_title": "Nadpisać agentów?",
        "cloud_overwrite_text": "Pobranie zastąpi agentów i ustawienia na tym komputerze zawartością paczki z chmury. Kontynuować?",
        "cloud_err": "Nie udało się: {error}",
        "status_terminal_snapshot_only": "Zapisano zrzut terminala (brak sesji do wznowienia)",
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
        "menu_groq_api": "Klucz AI Managera (dyktowanie)...",
        "menu_anthropic_api": "Klucz API Anthropic...",
        "menu_claude_command": "Komenda Claude Code...",
        "menu_check_models": "Sprawdź nowe modele",
        "status_checking_models": "Sprawdzam listę modeli...",
        "status_models_updated": "Zaktualizowano nazwy modeli: {changes}",
        "models_up_to_date": "Lista modeli jest aktualna.",
        "models_new_family": ("Anthropic wypuścił nowy model: {names}.\n\n"
                              "Nie dodaję go automatycznie, bo nie wiem, czy "
                              "Twoja wersja Claude Code już go obsługuje — "
                              "zgłoś to autorowi aplikacji."),
        "models_check_failed": ("Nie udało się pobrać listy modeli.\n\n{error}\n\n"
                                "Nic się nie zepsuło — apka używa nazw "
                                "zapisanych wcześniej."),
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
        "model_default_full": "Domyślny (z konfiguracji Claude Code)",
        "model_default_short": "Domyślny",
        # Ustawienie „Domyślny" + model WYKRYTY z dziennika sesji. Nazwy nie
        # wpisujemy tu na sztywno — wstawia ją katalog modeli.
        "model_default_detected": "Domyślny ({name})",
        "model_detected_line": "Aktualnie odpowiada: {name}",
        # Same OPISY — nazwa modelu dochodzi z CLAUDE_MODELS/katalogu,
        # żeby numer wersji nie starzał się w dwóch językach naraz.
        "model_fable_desc": "najpotężniejszy, do najtrudniejszych zadań",
        "model_opus_desc": "najbardziej zdolny",
        "model_sonnet_desc": "szybki, zbalansowany",
        "model_haiku_desc": "najszybszy",
        "model_claude_opus_4_8_desc": "starszy Opus — mniej tokenów na zadanie",
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
        "status_copied_chars": "Skopiowano do schowka ({n} znaków)",
        "status_copy_no_selection": "Brak zaznaczenia — zaznacz tekst w terminalu (przytrzymaj Shift, gdy Claude używa myszy)",
        "status_copied_clipboard": "Skopiowano do schowka",
        # 🔍 Szukanie w rozmowie (dolny pasek, Ctrl+F)
        "search_tooltip": "Szukaj w rozmowie (Ctrl+F)",
        "search_title": "Szukaj w rozmowie",
        "search_placeholder": "Wpisz, czego szukać (bez ogonków też zadziała)...",
        "search_prev": "Poprzednie trafienie",
        "search_next": "Następne trafienie",
        "search_copy": "Kopiuj",
        "search_read": "Przeczytaj",
        "search_close": "Zamknij",
        # Odmiana przez liczbę: „1 raz w 1 wypowiedzi" / „5 razy w 3 wypowiedziach".
        # Po polsku wystarczą DWIE formy (raz/razy, wypowiedzi/wypowiedziach) —
        # „22 razy" i „25 wypowiedziach" są poprawne tak samo jak „5 razy".
        "search_count": "Znaleziono {hits} {hits_word} w {entries} {entries_word}",
        "search_word_hit_one": "raz",
        "search_word_hit_many": "razy",
        "search_word_entry_one": "wypowiedzi",
        "search_word_entry_many": "wypowiedziach",
        "search_none": "Nic takiego nie ma w tej rozmowie",
        "search_empty_journal": "Ta zakładka nie ma jeszcze zapisu rozmowy",
        "search_role_user": "Ty",
        "search_role_assistant": "Claude",
        "search_copied": "Skopiowano do schowka",
        "search_scrolled": "Przewinięto terminal do tego miejsca",
        "search_not_on_screen": "Tego fragmentu nie ma już w oknie terminala",
        "status_reading_last": "Czytam ostatnią odpowiedź...",
        "status_reading_wait": "⏳ Agent jeszcze pisze — czekam na koniec wypowiedzi...",
        "status_reading_wait_timeout": "Agent wciąż pisze — nowej odpowiedzi jeszcze nie ma. Kliknij 🔊 ponownie za chwilę.",
        "status_reading_wait_stalled": "Agent jeszcze nie napisał nowej odpowiedzi. Kliknij 🔊 ponownie za chwilę.",
        "status_reading_nothing_new": "Agent pracuje — od ostatniego czytania nic nowego nie napisał.",
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
        "status_unread_backlog": "🔔 {n} nieprzeczytanych wypowiedzi w tej zakładce — kliknij 🔊, aby doczytać",
        # === Dialogi (src/gui/dialogs.py) ===
        # --- Wspólne przyciski ---
        "dlg_cancel": "Anuluj",
        "dlg_save": "Zapisz",
        "dlg_close": "Zamknij",
        "dlg_delete": "Usuń",
        "dlg_edit": "Edytuj",
        "dlg_add": "Dodaj",
        "dlg_refresh": "Odśwież",
        "dlg_next": "Dalej →",
        "dlg_no_selection_title": "Brak wyboru",
        "dlg_no_name_title": "Brak nazwy",
        "dlg_no_data_title": "Brak danych",
        "dlg_confirm_delete_title": "Potwierdź usunięcie",
        "dlg_added_title": "Dodano",
        "dlg_installed_title": "Zainstalowano",
        "dlg_removed_title": "Usunięto",
        "dlg_saved_title": "Zapisano",
        "dlg_not_found_title": "Nie znaleziono",
        "dlg_save_error_title": "Błąd zapisu",
        "dlg_add_error_title": "Błąd dodawania",
        "dlg_delete_error_title": "Błąd usuwania",
        "dlg_edit_error_title": "Błąd edycji",
        "dlg_install_error_title": "Błąd instalacji",
        "dlg_error_title": "Błąd",
        "dlg_no_dir_title": "Brak katalogu",
        "dlg_set_valid_dir_first": "Najpierw ustaw poprawny katalog roboczy.",
        # --- Stylizowane dialogi plików ---
        "dlg_file_look_in": "Szukaj w:",
        "dlg_file_name": "Nazwa:",
        "dlg_file_type": "Typ plików:",
        "dlg_file_select": "Wybierz",
        "dlg_file_save": "Zapisz",
        # --- MemoryProjectsDialog ---
        "dlg_mem_title": "Pliki pamięci projektów",
        "dlg_mem_cannot_save": "Nie można zapisać: {error}",
        "dlg_mem_header": "Zarządzaj projektami i ich plikami pamięci",
        "dlg_mem_desc": "Pliki pamięci są automatycznie wysyłane do Claude Code jako kontekst przy starcie sesji.",
        "dlg_mem_col_name": "Nazwa",
        "dlg_mem_col_path": "Ścieżka",
        "dlg_mem_add_project": "Dodaj projekt",
        "dlg_mem_add_file": "Dodaj plik",
        "dlg_mem_add_folder": "Dodaj folder",
        "dlg_mem_unnamed": "Bez nazwy",
        "dlg_mem_no_file": "Brak pliku",
        "dlg_mem_select_project_for_file": "Wybierz projekt, do którego chcesz dodać plik.",
        "dlg_mem_select_project_for_files": "Wybierz projekt, do którego chcesz dodać pliki.",
        "dlg_mem_file_filter": "Pliki pamięci (*.md *.txt *.json);;Wszystkie pliki (*)",
        "dlg_mem_choose_files": "Wybierz pliki pamięci",
        "dlg_mem_choose_folder": "Wybierz folder z plikami",
        "dlg_mem_files_added_title": "Dodano pliki",
        "dlg_mem_files_added_n": "Dodano {n} plików z folderu.",
        "dlg_mem_no_files_title": "Brak plików",
        "dlg_mem_no_new_files": "Nie znaleziono nowych plików do dodania.",
        "dlg_mem_select_to_edit": "Wybierz element do edycji.",
        "dlg_mem_select_to_delete": "Wybierz element do usunięcia.",
        "dlg_mem_confirm_delete_project": 'Czy na pewno usunąć projekt "{name}" i wszystkie jego pliki?',
        "dlg_mem_confirm_delete_file": 'Czy na pewno usunąć plik "{name}"?',
        # --- ProjectEditDialog ---
        "dlg_proj_edit_title": "Edytuj projekt",
        "dlg_proj_new_title": "Nowy projekt",
        "dlg_proj_name_placeholder": "np. Fulfillment CRM",
        "dlg_proj_name_label": "Nazwa projektu:",
        "dlg_proj_give_name": "Podaj nazwę projektu.",
        # --- AgentConfigDialog ---
        "dlg_agent_edit_title": "Edytuj agenta",
        "dlg_agent_new_title": "Nowy agent",
        "dlg_agent_config_header": "Konfiguracja agenta",
        "dlg_agent_save_run": "Zapisz i uruchom",
        "dlg_agent_tab_basic": "📝 Podstawowe",
        "dlg_agent_tab_memory": "💾 Pamięć",
        "dlg_agent_tab_skills": "🧩 Skille",
        "dlg_agent_tab_mcp": "🔌 MCP",
        "dlg_agent_name_placeholder": "np. CRM Development",
        "dlg_agent_name_label": "Nazwa agenta:",
        "dlg_agent_working_dir_label": "Katalog roboczy:",
        "dlg_agent_model_label": "Model Claude Code:",
        "dlg_agent_model_hint": "Zmiana modelu wymaga restartu agenta (Stop → Uruchom).",
        "dlg_agent_auto_start": "Uruchamiaj automatycznie przy starcie aplikacji",
        "dlg_agent_load_memory": "Wczytaj pliki pamięci po starcie Claude Code",
        "dlg_agent_icon_label": "Ikona zakładki",
        "dlg_agent_icon_emoji_ph": "Emoji (wpisz lub wklej)",
        "dlg_agent_icon_file_btn": "📁 Plik…",
        "dlg_agent_icon_clear": "Wyczyść",
        "dlg_agent_icon_file_title": "Wybierz ikonę (obraz)",
        "dlg_agent_icon_hint": "Kliknij podgląd (🤖), aby wybrać z gotowej puli ikon. Możesz też wpisać własne emoji albo wskazać obrazek (PNG/SVG). Puste = domyślna 🤖.",
        "dlg_agent_icon_pick_tooltip": "Kliknij, aby wybrać ikonę z gotowej puli",
        "dlg_agent_color_label": "Kolor zakładki",
        "dlg_agent_color_clear": "Bez koloru",
        "dlg_agent_color_tooltip": "Kliknij, aby wybrać dowolny kolor zakładki",
        "dlg_agent_color_hint": "Kolor zabarwia tekst tej zakładki oraz ramkę całego okna, gdy zakładka jest aktywna. Wybierz z palety obok albo kliknij kwadrat po lewej, by otworzyć pełną paletę. Puste = bez koloru.",
        "dlg_agent_voice_label": "Głos czytającego",
        "dlg_agent_voice_default": "Domyślny (wg języka aplikacji)",
        "dlg_agent_voice_more": "🌐 Więcej głosów…",
        "dlg_agent_voice_loading": "Pobieranie głosów z internetu…",
        "dlg_agent_voice_load_failed": "Nie udało się pobrać listy głosów (brak internetu?)",
        "dlg_agent_voice_search_title": "Wybierz głos — szukaj po języku",
        "dlg_agent_voice_search_ph": "Szukaj języka lub głosu (np. polish, english, german, ja-JP)…",
        "dlg_agent_voice_search_count": "Pasujące głosy: {n}",
        "dlg_agent_voice_hint": "Głos, którym czytane są na głos odpowiedzi w tej zakładce. Puste = głos domyślny dla języka aplikacji. Lista wbudowana ma głosy polskie i angielskie; „Więcej głosów…” otwiera pełną listę z internetu z wyszukiwarką po języku.",
        "dlg_agent_icon_cat_dev": "Programowanie",
        "dlg_agent_icon_cat_sales": "Sprzedaż",
        "dlg_agent_icon_cat_seo": "SEO / pozycjonowanie",
        "dlg_agent_icon_cat_social": "Social media / marketing",
        "dlg_agent_icon_cat_project": "Projekty / praca",
        "dlg_agent_memory_files_label": "📄 Pliki pamięci agenta:",
        "dlg_agent_memory_info": "ℹ️ Pliki wczytywane przy starcie agenta — Claude Code dostaje je jako kontekst rozmowy.",
        "dlg_agent_add_file": "+ Dodaj plik",
        "dlg_agent_skills_label": "🧩 Skille tego agenta:",
        "dlg_agent_skills_info": "ℹ️ Każdy agent dziedziczy globalne skille z menu Rozszerzenia. Tutaj możesz dodać dodatkowe — widoczne tylko dla tego agenta.",
        "dlg_agent_disable_skills_label": "🚫 Wyłącz globalne skille dla tego agenta:",
        "dlg_agent_disable_skills_info": "ℹ️ Globalne skille są domyślnie aktywne. Odznacz te, których ten agent ma nie używać. Zapis dzieje się natychmiast.",
        "dlg_agent_mcp_label": "🔌 Serwery MCP tego agenta:",
        "dlg_agent_mcp_info": "ℹ️ Każdy agent dziedziczy globalne serwery MCP z menu Rozszerzenia. Tutaj możesz dodać dodatkowe — działające tylko w katalogu tego agenta.",
        "dlg_agent_disable_mcp_label": "🚫 Wyłącz globalne MCP dla tego agenta:",
        "dlg_agent_disable_mcp_info": "ℹ️ Globalne serwery MCP są domyślnie aktywne. Odznacz te, których ten agent ma nie używać. Zapis dzieje się natychmiast.",
        "dlg_agent_choose_working_dir": "Wybierz katalog roboczy",
        "dlg_agent_give_name": "Podaj nazwę agenta.",
        "dlg_agent_invalid_dir_title": "Nieprawidłowy katalog",
        "dlg_agent_dir_not_exist": "Podany katalog nie istnieje.",
        "dlg_agent_manage_skills_no_dir": "🧩 Zarządzaj lokalnymi skillami (najpierw ustaw poprawny katalog)",
        "dlg_agent_manage_skills_none": "🧩 Zarządzaj lokalnymi skillami (brak)",
        "dlg_agent_manage_skills_1": "🧩 Zarządzaj lokalnymi skillami (1 zainstalowany)",
        "dlg_agent_manage_skills_few": "🧩 Zarządzaj lokalnymi skillami ({n} zainstalowane)",
        "dlg_agent_manage_skills_many": "🧩 Zarządzaj lokalnymi skillami ({n} zainstalowanych)",
        "dlg_agent_skills_local_tooltip": "Skille lokalne dla tego agenta ({path})",
        "dlg_agent_skills_save_failed": "Nie udało się zapisać ustawień: {error}",
        "dlg_agent_manage_mcp_no_dir": "🔌 Zarządzaj lokalnymi MCP (najpierw ustaw poprawny katalog)",
        "dlg_agent_manage_mcp_none": "🔌 Zarządzaj lokalnymi MCP (brak)",
        "dlg_agent_manage_mcp_1": "🔌 Zarządzaj lokalnymi MCP (1 zainstalowany)",
        "dlg_agent_manage_mcp_few": "🔌 Zarządzaj lokalnymi MCP ({n} zainstalowane)",
        "dlg_agent_manage_mcp_many": "🔌 Zarządzaj lokalnymi MCP ({n} zainstalowanych)",
        "dlg_agent_mcp_local_tooltip": "Serwery MCP lokalne dla tego agenta ({path})",
        "dlg_agent_mcp_save_failed": "Nie udało się zapisać ustawień MCP: {error}",
        "dlg_agent_skills_no_desc": "(brak opisu)",
        "dlg_agent_skills_count_no_dir": "⚠ Najpierw ustaw poprawny katalog roboczy.",
        "dlg_agent_skills_count_none": "Brak zainstalowanych globalnych skilli. Zainstaluj je w menu Rozszerzenia → Umiejętności.",
        "dlg_agent_disabled_of_global": "{disabled} z {total} globalnych wyłączone dla tego agenta.",
        "dlg_agent_mcp_count_none": "Brak globalnych serwerów MCP. Dodaj je w menu Rozszerzenia → Serwery MCP.",
        "dlg_agent_fallback_name": "Agent",
        "dlg_agent_choose_memory_files": "Wybierz pliki pamięci",
        # --- AgentsManagerDialog ---
        "dlg_agents_title": "Zarządzaj agentami",
        "dlg_agents_header": "Zarządzaj agentami (zakładkami terminala)",
        "dlg_agents_desc": "Każdy agent to osobna zakładka z własnym terminalem i przypisanym projektem pamięci.",
        "dlg_agents_move_up": "▲ W górę",
        "dlg_agents_move_down": "▼ W dół",
        "dlg_agents_run": "▶️ Uruchom",
        "dlg_agents_add": "➕ Dodaj",
        "dlg_agents_edit": "✏️ Edytuj",
        "dlg_agents_duplicate": "📋 Duplikuj",
        "dlg_agents_delete": "🗑️ Usuń",
        "dlg_agents_no_files": "Brak plików",
        "dlg_agents_files_1": "1 plik",
        "dlg_agents_files_few": "{n} pliki",
        "dlg_agents_files_many": "{n} plików",
        "dlg_agents_unnamed": "Bez nazwy",
        "dlg_agents_loading": "⏳ ładowanie…",
        "dlg_agents_skills_loading_tooltip": "Ładuję listę skilli tego agenta...",
        "dlg_agents_mcp_loading_tooltip": "Ładuję listę MCP tego agenta (wymaga uruchomienia 'claude mcp list')...",
        "dlg_agents_skills_error": "⚠ błąd skille",
        "dlg_agents_skills_error_tooltip": "Nie udało się załadować skilli:\n{error}",
        "dlg_agents_mcp_error": "⚠ błąd MCP",
        "dlg_agents_mcp_error_tooltip": "Nie udało się załadować MCP:\n{error}",
        "dlg_agents_mem_tooltip_header": "Pliki pamięci tego agenta:",
        "dlg_agents_mem_tooltip_none": "Pliki pamięci tego agenta:\n\n   (brak plików pamięci)",
        "dlg_agents_local_1": "{n} lokalny",
        "dlg_agents_local_few": "{n} lokalne",
        "dlg_agents_local_many": "{n} lokalnych",
        "dlg_agents_global_1": "{n} globalny",
        "dlg_agents_global_few": "{n} globalne",
        "dlg_agents_global_many": "{n} globalnych",
        "dlg_agents_skills_unknown": "⚠ skille nieznane",
        "dlg_agents_skills_unknown_tooltip": "Katalog roboczy agenta jest pusty lub nie istnieje —\nnie da się odczytać listy skilli.",
        "dlg_agents_no_skills": "🚫 brak skilli",
        "dlg_agents_skills_global": "🧩 {global}",
        "dlg_agents_skills_global_local": "🧩 {global} + {local}",
        "dlg_agents_skills_cut": "✂️ {on} z {total} globalnych",
        "dlg_agents_skills_cut_local": "✂️ {on} z {total} globalnych + {local}",
        "dlg_agents_skills_tooltip_header": "Skille tego agenta:",
        "dlg_agents_tooltip_global_active": "\n✓ Globalne aktywne ({n}):",
        "dlg_agents_tooltip_global_disabled": "\n✗ Globalne wyłączone ({n}):",
        "dlg_agents_tooltip_local": "\n+ Lokalne ({n}):",
        "dlg_agents_skills_tooltip_none": "\n(brak zainstalowanych skilli)",
        "dlg_agents_mcp_unknown": "⚠ MCP nieznane",
        "dlg_agents_mcp_unknown_tooltip": "Katalog roboczy agenta jest pusty lub nie istnieje —\nnie da się odczytać listy MCP.",
        "dlg_agents_mcp_fetch_failed_tooltip": "Nie udało się pobrać listy MCP (komenda 'claude' nieaktywna?).",
        "dlg_agents_no_mcp": "🚫 brak MCP",
        "dlg_agents_mcp_global": "🔌 {global}",
        "dlg_agents_mcp_global_local": "🔌 {global} + {local}",
        "dlg_agents_mcp_cut": "✂️ {on} z {total} globalnych MCP",
        "dlg_agents_mcp_cut_local": "✂️ {on} z {total} globalnych MCP + {local}",
        "dlg_agents_mcp_tooltip_header": "Serwery MCP tego agenta:",
        "dlg_agents_mcp_tooltip_none": "\n(brak zarejestrowanych MCP)",
        "dlg_agents_select_to_run": "Wybierz agenta do uruchomienia.",
        "dlg_agents_select_to_edit": "Wybierz agenta do edycji.",
        "dlg_agents_select_to_duplicate": "Wybierz agenta do duplikacji.",
        "dlg_agents_select_to_delete": "Wybierz agenta do usunięcia.",
        "dlg_agents_copy_suffix": "{name} (kopia)",
        "dlg_agents_cannot_delete_title": "Nie można usunąć",
        "dlg_agents_must_keep_one": "Musi pozostać co najmniej jeden agent.",
        "dlg_agents_confirm_delete": 'Czy na pewno usunąć agenta "{name}"?',
        # --- SkillsManagerDialog ---
        "dlg_skills_agent_title_named": "Skille agenta — {name}",
        "dlg_skills_agent_title": "Skille agenta",
        "dlg_skills_global_title": "Umiejętności (Skills)",
        "dlg_skills_agent_header_named": "🧩 Skille agenta — {name}",
        "dlg_skills_agent_header": "🧩 Skille agenta",
        "dlg_skills_agent_desc": "Skille tutaj są widoczne TYLKO dla tego agenta. Globalne (dla wszystkich agentów) zarządzasz w menu Rozszerzenia → Umiejętności (Skills).",
        "dlg_skills_global_desc": "Skille rozszerzają możliwości Claude Code o gotowe procedury (np. analiza PDF, tworzenie dokumentów). Claude sam je aktywuje gdy ich opis pasuje do treści rozmowy.",
        "dlg_skills_location": "📂 Lokalizacja: {path}",
        "dlg_skills_add_zip": "📦 Dodaj z ZIP",
        "dlg_skills_add_folder": "📂 Dodaj z folderu",
        "dlg_skills_show_folder": "📁 Pokaż folder",
        "dlg_skills_refresh": "🔄 Odśwież",
        "dlg_skills_delete": "🗑️ Usuń",
        "dlg_skills_empty": 'Brak zainstalowanych skilli.\nUżyj „Dodaj z ZIP" lub „Dodaj z folderu" żeby zainstalować pierwszy.',
        "dlg_skills_no_desc": "(brak opisu)",
        "dlg_skills_zip_filter": "Plik ZIP (*.zip);;Wszystkie pliki (*)",
        "dlg_skills_choose_zip": "Wybierz plik ZIP ze skillem",
        "dlg_skills_choose_folder": "Wybierz folder ze skillem",
        "dlg_skills_already_exists_marker": "już istnieje",
        "dlg_skills_already_exists_title": "Skill już istnieje",
        "dlg_skills_overwrite_prompt": "{msg}\n\nNadpisać istniejącego skilla?",
        "dlg_skills_unexpected_error": "Nieoczekiwany błąd: {error}",
        "dlg_skills_installed_msg": 'Skill „{name}" został zainstalowany.',
        "dlg_skills_select_to_delete": "Wybierz skill do usunięcia.",
        "dlg_skills_confirm_delete": 'Czy na pewno usunąć skill „{name}"?\nFolder zostanie nieodwracalnie usunięty:\n{path}',
        "dlg_skills_removed_msg": 'Skill „{name}" został usunięty.',
        "dlg_skills_folder_gone": "Folder skilla już nie istniał.",
        # --- MCP status / scope ---
        "dlg_mcp_status_connected": "Aktywny",
        "dlg_mcp_status_needs_auth": "Wymaga autoryzacji",
        "dlg_mcp_status_failed": "Błąd połączenia",
        "dlg_mcp_status_unknown": "Status nieznany",
        "dlg_mcp_scope_user": "globalny",
        "dlg_mcp_scope_local": "lokalny (agenta)",
        "dlg_mcp_scope_managed": "zarządzany (claude.ai)",
        # --- McpManagerDialog ---
        "dlg_mcp_agent_title_named": "Serwery MCP agenta — {name}",
        "dlg_mcp_agent_title": "Serwery MCP agenta",
        "dlg_mcp_global_title": "Serwery MCP",
        "dlg_mcp_agent_header_named": "🔌 Serwery MCP agenta — {name}",
        "dlg_mcp_agent_header": "🔌 Serwery MCP agenta",
        "dlg_mcp_agent_desc": "Serwery dodane tutaj działają TYLKO w katalogu tego agenta. Globalne serwery (dla wszystkich agentów) zarządzasz w menu Rozszerzenia → Serwery MCP.",
        "dlg_mcp_global_header": "🔌 Serwery MCP (Model Context Protocol)",
        "dlg_mcp_global_desc": "Serwery MCP to „wtyczki z narzędziami\" dla Claude Code — pozwalają agentowi czytać Twój dysk, kalendarz, bazy danych, wysyłać wiadomości itp. Claude sam decyduje, kiedy ich użyć.",
        "dlg_mcp_add_template": "📚 Dodaj z szablonu...",
        "dlg_mcp_add_manual": "✏️ Dodaj ręcznie...",
        "dlg_mcp_add_json": "📋 Dodaj z JSON...",
        "dlg_mcp_authorize": "🔓 Autoryzuj",
        "dlg_mcp_authorize_tooltip": "Dla serwerów wymagających autoryzacji (claude.ai, OAuth)",
        "dlg_mcp_test": "🔍 Test",
        "dlg_mcp_test_tooltip": "Sprawdź czy zaznaczony serwer odpowiada",
        "dlg_mcp_edit": "✏️ Edytuj",
        "dlg_mcp_edit_tooltip": "Edytuj zaznaczony serwer (nie działa dla zarządzanych przez claude.ai)",
        "dlg_mcp_refresh": "🔄 Odśwież",
        "dlg_mcp_delete": "🗑️ Usuń",
        "dlg_mcp_fetch_failed": "Nie udało się pobrać listy MCP:\n{error}",
        "dlg_mcp_empty": 'Brak serwerów MCP.\nUżyj „Dodaj z szablonu" żeby zainstalować pierwszy.',
        "dlg_mcp_added_msg": 'Serwer „{name}" został dodany.\n\n{hint}',
        "dlg_mcp_added_simple": 'Serwer „{name}" został dodany.',
        "dlg_mcp_select_to_authorize": "Wybierz serwer do autoryzacji.",
        "dlg_mcp_browser_opened_title": "Otwarto przeglądarkę",
        "dlg_mcp_browser_opened_msg": 'Otworzyłem panel integracji claude.ai. Tam zaloguj się i autoryzuj serwer „{name}". Po zakończeniu wróć tutaj i kliknij „🔄 Odśwież".',
        "dlg_mcp_oauth_title": "Autoryzacja OAuth",
        "dlg_mcp_oauth_msg": 'Aby autoryzować serwer „{name}":\n\n1. Otwórz Claude Code w katalogu:\n   {dir}\n\n2. Poproś go o jakiekolwiek użycie tego serwera (np. „pokaż mi listę narzędzi z {name}").\n\n3. Claude Code otworzy przeglądarkę i poprowadzi przez OAuth.\n\n4. Wróć tutaj i kliknij „🔄 Odśwież".',
        "dlg_mcp_select_to_test": "Wybierz serwer do przetestowania.",
        "dlg_mcp_test_error_title": "Błąd testu",
        "dlg_mcp_server_gone": 'Serwer „{name}" nie istnieje już w konfiguracji.',
        "dlg_mcp_test_result_title": "Wynik testu",
        "dlg_mcp_test_result_msg": '{icon} Serwer „{name}"\n\nStatus: {status}\nCzas sprawdzenia: {ms} ms\nSurowy status: {raw}',
        "dlg_mcp_raw_status_none": "(brak)",
        "dlg_mcp_select_to_edit": "Wybierz serwer do edycji.",
        "dlg_mcp_managed_title": "Serwer zarządzany",
        "dlg_mcp_managed_edit_msg": 'Serwer „{name}" jest zarządzany przez claude.ai i nie można go edytować z poziomu tej aplikacji.',
        "dlg_mcp_updated_msg": 'Serwer „{name}" został zaktualizowany.',
        "dlg_mcp_select_to_delete": "Wybierz serwer do usunięcia.",
        "dlg_mcp_managed_delete_msg": 'Serwer „{name}" jest zarządzany przez claude.ai i nie można go usunąć z poziomu tej aplikacji. Aby go odłączyć, zaloguj się na claude.ai i odepnij integrację w ustawieniach.',
        "dlg_mcp_confirm_delete": 'Czy na pewno usunąć serwer MCP „{name}" (scope: {scope})?',
        "dlg_mcp_deleted_msg": 'Serwer „{name}" został usunięty.',
        # --- _McpTemplatePickerDialog ---
        "dlg_mcptpl_title": "Wybierz szablon MCP",
        "dlg_mcptpl_header": "📚 Wybierz szablon serwera MCP",
        "dlg_mcptpl_desc": "Każdy szablon to gotowy serwer MCP — kliknij i podaj wymagane dane (np. token, ścieżkę). Szczegóły konfiguracji w następnym kroku.",
        "dlg_mcptpl_select": "Wybierz szablon z listy.",
        # --- _McpTemplateConfigDialog ---
        "dlg_mcpcfg_title": "Konfiguracja: {title}",
        "dlg_mcpcfg_server_name": "Nazwa serwera:",
        "dlg_mcpcfg_optional_prefix": "(opcjonalne) {label}",
        "dlg_mcpcfg_env_opt_label": "{key} (opc.):",
        "dlg_mcpcfg_scope_user": "Globalny (dla wszystkich agentów)",
        "dlg_mcpcfg_scope_local": "Lokalny (tylko ten agent)",
        "dlg_mcpcfg_scope_label": "Zakres:",
        "dlg_mcpcfg_docs": "📖 Dokumentacja serwera",
        "dlg_mcpcfg_install": "✅ Zainstaluj",
        "dlg_mcpcfg_give_server_name": "Podaj nazwę serwera.",
        "dlg_mcpcfg_field_required": "Pole „{label}\" jest wymagane.",
        "dlg_mcpcfg_unknown_transport": "Nieznany transport szablonu: {transport}",
        # --- _McpAddManualDialog ---
        "dlg_mcpman_edit_title": "Edytuj serwer MCP — {name}",
        "dlg_mcpman_add_title": "Dodaj serwer MCP ręcznie",
        "dlg_mcpman_edit_header": "✏️ Edytuj serwer MCP",
        "dlg_mcpman_add_header": "✏️ Dodaj serwer MCP ręcznie",
        "dlg_mcpman_edit_note": "ℹ️ Zmiany zostaną zapisane jako: usunięcie starego wpisu + dodanie z nowymi danymi. W razie błędu — automatyczny powrót do poprzedniej konfiguracji.",
        "dlg_mcpman_name_placeholder": "np. moje-narzedzie",
        "dlg_mcpman_name_label": "Nazwa:",
        "dlg_mcpman_transport_stdio": "stdio (komenda lokalna)",
        "dlg_mcpman_transport_http": "http (serwer HTTP)",
        "dlg_mcpman_transport_sse": "sse (Server-Sent Events)",
        "dlg_mcpman_transport_label": "Transport:",
        "dlg_mcpman_args_placeholder": "-y @scope/package arg1 arg2  (oddziel spacjami)",
        "dlg_mcpman_command_label": "Komenda:",
        "dlg_mcpman_args_label": "Argumenty:",
        "dlg_mcpman_url_label": "URL:",
        "dlg_mcpman_env_placeholder": "KEY1=value1\nKEY2=value2",
        "dlg_mcpman_env_label": "ENV (po linii):",
        "dlg_mcpman_headers_placeholder": "Authorization: Bearer xxx\nX-Api-Key: yyy",
        "dlg_mcpman_headers_label": "Nagłówki (po linii):",
        "dlg_mcpman_scope_label": "Zakres:",
        "dlg_mcpman_ok_save": "💾 Zapisz",
        "dlg_mcpman_ok_add": "✅ Dodaj",
        "dlg_mcpman_name_immutable_tooltip": "W trybie edycji nazwa jest niezmienna.",
        "dlg_mcpman_give_server_name": "Podaj nazwę serwera.",
        "dlg_mcpman_no_command_title": "Brak komendy",
        "dlg_mcpman_give_command": "Podaj komendę do uruchomienia.",
        "dlg_mcpman_bad_url_title": "Zły URL",
        "dlg_mcpman_bad_url_msg": "URL musi zaczynać się od http:// lub https://",
        # --- _McpJsonImportDialog ---
        "dlg_mcpjson_title": "Dodaj serwer MCP z JSON",
        "dlg_mcpjson_header": "📋 Dodaj serwer MCP z JSON",
        "dlg_mcpjson_desc": 'Wklej JSON konfiguracji serwera MCP (np. z dokumentacji). Format: <code>{"type":"stdio","command":"npx","args":[...],"env":{...}}</code>',
        "dlg_mcpjson_name_placeholder": "np. moj-serwer",
        "dlg_mcpjson_name_label": "Nazwa:",
        "dlg_mcpjson_scope_label": "Zakres:",
        "dlg_mcpjson_ok_add": "✅ Dodaj",
        "dlg_mcpjson_give_server_name": "Podaj nazwę serwera.",
        "dlg_mcpjson_no_json_title": "Brak JSON",
        "dlg_mcpjson_paste_json": "Wklej JSON konfiguracji serwera.",
        "dlg_mcpjson_bad_json_title": "Zły JSON",
        "dlg_mcpjson_bad_json_msg": "Nieprawidłowy JSON: {error}",
        # --- UpdateAvailableDialog ---
        "dlg_update_title": "Dostępna aktualizacja",
        "dlg_update_new_version": "Dostępna nowa wersja: {version}",
        "dlg_update_current_version": "Masz zainstalowaną wersję {version}.",
        "dlg_update_mandatory": "⚠️ To jest aktualizacja wymagana.",
        "dlg_update_release_notes": "Informacje o wydaniu…",
        "dlg_update_later": "Później",
        "dlg_update_download_install": "Pobierz i zainstaluj",
        "dlg_update_downloading": "Pobieranie…",
        "dlg_update_downloading_progress": "Pobieranie… {done:.1f}/{total:.1f} MB",
        "dlg_update_downloading_simple": "Pobieranie… {done:.1f} MB",
        "dlg_update_installing": "Pobrano. Instaluję nową wersję…",
        "dlg_update_downloaded_opening": "Pobrano i zweryfikowano. Otwieram instalator…",
        "dlg_update_relaunch_status": "Gotowe. Uruchamiam nową wersję…",
        "dlg_update_ready_title": "Aktualizacja gotowa",
        "dlg_update_ready_msg": "Nowa wersja zostanie zainstalowana, a aplikacja uruchomi się ponownie za chwilę.",
        "dlg_update_downloaded_title": "Aktualizacja pobrana",
        "dlg_update_installer_opened_msg": "Instalator został otwarty. Dokończ instalację i uruchom aplikację ponownie.",
        "dlg_update_error_title": "Błąd aktualizacji",
        # --- Lampka „nowa wersja" w pasku statusu ---
        "update_indicator_text": "⬆ Nowa wersja",
        "update_indicator_tooltip": "Dostępna jest nowa wersja. Kliknij, aby pobrać i zainstalować.",
        # --- Wskaźnik zużycia pamięci RAM w pasku statusu ---
        "ram_indicator_loading": "Pamięć RAM — pomiar…",
        "ram_indicator_swap_none": "brak",
        "ram_indicator_tooltip": (
            "Pamięć komputera (RAM)\n"
            "Program (z Claude Code): {prog}\n"
            "System: {used} / {total} ({pct}%)\n"
            "Plik wymiany (swap): {swap}\n\n"
            "Kolor ostrzega przed zawieszeniem, gdy pamięć się zapełnia:\n"
            "zielony → żółty → pomarańczowy → czerwony."
        ),
        # --- ClaudeSetupDialog ---
        "dlg_setup_title": "Dokończ instalację — potrzebny Claude Code",
        "dlg_setup_header": "Jeszcze jeden krok — zainstaluj Claude Code",
        "dlg_setup_intro": "Ten program jest „pilotem” do narzędzia <b>Claude Code</b> — to ono rozmawia z Tobą i pisze kod. Na tym komputerze jeszcze go nie ma, dlatego terminal nie zadziała. Instalacja jest darmowa i zajmuje kilka minut. Wystarczy wykonać te trzy kroki:",
        "dlg_setup_step1_title": "Krok 1 — zainstaluj Node.js (darmowy program pomocniczy)",
        "dlg_setup_step1_label": "Kliknij przycisk poniżej, pobierz wersję <b>LTS</b> (zielony przycisk) i zainstaluj jak każdy program (Dalej → Dalej → Zakończ).",
        "dlg_setup_step1_warn": "⚠️ W instalatorze Node.js <b>NIE zaznaczaj</b> opcji „Tools for Native Modules”. Jeśli mimo to pojawi się czarne okno z groźnie wyglądającymi błędami — po prostu je zamknij, to nieszkodliwe (Node.js jest już zainstalowany).",
        "dlg_setup_node_btn": "🌐 Otwórz stronę nodejs.org",
        "dlg_setup_step2_title": "Krok 2 — zainstaluj Claude Code",
        "dlg_setup_step2_label": "Po zainstalowaniu Node.js <b>uruchom ten program od nowa</b>, wklej do terminala (czarne pole w oknie) poniższą komendę i naciśnij Enter. Napis „added … packages” oznacza sukces.",
        "dlg_setup_copy": "⧉ Kopiuj",
        "dlg_setup_copied": "✓ Skopiowano",
        "dlg_setup_step3_title": "Krok 3 — uruchom i zaloguj się",
        "dlg_setup_step3_label": "Wpisz w terminalu <b>claude</b> i naciśnij Enter. Przy pierwszym uruchomieniu Claude Code poprosi o zalogowanie — jeśli przeglądarka nie otworzy się sama, naciśnij klawisz <b>c</b> (skopiuje link), wklej go w przeglądarce i dokończ logowanie. <b>Nie przepisuj linku ręcznie</b> — jest bardzo długi.",
        "dlg_setup_full_guide": "📖 Pełna instrukcja (krok po kroku)",
        "dlg_setup_check_again": "🔄 Sprawdź ponownie",
        "dlg_setup_found_title": "Znaleziono Claude Code",
        "dlg_setup_found_msg": "Claude Code jest zainstalowany. 🎉\n\nMożesz teraz uruchomić agenta (zakładka → Uruchom) albo wpisać „claude” w terminalu.",
        "dlg_setup_not_found_title": "Jeszcze nie widać Claude Code",
        "dlg_setup_not_found_msg": "Nie znalazłem jeszcze Claude Code w systemie.\n\nUpewnij się, że Krok 1 (Node.js) i Krok 2 (komenda npm) zostały wykonane, a jeśli właśnie zainstalowano Node.js — uruchom ten program od nowa i spróbuj jeszcze raz.",
        "dlg_setup_check_title": "Konfiguracja programu — co jeszcze zostało",
        "dlg_setup_check_intro": "Sprawdziłem, co jest już gotowe. Uzupełnij punkty oznaczone <b>❗</b> — przy każdym napisałem, co zrobić, krok po kroku.",
        "dlg_setup_ready": "✅ gotowe",
        "dlg_setup_missing": "❗ do zrobienia",
        "dlg_setup_item_claude": "Claude Code — zainstalowany",
        "dlg_setup_item_login": "Claude Code — zalogowany",
        "dlg_setup_item_dictation": "Dyktowanie głosem — klucz Groq",
        "dlg_setup_dictation_intro": "Dyktowanie (mówienie zamiast pisania) to dodatek — program działa bez niego. Aby je włączyć, zdobądź <b>darmowy</b> klucz Groq i wklej go w Ustawieniach. Krok po kroku pokazuje strona poniżej.",
        "dlg_setup_groq_btn": "🔑 Jak zdobyć darmowy klucz Groq",
        "dlg_setup_settings_btn": "⚙️ Otwórz Ustawienia (wklej klucz)",
        "dlg_setup_dictation_dismiss": "Nie przypominaj mi o dyktowaniu",
        "dlg_setup_all_ready": "✅ Wszystko gotowe — możesz zaczynać pracę.",
        # --- Uszkodzona instalacja Claude Code (atrapa po nieudanym npm) ---
        "status_claude_broken": "Claude Code jest zainstalowany, ale uszkodzony — patrz okno z instrukcją naprawy",
        "dlg_setup_broken_chip": "USZKODZONY",
        "dlg_setup_broken_title": "Claude Code jest zainstalowany, ale uszkodzony",
        "dlg_setup_broken_intro": "Claude Code jest na tym komputerze, ale <b>nie da się go uruchomić</b> — instalacja skończyła się w połowie. To usterka po stronie instalatora npm, <b>nie</b> tego programu.",
        "dlg_setup_broken_why": "Paczka z npm nie zawiera gotowego programu — dociąga go osobnym krokiem już po instalacji. U Ciebie ten krok się nie wykonał, więc na dysku został sam plik zastępczy.",
        "dlg_setup_broken_why_windows": "Windows próbuje uruchomić ten plik zastępczy i pokazuje wtedy komunikat o „nieobsługiwanej aplikacji 16-bitowej”.",
        "dlg_setup_broken_path": "Uszkodzony plik: {path}",
        "dlg_setup_broken_steps_title": "Naprawa — jednorazowo, około 5 minut:",
        "dlg_setup_broken_step1": "1. Zamknij ten program.",
        "dlg_setup_broken_step2": "2. Otwórz PowerShell (Start → wpisz <b>powershell</b> → Enter) i przepisz po kolei oba polecenia poniżej, każde zatwierdzając Enterem.",
        "dlg_setup_broken_step2_unix": "2. Otwórz Terminal i przepisz po kolei oba polecenia poniżej, każde zatwierdzając Enterem.",
        "dlg_setup_broken_step3": "3. Zamknij PowerShell, otwórz nowy i sprawdź poleceniem <b>claude --version</b> — ma pokazać numer wersji, bez okienka o „aplikacji 16-bitowej”.",
        "dlg_setup_broken_step3_unix": "3. Zamknij Terminal, otwórz nowy i sprawdź poleceniem <b>claude --version</b> — ma pokazać numer wersji.",
        "dlg_setup_broken_step4": "4. Uruchom ten program i wejdź w Ustawienia → Komenda Claude Code → wpisz samo słowo <b>claude</b>.",
        "dlg_setup_broken_after": "Drugie polecenie wgrywa Claude Code prosto od Anthropic, z pominięciem npm — to npm zawiodło, więc powtarzanie instalacji przez npm zwykle nie pomaga.",
        "dlg_setup_broken_msg": "Claude Code jest zainstalowany, ale uszkodzony — instalacja z npm nie dokończyła się.\n\nWykonaj kroki naprawy z okna konfiguracji, a potem kliknij „Sprawdź ponownie”.",
        # --- i18n runda 2: dialogi main_window ---
        "dlg_cannot_close_title": "Nie można zamknąć",
        "dlg_must_keep_one_tab": "Musi pozostać co najmniej jedna zakładka.",
        "dlg_new_tab_tooltip": "Nowa zakładka",
        "dlg_agent_waiting_tooltip": "Agent czeka na odpowiedź",
        "dlg_agent_saved_msg": "Agent \"{name}\" został zapisany.\nZakładka pojawi się po restarcie aplikacji lub użyj 'Zarządzaj agentami'.",
        "dlg_many_agents_title": "Dużo aktywnych agentów",
        "dlg_many_agents_msg": "Masz już {active} aktywnych agentów, a Twój komputer ({total} GB RAM) bezpiecznie uniesie około {recommended}. Każdy agent uruchamia osobny proces Claude zużywający 3–5 GB pamięci.\n\nUruchomienie kolejnego może spowolnić lub zawiesić komputer.\n\nCzy na pewno uruchomić tego agenta?",
        "dlg_many_agents_msg_noram": "Masz już {active} aktywnych agentów. Każdy uruchamia osobny proces Claude zużywający 3–5 GB pamięci RAM.\n\nUruchomienie kolejnego może spowolnić lub zawiesić komputer.\n\nCzy na pewno uruchomić tego agenta?",
        "status_agents_saved": "Zapisano zmiany agentów.",
        "dlg_quick_add_title": "Dodaj szybką akcję",
        "dlg_quick_label_placeholder": "np. Sprawdź błędy",
        "dlg_quick_command_placeholder": "np. Sprawdź czy w kodzie są błędy i je napraw",
        "dlg_quick_action_name_label": "Nazwa akcji:",
        "dlg_quick_command_label": "Komenda:",
        "dlg_quick_no_name_msg": "Podaj nazwę akcji.",
        "dlg_quick_no_command_title": "Brak komendy",
        "dlg_quick_no_command_msg": "Podaj komendę.",
        "dlg_new_session_title": "Nowa sesja",
        "dlg_new_session_msg": "Czy na pewno chcesz rozpocząć nową sesję?",
        "dlg_about_title": "O programie {name}",
        "dlg_about_body": "<h2>{name}</h2><p>Wersja {version}</p><p>Asystent głosowy dla Claude Code.</p><p>© 2024 Fulfillment Polska</p>",
        "dlg_trial_start_title": "Rozpocznij trial",
        "dlg_trial_start_prompt": "Podaj adres email aby rozpocząć 30-dniowy trial:",
        "dlg_trial_active_title": "Trial aktywowany",
        "dlg_trial_active_msg": "Twój 30-dniowy trial został aktywowany!\nEmail: {email}",
        "dlg_trial_activate_failed": "Nie udało się aktywować trial.",
        "dlg_license_expired_title": "Licencja wygasła",
        "dlg_license_expired_msg": "Twoja licencja lub okres próbny wygasł.\nCzy chcesz kupić licencję?",
        "dlg_groq_required_title": "Dyktowanie wymaga klucza Groq",
        "dlg_groq_required_msg": "Aby dyktowanie głosem działało, dodaj darmowy klucz API Groq — służy do rozpoznawania mowy (zamiana głosu na tekst).\n\nUwaga: czytanie na głos działa bez klucza. Groq jest potrzebny WYŁĄCZNIE do dyktowania.\n\nDarmowy klucz zdobędziesz w minutę na:\nhttps://console.groq.com/keys\n(zaloguj się, kliknij 'Create API Key', skopiuj klucz 'gsk_...').\n\nCzy chcesz dodać klucz teraz?",
        "dlg_media_all_supported": "Wszystkie obsługiwane",
        "dlg_media_images": "Obrazy",
        "dlg_media_documents": "Dokumenty",
        "dlg_media_data": "Dane",
        "dlg_media_archives": "Archiwa",
        "dlg_media_all_files": "Wszystkie pliki",
        "dlg_media_add_title": "Dodaj media",
        "dlg_groq_key_title": "Klucz AI Managera (dyktowanie)",
        "dlg_groq_key_prompt": "Klucz jest potrzebny do dyktowania (zamiana mowy na tekst).\nCzytanie na głos działa bez klucza.\n\nDyktowanie idzie teraz przez bramkę AI Managera. Skąd wziąć klucz:\n1. Wejdź do panelu AI Managera.\n2. Otwórz aplikację 'Voice Assistant'.\n3. Skopiuj jej klucz (zaczyna się od 'aim-...') - UWAGA: pokazany jest tylko RAZ!\n4. Wklej go w pole poniżej i kliknij OK.\n\nAktualny klucz: {key}",
        "dlg_key_none": "brak",
        "dlg_groq_key_saved": "Klucz do dyktowania został zapisany.",
        "stt_err_bad_key": "Zły klucz AI Managera — wpisz klucz aplikacji „Voice Assistant\" w Ustawieniach.",
        "stt_err_rate_limit": "Za dużo dyktowania naraz — spróbuj ponownie za chwilę.",
        "stt_err_busy": "Bramka dyktowania jest chwilowo zajęta — spróbuj za moment.",
        # Dyktowanie — komunikaty, które MUSZĄ dotrzeć do użytkownika (2026-08-29).
        "stt_err_network": "Nie udało się wysłać nagrania — sprawdź internet. Powiedz to jeszcze raz.",
        "stt_err_empty": "Nie usłyszałem słów — powiedz to jeszcze raz, trochę dłużej.",
        "status_stt_busy": "Przetwarzam poprzednie nagranie — chwileczkę…",
        "status_stt_unblocked": "Dyktowanie odblokowane — mów.",
        "dlg_stt_failed_title": "Dyktowanie nie doszło",
        "dlg_stt_failed_msg": ("Nagranie nie zostało rozpoznane, więc nic nie wpisałem w pole poleceń.\n\n"
                               "Powód: {reason}\n\nPowiedz to jeszcze raz."),
        "dlg_anthropic_key_title": "Klucz API Anthropic",
        "dlg_anthropic_key_prompt": "Podaj klucz API Anthropic (Claude):\n\nAktualny: {key}",
        "dlg_anthropic_key_saved": "Klucz API Anthropic został zapisany.",
        "dlg_claude_cmd_title": "Komenda Claude Code",
        "dlg_claude_cmd_desc": "Podaj komendę uruchamiającą Claude Code w terminalu.\nTa komenda zostanie automatycznie wpisana po uruchomieniu programu.",
        "dlg_claude_cmd_command_label": "Komenda:",
        "dlg_claude_cmd_autorun": "Automatycznie uruchom po starcie programu",
        "dlg_claude_cmd_saved": "Komenda Claude Code została zapisana.\n\nKomenda: {command}\nAuto-uruchomienie: {autorun}",
        "dlg_yes": "Tak",
        "dlg_no": "Nie",
        "dlg_qa_manage_title": "Zarządzaj szybkimi akcjami",
        "dlg_qa_manage_header": "Zarządzaj swoimi szybkimi akcjami",
        "dlg_qa_col_label": "Etykieta",
        "dlg_qa_col_command": "Komenda",
        "dlg_qa_up": "▲ W górę",
        "dlg_qa_down": "▼ W dół",
        "dlg_qa_add_group": "Dodaj nową akcję",
        "dlg_qa_label_label": "Etykieta:",
        "dlg_qa_restore_defaults": "Przywróć domyślne",
        "dlg_qa_select_to_edit": "Wybierz akcję do edycji.",
        "dlg_qa_edit_title": "Edytuj akcję",
        "dlg_qa_select_to_delete": "Wybierz akcję do usunięcia.",
        "dlg_qa_confirm_delete_msg": "Czy na pewno usunąć akcję \"{label}\"?",
        "dlg_qa_no_label_title": "Brak etykiety",
        "dlg_qa_no_label_msg": "Podaj etykietę dla akcji.",
        "dlg_qa_no_command_title": "Brak komendy",
        "dlg_qa_no_command_msg": "Podaj komendę dla akcji.",
        "dlg_qa_restore_confirm_msg": "Czy na pewno przywrócić domyślne akcje?\nWszystkie Twoje akcje zostaną usunięte.",
        "dlg_skin_title": "Ustawienia skórki - Kolory i ikony",
        "dlg_skin_header": "Dostosuj kolory i ikony aplikacji",
        "dlg_skin_import": "📥 Importuj skórkę",
        "dlg_skin_export": "📤 Eksportuj skórkę",
        "dlg_skin_help_btn": "❓ Pomoc - Ikony",
        "dlg_skin_group_main": "Główne elementy",
        "dlg_skin_group_borders": "Obramowania i efekty",
        "dlg_skin_group_text": "Tekst i przyciski",
        "dlg_skin_group_terminal": "Terminal - tło i tekst",
        "dlg_skin_group_icon_colors": "Kolory ikon przycisków",
        "dlg_skin_group_icons": "Ikony przycisków",
        "dlg_skin_reset": "Przywróć domyślne (Ubuntu)",
        "dlg_skin_apply": "Zastosuj",
        "dlg_skin_pick_color": "Wybierz kolor: {name}",
        "dlg_skin_icon_normal_tooltip": "Ikona normalna (kliknij aby zmienić)",
        "dlg_skin_icon_active_tooltip": "Ikona aktywna (kliknij aby zmienić)",
        "dlg_skin_icon_processing_tooltip": "Ikona procesowania (kliknij aby zmienić)",
        "dlg_skin_change_icon_title": "Zmień ikonę: {name}",
        "dlg_skin_icon_input_label": "Wpisz emoji lub tekst dla stanu '{state}':\n(np. 🎤 lub tekst)",
        "dlg_skin_pick_icon_color_tooltip": "Zmień kolor ikony",
        "dlg_skin_pick_icon_color_title": "Wybierz kolor ikony",
        "dlg_skin_help_body": "\n<h2>🎨 Jak zmienić ikony przycisków</h2>\n\n<h3>📝 Instrukcja:</h3>\n<ol>\n<li>Kliknij na przycisk z ikoną którą chcesz zmienić</li>\n<li>Wpisz nowe emoji lub tekst</li>\n<li>Kliknij OK</li>\n</ol>\n\n<p><b>Ikona \"normalna\"</b> - wyświetlana gdy przycisk jest nieaktywny<br>\n<b>Ikona \"aktywna\"</b> - wyświetlana gdy przycisk jest wciśnięty/aktywny</p>\n\n<h3>⌨️ Jak wpisać emoji:</h3>\n<ul>\n<li><b>Windows:</b> Naciśnij <code>Win + .</code> (kropka)</li>\n<li><b>Linux:</b> Naciśnij <code>Ctrl + .</code> lub <code>Ctrl + Shift + E</code></li>\n<li><b>macOS:</b> Naciśnij <code>Ctrl + Cmd + Space</code></li>\n</ul>\n\n<h3>🌐 Strony z ikonami (skopiuj i wklej):</h3>\n<ul>\n<li><a href=\"https://emojipedia.org\">emojipedia.org</a> - wszystkie emoji</li>\n<li><a href=\"https://getemoji.com\">getemoji.com</a> - emoji do kopiowania</li>\n<li><a href=\"https://symbl.cc/en/\">symbl.cc</a> - symbole Unicode</li>\n<li><a href=\"https://unicode-table.com\">unicode-table.com</a> - tabela Unicode</li>\n<li><a href=\"https://fontawesome.com/search?o=r&m=free\">fontawesome.com</a> - ikony (skopiuj jako Unicode)</li>\n</ul>\n\n<h3>💡 Przykładowe ikony:</h3>\n<table>\n<tr><td><b>Mikrofon:</b></td><td>🎤 🎙️ 🎚️ 📢 🔴</td></tr>\n<tr><td><b>Głośnik:</b></td><td>🔊 🔉 🔈 🔇 📣 🎵</td></tr>\n<tr><td><b>Pauza/Play:</b></td><td>⏸️ ▶️ ⏯️ ⏹️ ⏺️</td></tr>\n<tr><td><b>Stop:</b></td><td>⬜ ⏹️ 🛑 ❌ ✖️</td></tr>\n<tr><td><b>Kopiuj:</b></td><td>⧉ 📋 📄 📑 ✂️</td></tr>\n<tr><td><b>Wyślij:</b></td><td>↵ ➡️ 📤 📨 ✈️</td></tr>\n<tr><td><b>Akcje:</b></td><td>⚡ ⭐ 💫 🔥 ✨</td></tr>\n</table>\n\n<h3>📁 Import/Eksport skórki:</h3>\n<p>Możesz zapisać swoją skórkę do pliku <code>.skin.json</code> i udostępnić innym,\nlub wczytać skórkę od kogoś innego.</p>\n",
        "dlg_skin_help_title": "Pomoc - Ikony i skórki",
        "dlg_skin_import_title": "Importuj skórkę",
        "dlg_skin_filter": "Pliki skórki (*.skin.json);;Wszystkie pliki (*)",
        "dlg_skin_success_title": "Sukces",
        "dlg_skin_loaded_msg": "Skórka wczytana z:\n{path}",
        "dlg_skin_load_failed_msg": "Nie udało się wczytać skórki:\n{error}",
        "dlg_skin_export_title": "Eksportuj skórkę",
        "dlg_skin_default_name": "Moja skórka",
        "dlg_skin_saved_msg": "Skórka zapisana do:\n{path}",
        "dlg_skin_save_failed_msg": "Nie udało się zapisać skórki:\n{error}",
        "dlg_settings_title": "Ustawienia",
        "dlg_settings_groq_label": "Klucz API Groq:",
        "dlg_license_title": "Licencja",
        "dlg_license_status": "Status: {status}",
        "dlg_license_email": "Email: {email}",
        "dlg_license_trial_days": "Pozostało dni trial: {days}",
        "dlg_license_key_label": "Wprowadź klucz licencji:",
        "dlg_license_activate": "Aktywuj licencję",
        "dlg_license_buy": "Kup licencję",
        "dlg_license_success_title": "Sukces",
        # nazwy kolorów skórki
        "skin_color_main_window_bg": "Tło głównego okna",
        "skin_color_menu_bar_bg": "Tło paska menu",
        "skin_color_status_bar_bg": "Tło paska statusu",
        "skin_color_bottom_panel_bg": "Tło panelu przycisków",
        "skin_color_border_color": "Kolor obramowań",
        "skin_color_hover_color": "Kolor podświetlenia (hover)",
        "skin_color_splitter_color": "Kolor rozdzielacza",
        "skin_color_text_color": "Kolor tekstu interfejsu",
        "skin_color_button_bg": "Tło przycisków",
        "skin_color_button_hover": "Przycisk przy najechaniu",
        "skin_color_input_bg": "Tło pola tekstowego",
        "skin_color_inactive_panel_bg": "Panel nieaktywny",
        "skin_color_terminal_bg": "Tło terminala",
        "skin_color_terminal_fg": "Tekst terminala",
        "skin_color_terminal_color_0": "Czarny",
        "skin_color_terminal_color_1": "Czerwony",
        "skin_color_terminal_color_2": "Zielony",
        "skin_color_terminal_color_3": "Żółty",
        "skin_color_terminal_color_4": "Niebieski",
        "skin_color_terminal_color_5": "Magenta (fioletowy)",
        "skin_color_terminal_color_6": "Cyan (turkusowy)",
        "skin_color_terminal_color_7": "Biały",
        "skin_color_terminal_color_0_bright": "Jasny czarny (szary)",
        "skin_color_terminal_color_1_bright": "Jasny czerwony",
        "skin_color_terminal_color_2_bright": "Jasny zielony",
        "skin_color_terminal_color_3_bright": "Jasny żółty",
        "skin_color_terminal_color_4_bright": "Jasny niebieski",
        "skin_color_terminal_color_5_bright": "Jasna magenta",
        "skin_color_terminal_color_6_bright": "Jasny cyan",
        "skin_color_terminal_color_7_bright": "Jasny biały",
        "skin_color_icon_dictate_color": "Kolor ikony mikrofonu",
        "skin_color_icon_read_color": "Kolor ikony głośnika",
        "skin_color_icon_pause_color": "Kolor ikony pauzy",
        "skin_color_icon_stop_color": "Kolor ikony stop",
        "skin_color_icon_copy_color": "Kolor ikony kopiuj",
        "skin_color_icon_clear_input_color": "Kolor ikony wyczyść",
        "skin_color_icon_add_media_color": "Kolor ikony dodaj media",
        "skin_color_icon_send_color": "Kolor ikony wyślij",
        "skin_color_icon_quick_actions_color": "Kolor ikony szybkich akcji",
        "skin_color_icon_search_color": "Kolor ikony lupy",
        # nazwy ikon skórki
        "skin_icon_dictate": "Mikrofon (dyktowanie)",
        "skin_icon_read": "Głośnik (czytanie)",
        "skin_icon_pause": "Pauza",
        "skin_icon_stop": "Stop",
        "skin_icon_copy": "Kopiuj",
        "skin_icon_clear_input": "Wyczyść pole",
        "skin_icon_add_media": "Dodaj media",
        "skin_icon_send": "Wyślij",
        "skin_icon_quick_actions": "Szybkie akcje",
    },
    "en-US": {
        "app_title": "Vibe Coding Assistant",
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
        "read_tooltip": "Read selected text or last response (hold Shift to select when Claude uses the mouse)",
        "pause_tooltip": "Pause / Resume",
        "stop_tooltip": "Stop everything",
        "copy_tooltip": "Copy selected text (hold Shift to select when Claude uses the mouse)",
        "mouse_mode_scroll": "Mouse: scroll",
        "mouse_mode_select": "Mouse: select",
        "mouse_mode_tooltip": ("Switch how the mouse works in the terminal:\n"
                               "• Scroll — the wheel scrolls the Claude conversation, you click menu"
                               " options, and select text with Shift.\n"
                               "• Select — select and copy text by dragging without Shift"
                               " (wheel/click no longer go to Claude)."),
        "status_mouse_scroll": "Mouse: scroll (wheel scrolls Claude, select with Shift)",
        "status_mouse_select": "Mouse: select text without Shift",
        "repair_terminal_tooltip": ("Fix the terminal display when text becomes\n"
                                    "\"spaced out\" (gaps between letters, ─ ─ ─ rules).\n"
                                    "Saves a diagnostic snapshot and restarts Claude Code\n"
                                    "keeping the current conversation."),
        "status_terminal_repair": "Fixing terminal display — resuming conversation…",
        "status_tts_catchup": "Narrator fell behind — skipping to the newest response",
        "status_login_checking": "Tab {name}: login error — checking whether tabs raced…",
        "status_login_race": "Tab {name}: not a logout — tabs raced for the token. Just restart it (Stop → Run)",
        "status_login_real": "Claude Code is logged out — type /login in the {name} tab terminal",
        "menu_cloud": "Cloud — agents on another computer…",
        "cloud_title": "Cloud",
        "cloud_account": "Google account",
        "cloud_connect": "Connect to Google",
        "cloud_disconnect": "Disconnect account",
        "cloud_connected": "Connected to Google Drive.",
        "cloud_not_connected": "Not connected. Click “Connect to Google” — your browser will open.",
        "cloud_disconnected": "Account disconnected. The bundle in the cloud was left untouched.",
        "cloud_no_client": "Google client details are missing — the account cannot be connected without them.",
        "cloud_scope_note": "The app can see ONLY the files it creates itself — it has no access to the rest of your Drive. Bundles go to the “{folder}” folder.",
        "cloud_pass_header": "Bundle password",
        "cloud_pass_desc": "The bundle is encrypted on your computer. Google stores only an unreadable file — without this password nobody can read it.",
        "cloud_pass_placeholder": "Generate a code or type your own password",
        "cloud_pass_generate": "Generate code",
        "cloud_pass_warn": "⚠️ Write this code down away from the computer (e.g. on paper). Lose it and the bundle cannot be recovered.",
        "cloud_pass_written": "The code is in the field. Write it on paper — you will need it on the other computer.",
        "cloud_transfer": "Transfer",
        "cloud_send": "Send agent brain to the cloud",
        "cloud_send_desc": "Sends agents, memory files, skills, quick actions and settings. It does NOT send project code — you pull that from git.",
        "cloud_get": "Download from the cloud to this computer",
        "cloud_get_desc": "Restores agents from the bundle and remaps their paths to the folder you choose.",
        "cloud_connect_working": "Opening your browser — confirm access in the Google window…",
        "cloud_connect_ok": "Connected to Google Drive.",
        "cloud_send_working": "Packing and encrypting…",
        "cloud_sent_ok": "Sent to the cloud ({kb} KB).",
        "cloud_get_working": "Downloading and decrypting…",
        "cloud_got_ok": "Done — {agents} agents restored. The code of {clone} projects still needs to be pulled from git (the agents keep their addresses). Restart the app to see them.",
        "cloud_need_pass": "Set the bundle password first — generate a code or type your own.",
        "cloud_pick_root": "Choose the folder where you keep your projects",
        "cloud_overwrite_title": "Overwrite agents?",
        "cloud_overwrite_text": "Downloading will replace the agents and settings on this computer with the bundle from the cloud. Continue?",
        "cloud_err": "Failed: {error}",
        "status_terminal_snapshot_only": "Terminal snapshot saved (no session to resume)",
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
        "menu_groq_api": "AI Manager key (dictation)...",
        "menu_anthropic_api": "Anthropic API key...",
        "menu_claude_command": "Claude Code command...",
        "menu_check_models": "Check for new models",
        "status_checking_models": "Checking the model list...",
        "status_models_updated": "Model names updated: {changes}",
        "models_up_to_date": "The model list is up to date.",
        "models_new_family": ("Anthropic released a new model: {names}.\n\n"
                              "It was not added automatically — your installed "
                              "Claude Code may not support it yet. Please report "
                              "it to the app author."),
        "models_check_failed": ("Could not fetch the model list.\n\n{error}\n\n"
                                "Nothing is broken — the app keeps the names it "
                                "saved earlier."),
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
        "model_default_full": "Default (from Claude Code config)",
        "model_default_short": "Default",
        # "Default" setting + the model DETECTED from the session transcript.
        "model_default_detected": "Default ({name})",
        "model_detected_line": "Currently answering: {name}",
        # Descriptions only — the model name comes from CLAUDE_MODELS/catalog.
        "model_fable_desc": "most powerful, for the hardest tasks",
        "model_opus_desc": "most capable",
        "model_sonnet_desc": "fast, balanced",
        "model_haiku_desc": "fastest",
        "model_claude_opus_4_8_desc": "older Opus — fewer tokens per task",
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
        "status_copied_chars": "Copied to clipboard ({n} characters)",
        "status_copy_no_selection": "Nothing selected — select text in the terminal (hold Shift if Claude uses the mouse)",
        "status_copied_clipboard": "Copied to clipboard",
        # 🔍 Conversation search (bottom bar, Ctrl+F)
        "search_tooltip": "Search the conversation (Ctrl+F)",
        "search_title": "Search the conversation",
        "search_placeholder": "Type what to look for (accents optional)...",
        "search_prev": "Previous match",
        "search_next": "Next match",
        "search_copy": "Copy",
        "search_read": "Read aloud",
        "search_close": "Close",
        "search_count": "Found {hits} {hits_word} in {entries} {entries_word}",
        "search_word_hit_one": "time",
        "search_word_hit_many": "times",
        "search_word_entry_one": "message",
        "search_word_entry_many": "messages",
        "search_none": "Nothing like that in this conversation",
        "search_empty_journal": "This tab has no conversation log yet",
        "search_role_user": "You",
        "search_role_assistant": "Claude",
        "search_copied": "Copied to clipboard",
        "search_scrolled": "Scrolled the terminal to this spot",
        "search_not_on_screen": "This fragment is no longer in the terminal window",
        "status_reading_last": "Reading the last response...",
        "status_reading_wait": "⏳ The agent is still writing — waiting for the answer to finish...",
        "status_reading_wait_timeout": "The agent is still writing — there is no new answer yet. Click 🔊 again in a moment.",
        "status_reading_wait_stalled": "The agent has not written a new answer yet. Click 🔊 again in a moment.",
        "status_reading_nothing_new": "The agent is working — nothing new since the last read.",
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
        "status_unread_backlog": "🔔 {n} unread responses in this tab — click 🔊 to catch up",
        # === Dialogs (src/gui/dialogs.py) ===
        # --- Shared buttons ---
        "dlg_cancel": "Cancel",
        "dlg_save": "Save",
        "dlg_close": "Close",
        "dlg_delete": "Delete",
        "dlg_edit": "Edit",
        "dlg_add": "Add",
        "dlg_refresh": "Refresh",
        "dlg_next": "Next →",
        "dlg_no_selection_title": "No selection",
        "dlg_no_name_title": "No name",
        "dlg_no_data_title": "Missing data",
        "dlg_confirm_delete_title": "Confirm deletion",
        "dlg_added_title": "Added",
        "dlg_installed_title": "Installed",
        "dlg_removed_title": "Removed",
        "dlg_saved_title": "Saved",
        "dlg_not_found_title": "Not found",
        "dlg_save_error_title": "Save error",
        "dlg_add_error_title": "Error adding",
        "dlg_delete_error_title": "Error deleting",
        "dlg_edit_error_title": "Error editing",
        "dlg_install_error_title": "Installation error",
        "dlg_error_title": "Error",
        "dlg_no_dir_title": "No directory",
        "dlg_set_valid_dir_first": "First set a valid working directory.",
        # --- Styled file dialogs ---
        "dlg_file_look_in": "Look in:",
        "dlg_file_name": "Name:",
        "dlg_file_type": "File type:",
        "dlg_file_select": "Select",
        "dlg_file_save": "Save",
        # --- MemoryProjectsDialog ---
        "dlg_mem_title": "Project memory files",
        "dlg_mem_cannot_save": "Could not save: {error}",
        "dlg_mem_header": "Manage projects and their memory files",
        "dlg_mem_desc": "Memory files are automatically sent to Claude Code as context when a session starts.",
        "dlg_mem_col_name": "Name",
        "dlg_mem_col_path": "Path",
        "dlg_mem_add_project": "Add project",
        "dlg_mem_add_file": "Add file",
        "dlg_mem_add_folder": "Add folder",
        "dlg_mem_unnamed": "Unnamed",
        "dlg_mem_no_file": "No file",
        "dlg_mem_select_project_for_file": "Select the project you want to add a file to.",
        "dlg_mem_select_project_for_files": "Select the project you want to add files to.",
        "dlg_mem_file_filter": "Memory files (*.md *.txt *.json);;All files (*)",
        "dlg_mem_choose_files": "Choose memory files",
        "dlg_mem_choose_folder": "Choose a folder with files",
        "dlg_mem_files_added_title": "Files added",
        "dlg_mem_files_added_n": "Added {n} files from the folder.",
        "dlg_mem_no_files_title": "No files",
        "dlg_mem_no_new_files": "No new files found to add.",
        "dlg_mem_select_to_edit": "Select an item to edit.",
        "dlg_mem_select_to_delete": "Select an item to delete.",
        "dlg_mem_confirm_delete_project": 'Are you sure you want to delete the project "{name}" and all its files?',
        "dlg_mem_confirm_delete_file": 'Are you sure you want to delete the file "{name}"?',
        # --- ProjectEditDialog ---
        "dlg_proj_edit_title": "Edit project",
        "dlg_proj_new_title": "New project",
        "dlg_proj_name_placeholder": "e.g. Fulfillment CRM",
        "dlg_proj_name_label": "Project name:",
        "dlg_proj_give_name": "Enter a project name.",
        # --- AgentConfigDialog ---
        "dlg_agent_edit_title": "Edit agent",
        "dlg_agent_new_title": "New agent",
        "dlg_agent_config_header": "Agent configuration",
        "dlg_agent_save_run": "Save and run",
        "dlg_agent_tab_basic": "📝 Basics",
        "dlg_agent_tab_memory": "💾 Memory",
        "dlg_agent_tab_skills": "🧩 Skills",
        "dlg_agent_tab_mcp": "🔌 MCP",
        "dlg_agent_name_placeholder": "e.g. CRM Development",
        "dlg_agent_name_label": "Agent name:",
        "dlg_agent_working_dir_label": "Working directory:",
        "dlg_agent_model_label": "Claude Code model:",
        "dlg_agent_model_hint": "Changing the model requires restarting the agent (Stop → Run).",
        "dlg_agent_auto_start": "Start automatically when the app launches",
        "dlg_agent_load_memory": "Load memory files after Claude Code starts",
        "dlg_agent_icon_label": "Tab icon",
        "dlg_agent_icon_emoji_ph": "Emoji (type or paste)",
        "dlg_agent_icon_file_btn": "📁 File…",
        "dlg_agent_icon_clear": "Clear",
        "dlg_agent_icon_file_title": "Choose an icon (image)",
        "dlg_agent_icon_hint": "Click the preview (🤖) to pick from a ready-made icon set. You can also type your own emoji or choose an image (PNG/SVG). Empty = default 🤖.",
        "dlg_agent_icon_pick_tooltip": "Click to pick an icon from the ready-made set",
        "dlg_agent_color_label": "Tab color",
        "dlg_agent_color_clear": "No color",
        "dlg_agent_color_tooltip": "Click to pick any tab color",
        "dlg_agent_color_hint": "The color tints this tab's text and the whole window's frame while the tab is active. Pick from the palette, or click the square on the left for the full color picker. Empty = no color.",
        "dlg_agent_voice_label": "Reading voice",
        "dlg_agent_voice_default": "Default (by app language)",
        "dlg_agent_voice_more": "🌐 More voices…",
        "dlg_agent_voice_loading": "Downloading voices from the internet…",
        "dlg_agent_voice_load_failed": "Could not download the voice list (no internet?)",
        "dlg_agent_voice_search_title": "Choose a voice — search by language",
        "dlg_agent_voice_search_ph": "Search language or voice (e.g. polish, english, german, ja-JP)…",
        "dlg_agent_voice_search_count": "Matching voices: {n}",
        "dlg_agent_voice_hint": "The voice used to read this tab's responses aloud. Empty = the default voice for the app language. The built-in list has Polish and English voices; \"More voices…\" opens the full internet list with search by language.",
        "dlg_agent_icon_cat_dev": "Programming",
        "dlg_agent_icon_cat_sales": "Sales",
        "dlg_agent_icon_cat_seo": "SEO / positioning",
        "dlg_agent_icon_cat_social": "Social media / marketing",
        "dlg_agent_icon_cat_project": "Projects / work",
        "dlg_agent_memory_files_label": "📄 Agent memory files:",
        "dlg_agent_memory_info": "ℹ️ Files loaded when the agent starts — Claude Code receives them as conversation context.",
        "dlg_agent_add_file": "+ Add file",
        "dlg_agent_skills_label": "🧩 This agent's skills:",
        "dlg_agent_skills_info": "ℹ️ Every agent inherits the global skills from the Extensions menu. Here you can add extra ones — visible only to this agent.",
        "dlg_agent_disable_skills_label": "🚫 Disable global skills for this agent:",
        "dlg_agent_disable_skills_info": "ℹ️ Global skills are enabled by default. Uncheck the ones this agent should not use. Changes are saved immediately.",
        "dlg_agent_mcp_label": "🔌 This agent's MCP servers:",
        "dlg_agent_mcp_info": "ℹ️ Every agent inherits the global MCP servers from the Extensions menu. Here you can add extra ones — working only in this agent's directory.",
        "dlg_agent_disable_mcp_label": "🚫 Disable global MCP for this agent:",
        "dlg_agent_disable_mcp_info": "ℹ️ Global MCP servers are enabled by default. Uncheck the ones this agent should not use. Changes are saved immediately.",
        "dlg_agent_choose_working_dir": "Choose a working directory",
        "dlg_agent_give_name": "Enter an agent name.",
        "dlg_agent_invalid_dir_title": "Invalid directory",
        "dlg_agent_dir_not_exist": "The given directory does not exist.",
        "dlg_agent_manage_skills_no_dir": "🧩 Manage local skills (set a valid directory first)",
        "dlg_agent_manage_skills_none": "🧩 Manage local skills (none)",
        "dlg_agent_manage_skills_1": "🧩 Manage local skills (1 installed)",
        "dlg_agent_manage_skills_few": "🧩 Manage local skills ({n} installed)",
        "dlg_agent_manage_skills_many": "🧩 Manage local skills ({n} installed)",
        "dlg_agent_skills_local_tooltip": "Local skills for this agent ({path})",
        "dlg_agent_skills_save_failed": "Could not save settings: {error}",
        "dlg_agent_manage_mcp_no_dir": "🔌 Manage local MCP (set a valid directory first)",
        "dlg_agent_manage_mcp_none": "🔌 Manage local MCP (none)",
        "dlg_agent_manage_mcp_1": "🔌 Manage local MCP (1 installed)",
        "dlg_agent_manage_mcp_few": "🔌 Manage local MCP ({n} installed)",
        "dlg_agent_manage_mcp_many": "🔌 Manage local MCP ({n} installed)",
        "dlg_agent_mcp_local_tooltip": "Local MCP servers for this agent ({path})",
        "dlg_agent_mcp_save_failed": "Could not save MCP settings: {error}",
        "dlg_agent_skills_no_desc": "(no description)",
        "dlg_agent_skills_count_no_dir": "⚠ First set a valid working directory.",
        "dlg_agent_skills_count_none": "No global skills installed. Install them in the Extensions → Skills menu.",
        "dlg_agent_disabled_of_global": "{disabled} of {total} global ones disabled for this agent.",
        "dlg_agent_mcp_count_none": "No global MCP servers. Add them in the Extensions → MCP servers menu.",
        "dlg_agent_fallback_name": "Agent",
        "dlg_agent_choose_memory_files": "Choose memory files",
        # --- AgentsManagerDialog ---
        "dlg_agents_title": "Manage agents",
        "dlg_agents_header": "Manage agents (terminal tabs)",
        "dlg_agents_desc": "Each agent is a separate tab with its own terminal and assigned memory project.",
        "dlg_agents_move_up": "▲ Up",
        "dlg_agents_move_down": "▼ Down",
        "dlg_agents_run": "▶️ Run",
        "dlg_agents_add": "➕ Add",
        "dlg_agents_edit": "✏️ Edit",
        "dlg_agents_duplicate": "📋 Duplicate",
        "dlg_agents_delete": "🗑️ Delete",
        "dlg_agents_no_files": "No files",
        "dlg_agents_files_1": "1 file",
        "dlg_agents_files_few": "{n} files",
        "dlg_agents_files_many": "{n} files",
        "dlg_agents_unnamed": "Unnamed",
        "dlg_agents_loading": "⏳ loading…",
        "dlg_agents_skills_loading_tooltip": "Loading this agent's skills list...",
        "dlg_agents_mcp_loading_tooltip": "Loading this agent's MCP list (requires running 'claude mcp list')...",
        "dlg_agents_skills_error": "⚠ skills error",
        "dlg_agents_skills_error_tooltip": "Could not load skills:\n{error}",
        "dlg_agents_mcp_error": "⚠ MCP error",
        "dlg_agents_mcp_error_tooltip": "Could not load MCP:\n{error}",
        "dlg_agents_mem_tooltip_header": "This agent's memory files:",
        "dlg_agents_mem_tooltip_none": "This agent's memory files:\n\n   (no memory files)",
        "dlg_agents_local_1": "{n} local",
        "dlg_agents_local_few": "{n} local",
        "dlg_agents_local_many": "{n} local",
        "dlg_agents_global_1": "{n} global",
        "dlg_agents_global_few": "{n} global",
        "dlg_agents_global_many": "{n} global",
        "dlg_agents_skills_unknown": "⚠ skills unknown",
        "dlg_agents_skills_unknown_tooltip": "The agent's working directory is empty or does not exist —\nthe skills list cannot be read.",
        "dlg_agents_no_skills": "🚫 no skills",
        "dlg_agents_skills_global": "🧩 {global}",
        "dlg_agents_skills_global_local": "🧩 {global} + {local}",
        "dlg_agents_skills_cut": "✂️ {on} of {total} global",
        "dlg_agents_skills_cut_local": "✂️ {on} of {total} global + {local}",
        "dlg_agents_skills_tooltip_header": "This agent's skills:",
        "dlg_agents_tooltip_global_active": "\n✓ Global active ({n}):",
        "dlg_agents_tooltip_global_disabled": "\n✗ Global disabled ({n}):",
        "dlg_agents_tooltip_local": "\n+ Local ({n}):",
        "dlg_agents_skills_tooltip_none": "\n(no skills installed)",
        "dlg_agents_mcp_unknown": "⚠ MCP unknown",
        "dlg_agents_mcp_unknown_tooltip": "The agent's working directory is empty or does not exist —\nthe MCP list cannot be read.",
        "dlg_agents_mcp_fetch_failed_tooltip": "Could not fetch the MCP list (is the 'claude' command inactive?).",
        "dlg_agents_no_mcp": "🚫 no MCP",
        "dlg_agents_mcp_global": "🔌 {global}",
        "dlg_agents_mcp_global_local": "🔌 {global} + {local}",
        "dlg_agents_mcp_cut": "✂️ {on} of {total} global MCP",
        "dlg_agents_mcp_cut_local": "✂️ {on} of {total} global MCP + {local}",
        "dlg_agents_mcp_tooltip_header": "This agent's MCP servers:",
        "dlg_agents_mcp_tooltip_none": "\n(no MCP registered)",
        "dlg_agents_select_to_run": "Select an agent to run.",
        "dlg_agents_select_to_edit": "Select an agent to edit.",
        "dlg_agents_select_to_duplicate": "Select an agent to duplicate.",
        "dlg_agents_select_to_delete": "Select an agent to delete.",
        "dlg_agents_copy_suffix": "{name} (copy)",
        "dlg_agents_cannot_delete_title": "Cannot delete",
        "dlg_agents_must_keep_one": "At least one agent must remain.",
        "dlg_agents_confirm_delete": 'Are you sure you want to delete the agent "{name}"?',
        # --- SkillsManagerDialog ---
        "dlg_skills_agent_title_named": "Agent skills — {name}",
        "dlg_skills_agent_title": "Agent skills",
        "dlg_skills_global_title": "Skills",
        "dlg_skills_agent_header_named": "🧩 Agent skills — {name}",
        "dlg_skills_agent_header": "🧩 Agent skills",
        "dlg_skills_agent_desc": "Skills here are visible ONLY to this agent. Global skills (for all agents) are managed in the Extensions → Skills menu.",
        "dlg_skills_global_desc": "Skills extend Claude Code with ready-made procedures (e.g. PDF analysis, creating documents). Claude activates them itself when their description matches the conversation.",
        "dlg_skills_location": "📂 Location: {path}",
        "dlg_skills_add_zip": "📦 Add from ZIP",
        "dlg_skills_add_folder": "📂 Add from folder",
        "dlg_skills_show_folder": "📁 Show folder",
        "dlg_skills_refresh": "🔄 Refresh",
        "dlg_skills_delete": "🗑️ Delete",
        "dlg_skills_empty": 'No skills installed.\nUse "Add from ZIP" or "Add from folder" to install the first one.',
        "dlg_skills_no_desc": "(no description)",
        "dlg_skills_zip_filter": "ZIP file (*.zip);;All files (*)",
        "dlg_skills_choose_zip": "Choose a ZIP file with a skill",
        "dlg_skills_choose_folder": "Choose a folder with a skill",
        "dlg_skills_already_exists_marker": "już istnieje",
        "dlg_skills_already_exists_title": "Skill already exists",
        "dlg_skills_overwrite_prompt": "{msg}\n\nOverwrite the existing skill?",
        "dlg_skills_unexpected_error": "Unexpected error: {error}",
        "dlg_skills_installed_msg": 'Skill "{name}" has been installed.',
        "dlg_skills_select_to_delete": "Select a skill to delete.",
        "dlg_skills_confirm_delete": 'Are you sure you want to delete the skill "{name}"?\nThe folder will be permanently removed:\n{path}',
        "dlg_skills_removed_msg": 'Skill "{name}" has been removed.',
        "dlg_skills_folder_gone": "The skill folder no longer existed.",
        # --- MCP status / scope ---
        "dlg_mcp_status_connected": "Active",
        "dlg_mcp_status_needs_auth": "Needs authorization",
        "dlg_mcp_status_failed": "Connection error",
        "dlg_mcp_status_unknown": "Status unknown",
        "dlg_mcp_scope_user": "global",
        "dlg_mcp_scope_local": "local (agent)",
        "dlg_mcp_scope_managed": "managed (claude.ai)",
        # --- McpManagerDialog ---
        "dlg_mcp_agent_title_named": "Agent MCP servers — {name}",
        "dlg_mcp_agent_title": "Agent MCP servers",
        "dlg_mcp_global_title": "MCP servers",
        "dlg_mcp_agent_header_named": "🔌 Agent MCP servers — {name}",
        "dlg_mcp_agent_header": "🔌 Agent MCP servers",
        "dlg_mcp_agent_desc": "Servers added here work ONLY in this agent's directory. Global servers (for all agents) are managed in the Extensions → MCP servers menu.",
        "dlg_mcp_global_header": "🔌 MCP servers (Model Context Protocol)",
        "dlg_mcp_global_desc": "MCP servers are \"tool plugins\" for Claude Code — they let the agent read your disk, calendar, databases, send messages, etc. Claude decides on its own when to use them.",
        "dlg_mcp_add_template": "📚 Add from template...",
        "dlg_mcp_add_manual": "✏️ Add manually...",
        "dlg_mcp_add_json": "📋 Add from JSON...",
        "dlg_mcp_authorize": "🔓 Authorize",
        "dlg_mcp_authorize_tooltip": "For servers requiring authorization (claude.ai, OAuth)",
        "dlg_mcp_test": "🔍 Test",
        "dlg_mcp_test_tooltip": "Check whether the selected server responds",
        "dlg_mcp_edit": "✏️ Edit",
        "dlg_mcp_edit_tooltip": "Edit the selected server (does not work for servers managed by claude.ai)",
        "dlg_mcp_refresh": "🔄 Refresh",
        "dlg_mcp_delete": "🗑️ Delete",
        "dlg_mcp_fetch_failed": "Could not fetch the MCP list:\n{error}",
        "dlg_mcp_empty": 'No MCP servers.\nUse "Add from template" to install the first one.',
        "dlg_mcp_added_msg": 'Server "{name}" has been added.\n\n{hint}',
        "dlg_mcp_added_simple": 'Server "{name}" has been added.',
        "dlg_mcp_select_to_authorize": "Select a server to authorize.",
        "dlg_mcp_browser_opened_title": "Browser opened",
        "dlg_mcp_browser_opened_msg": 'I opened the claude.ai integrations panel. Sign in there and authorize the server "{name}". When done, come back here and click "🔄 Refresh".',
        "dlg_mcp_oauth_title": "OAuth authorization",
        "dlg_mcp_oauth_msg": 'To authorize the server "{name}":\n\n1. Open Claude Code in the directory:\n   {dir}\n\n2. Ask it to use this server in any way (e.g. "show me the list of tools from {name}").\n\n3. Claude Code will open a browser and guide you through OAuth.\n\n4. Come back here and click "🔄 Refresh".',
        "dlg_mcp_select_to_test": "Select a server to test.",
        "dlg_mcp_test_error_title": "Test error",
        "dlg_mcp_server_gone": 'Server "{name}" no longer exists in the configuration.',
        "dlg_mcp_test_result_title": "Test result",
        "dlg_mcp_test_result_msg": '{icon} Server "{name}"\n\nStatus: {status}\nCheck time: {ms} ms\nRaw status: {raw}',
        "dlg_mcp_raw_status_none": "(none)",
        "dlg_mcp_select_to_edit": "Select a server to edit.",
        "dlg_mcp_managed_title": "Managed server",
        "dlg_mcp_managed_edit_msg": 'Server "{name}" is managed by claude.ai and cannot be edited from this application.',
        "dlg_mcp_updated_msg": 'Server "{name}" has been updated.',
        "dlg_mcp_select_to_delete": "Select a server to delete.",
        "dlg_mcp_managed_delete_msg": 'Server "{name}" is managed by claude.ai and cannot be deleted from this application. To detach it, sign in to claude.ai and unpin the integration in settings.',
        "dlg_mcp_confirm_delete": 'Are you sure you want to delete the MCP server "{name}" (scope: {scope})?',
        "dlg_mcp_deleted_msg": 'Server "{name}" has been deleted.',
        # --- _McpTemplatePickerDialog ---
        "dlg_mcptpl_title": "Choose an MCP template",
        "dlg_mcptpl_header": "📚 Choose an MCP server template",
        "dlg_mcptpl_desc": "Each template is a ready-made MCP server — click it and provide the required data (e.g. token, path). Configuration details are in the next step.",
        "dlg_mcptpl_select": "Select a template from the list.",
        # --- _McpTemplateConfigDialog ---
        "dlg_mcpcfg_title": "Configuration: {title}",
        "dlg_mcpcfg_server_name": "Server name:",
        "dlg_mcpcfg_optional_prefix": "(optional) {label}",
        "dlg_mcpcfg_env_opt_label": "{key} (opt.):",
        "dlg_mcpcfg_scope_user": "Global (for all agents)",
        "dlg_mcpcfg_scope_local": "Local (this agent only)",
        "dlg_mcpcfg_scope_label": "Scope:",
        "dlg_mcpcfg_docs": "📖 Server documentation",
        "dlg_mcpcfg_install": "✅ Install",
        "dlg_mcpcfg_give_server_name": "Enter a server name.",
        "dlg_mcpcfg_field_required": 'The "{label}" field is required.',
        "dlg_mcpcfg_unknown_transport": "Unknown template transport: {transport}",
        # --- _McpAddManualDialog ---
        "dlg_mcpman_edit_title": "Edit MCP server — {name}",
        "dlg_mcpman_add_title": "Add MCP server manually",
        "dlg_mcpman_edit_header": "✏️ Edit MCP server",
        "dlg_mcpman_add_header": "✏️ Add MCP server manually",
        "dlg_mcpman_edit_note": "ℹ️ Changes will be saved as: removal of the old entry + adding one with the new data. On error — automatic rollback to the previous configuration.",
        "dlg_mcpman_name_placeholder": "e.g. my-tool",
        "dlg_mcpman_name_label": "Name:",
        "dlg_mcpman_transport_stdio": "stdio (local command)",
        "dlg_mcpman_transport_http": "http (HTTP server)",
        "dlg_mcpman_transport_sse": "sse (Server-Sent Events)",
        "dlg_mcpman_transport_label": "Transport:",
        "dlg_mcpman_args_placeholder": "-y @scope/package arg1 arg2  (separate with spaces)",
        "dlg_mcpman_command_label": "Command:",
        "dlg_mcpman_args_label": "Arguments:",
        "dlg_mcpman_url_label": "URL:",
        "dlg_mcpman_env_placeholder": "KEY1=value1\nKEY2=value2",
        "dlg_mcpman_env_label": "ENV (one per line):",
        "dlg_mcpman_headers_placeholder": "Authorization: Bearer xxx\nX-Api-Key: yyy",
        "dlg_mcpman_headers_label": "Headers (one per line):",
        "dlg_mcpman_scope_label": "Scope:",
        "dlg_mcpman_ok_save": "💾 Save",
        "dlg_mcpman_ok_add": "✅ Add",
        "dlg_mcpman_name_immutable_tooltip": "In edit mode the name cannot be changed.",
        "dlg_mcpman_give_server_name": "Enter a server name.",
        "dlg_mcpman_no_command_title": "No command",
        "dlg_mcpman_give_command": "Enter a command to run.",
        "dlg_mcpman_bad_url_title": "Bad URL",
        "dlg_mcpman_bad_url_msg": "The URL must start with http:// or https://",
        # --- _McpJsonImportDialog ---
        "dlg_mcpjson_title": "Add MCP server from JSON",
        "dlg_mcpjson_header": "📋 Add MCP server from JSON",
        "dlg_mcpjson_desc": 'Paste the MCP server configuration JSON (e.g. from the documentation). Format: <code>{"type":"stdio","command":"npx","args":[...],"env":{...}}</code>',
        "dlg_mcpjson_name_placeholder": "e.g. my-server",
        "dlg_mcpjson_name_label": "Name:",
        "dlg_mcpjson_scope_label": "Scope:",
        "dlg_mcpjson_ok_add": "✅ Add",
        "dlg_mcpjson_give_server_name": "Enter a server name.",
        "dlg_mcpjson_no_json_title": "No JSON",
        "dlg_mcpjson_paste_json": "Paste the server configuration JSON.",
        "dlg_mcpjson_bad_json_title": "Bad JSON",
        "dlg_mcpjson_bad_json_msg": "Invalid JSON: {error}",
        # --- UpdateAvailableDialog ---
        "dlg_update_title": "Update available",
        "dlg_update_new_version": "New version available: {version}",
        "dlg_update_current_version": "You have version {version} installed.",
        "dlg_update_mandatory": "⚠️ This is a required update.",
        "dlg_update_release_notes": "Release notes…",
        "dlg_update_later": "Later",
        "dlg_update_download_install": "Download and install",
        "dlg_update_downloading": "Downloading…",
        "dlg_update_downloading_progress": "Downloading… {done:.1f}/{total:.1f} MB",
        "dlg_update_downloading_simple": "Downloading… {done:.1f} MB",
        "dlg_update_installing": "Downloaded. Installing the new version…",
        "dlg_update_downloaded_opening": "Downloaded and verified. Opening the installer…",
        "dlg_update_relaunch_status": "Done. Launching the new version…",
        "dlg_update_ready_title": "Update ready",
        "dlg_update_ready_msg": "The new version will be installed and the app will restart in a moment.",
        "dlg_update_downloaded_title": "Update downloaded",
        "dlg_update_installer_opened_msg": "The installer has been opened. Finish the installation and start the app again.",
        "dlg_update_error_title": "Update error",
        # --- "New version" indicator in the status bar ---
        "update_indicator_text": "⬆ New version",
        "update_indicator_tooltip": "A new version is available. Click to download and install.",
        # --- RAM usage indicator in the status bar ---
        "ram_indicator_loading": "RAM — measuring…",
        "ram_indicator_swap_none": "none",
        "ram_indicator_tooltip": (
            "Computer memory (RAM)\n"
            "App (incl. Claude Code): {prog}\n"
            "System: {used} / {total} ({pct}%)\n"
            "Swap file: {swap}\n\n"
            "Color warns about freezes as memory fills up:\n"
            "green → yellow → orange → red."
        ),
        # --- ClaudeSetupDialog ---
        "dlg_setup_title": "Finish setup — Claude Code is required",
        "dlg_setup_header": "One more step — install Claude Code",
        "dlg_setup_intro": "This program is a \"remote control\" for the <b>Claude Code</b> tool — that's what talks to you and writes code. It isn't on this computer yet, which is why the terminal won't work. Installation is free and takes a few minutes. Just follow these three steps:",
        "dlg_setup_step1_title": "Step 1 — install Node.js (a free helper program)",
        "dlg_setup_step1_label": "Click the button below, download the <b>LTS</b> version (the green button) and install it like any program (Next → Next → Finish).",
        "dlg_setup_step1_warn": "⚠️ In the Node.js installer <b>do NOT check</b> the \"Tools for Native Modules\" option. If a black window with scary-looking errors appears anyway — just close it, it's harmless (Node.js is already installed).",
        "dlg_setup_node_btn": "🌐 Open nodejs.org",
        "dlg_setup_step2_title": "Step 2 — install Claude Code",
        "dlg_setup_step2_label": "After installing Node.js <b>restart this program</b>, paste the command below into the terminal (the black box in the window) and press Enter. The message \"added … packages\" means success.",
        "dlg_setup_copy": "⧉ Copy",
        "dlg_setup_copied": "✓ Copied",
        "dlg_setup_step3_title": "Step 3 — run and sign in",
        "dlg_setup_step3_label": "Type <b>claude</b> in the terminal and press Enter. On first launch Claude Code will ask you to sign in — if the browser does not open by itself, press the <b>c</b> key (it copies the link), paste it into a browser and finish signing in. <b>Do not retype the link by hand</b> — it is very long.",
        "dlg_setup_full_guide": "📖 Full guide (step by step)",
        "dlg_setup_check_again": "🔄 Check again",
        "dlg_setup_found_title": "Claude Code found",
        "dlg_setup_found_msg": "Claude Code is installed. 🎉\n\nYou can now run an agent (tab → Run) or type \"claude\" in the terminal.",
        "dlg_setup_not_found_title": "Claude Code not visible yet",
        "dlg_setup_not_found_msg": "I haven't found Claude Code on the system yet.\n\nMake sure Step 1 (Node.js) and Step 2 (the npm command) were completed, and if you just installed Node.js — restart this program and try again.",
        "dlg_setup_check_title": "Program setup — what's still left",
        "dlg_setup_check_intro": "I've checked what's already done. Complete the items marked <b>❗</b> — for each one I've written what to do, step by step.",
        "dlg_setup_ready": "✅ done",
        "dlg_setup_missing": "❗ to do",
        "dlg_setup_item_claude": "Claude Code — installed",
        "dlg_setup_item_login": "Claude Code — signed in",
        "dlg_setup_item_dictation": "Voice dictation — Groq key",
        "dlg_setup_dictation_intro": "Dictation (speaking instead of typing) is optional — the program works without it. To enable it, get a <b>free</b> Groq key and paste it in Settings. The page below shows it step by step.",
        "dlg_setup_groq_btn": "🔑 How to get a free Groq key",
        "dlg_setup_settings_btn": "⚙️ Open Settings (paste the key)",
        "dlg_setup_dictation_dismiss": "Don't remind me about dictation",
        "dlg_setup_all_ready": "✅ All set — you're ready to go.",
        # --- Broken Claude Code install (placeholder left by a failed npm run) ---
        "status_claude_broken": "Claude Code is installed but broken — see the repair instructions window",
        "dlg_setup_broken_chip": "BROKEN",
        "dlg_setup_broken_title": "Claude Code is installed but broken",
        "dlg_setup_broken_intro": "Claude Code is on this computer, but it <b>cannot be started</b> — the installation stopped halfway. This is a fault of the npm installer, <b>not</b> of this program.",
        "dlg_setup_broken_why": "The npm package does not contain the finished program — it downloads it in a separate step after installation. On your computer that step did not run, so only a placeholder file was left behind.",
        "dlg_setup_broken_why_windows": "Windows tries to run that placeholder file and then shows the „unsupported 16-bit application” message.",
        "dlg_setup_broken_path": "Broken file: {path}",
        "dlg_setup_broken_steps_title": "Repair — one time, about 5 minutes:",
        "dlg_setup_broken_step1": "1. Close this program.",
        "dlg_setup_broken_step2": "2. Open PowerShell (Start → type <b>powershell</b> → Enter) and type in both commands below, one after another, confirming each with Enter.",
        "dlg_setup_broken_step2_unix": "2. Open Terminal and type in both commands below, one after another, confirming each with Enter.",
        "dlg_setup_broken_step3": "3. Close PowerShell, open a new one and check with <b>claude --version</b> — it should print a version number, with no „16-bit application” dialog.",
        "dlg_setup_broken_step3_unix": "3. Close Terminal, open a new one and check with <b>claude --version</b> — it should print a version number.",
        "dlg_setup_broken_step4": "4. Start this program and go to Settings → Claude Code command → type just the word <b>claude</b>.",
        "dlg_setup_broken_after": "The second command installs Claude Code straight from Anthropic, bypassing npm — npm is what failed, so repeating the npm installation usually does not help.",
        "dlg_setup_broken_msg": "Claude Code is installed but broken — the npm installation did not finish.\n\nFollow the repair steps in the setup window, then click „Check again”.",
        # --- i18n round 2: main_window dialogs ---
        "dlg_cannot_close_title": "Cannot close",
        "dlg_must_keep_one_tab": "At least one tab must remain.",
        "dlg_new_tab_tooltip": "New tab",
        "dlg_agent_waiting_tooltip": "Agent is waiting for a reply",
        "dlg_agent_saved_msg": "Agent \"{name}\" has been saved.\nThe tab will appear after restarting the app, or use 'Manage agents'.",
        "dlg_many_agents_title": "Many active agents",
        "dlg_many_agents_msg": "You already have {active} active agents, and your computer ({total} GB RAM) can safely handle about {recommended}. Each agent runs a separate Claude process using 3–5 GB of memory.\n\nLaunching another may slow down or freeze your computer.\n\nAre you sure you want to run this agent?",
        "dlg_many_agents_msg_noram": "You already have {active} active agents. Each one runs a separate Claude process using 3–5 GB of RAM.\n\nLaunching another may slow down or freeze your computer.\n\nAre you sure you want to run this agent?",
        "status_agents_saved": "Agent changes saved.",
        "dlg_quick_add_title": "Add quick action",
        "dlg_quick_label_placeholder": "e.g. Check errors",
        "dlg_quick_command_placeholder": "e.g. Check the code for errors and fix them",
        "dlg_quick_action_name_label": "Action name:",
        "dlg_quick_command_label": "Command:",
        "dlg_quick_no_name_msg": "Enter an action name.",
        "dlg_quick_no_command_title": "No command",
        "dlg_quick_no_command_msg": "Enter a command.",
        "dlg_new_session_title": "New session",
        "dlg_new_session_msg": "Are you sure you want to start a new session?",
        "dlg_about_title": "About {name}",
        "dlg_about_body": "<h2>{name}</h2><p>Version {version}</p><p>Voice assistant for Claude Code.</p><p>© 2024 Fulfillment Polska</p>",
        "dlg_trial_start_title": "Start trial",
        "dlg_trial_start_prompt": "Enter your email address to start a 30-day trial:",
        "dlg_trial_active_title": "Trial activated",
        "dlg_trial_active_msg": "Your 30-day trial has been activated!\nEmail: {email}",
        "dlg_trial_activate_failed": "Failed to activate the trial.",
        "dlg_license_expired_title": "License expired",
        "dlg_license_expired_msg": "Your license or trial period has expired.\nWould you like to buy a license?",
        "dlg_groq_required_title": "Dictation requires a Groq key",
        "dlg_groq_required_msg": "To enable voice dictation, add a free Groq API key — it is used for speech recognition (converting voice to text).\n\nNote: reading aloud works without a key. Groq is needed ONLY for dictation.\n\nYou can get a free key in a minute at:\nhttps://console.groq.com/keys\n(sign in, click 'Create API Key', copy the 'gsk_...' key).\n\nWould you like to add a key now?",
        "dlg_media_all_supported": "All supported",
        "dlg_media_images": "Images",
        "dlg_media_documents": "Documents",
        "dlg_media_data": "Data",
        "dlg_media_archives": "Archives",
        "dlg_media_all_files": "All files",
        "dlg_media_add_title": "Add media",
        "dlg_groq_key_title": "AI Manager key (dictation)",
        "dlg_groq_key_prompt": "A key is needed for dictation (converting speech to text).\nReading aloud works without a key.\n\nDictation now goes through the AI Manager gateway. How to get the key:\n1. Open the AI Manager panel.\n2. Open the 'Voice Assistant' application.\n3. Copy its key (starts with 'aim-...') - NOTE: it is shown only ONCE!\n4. Paste it in the field below and click OK.\n\nCurrent key: {key}",
        "dlg_key_none": "none",
        "dlg_groq_key_saved": "The dictation key has been saved.",
        "stt_err_bad_key": "Invalid AI Manager key — enter the 'Voice Assistant' app key in Settings.",
        "stt_err_rate_limit": "Too much dictation at once — please try again in a moment.",
        "stt_err_busy": "The dictation gateway is momentarily busy — please try again shortly.",
        # Dictation — messages that MUST reach the user (2026-08-29).
        "stt_err_network": "Could not send the recording — check your internet. Please say it again.",
        "stt_err_empty": "I did not hear any words — please say it again, a bit longer.",
        "status_stt_busy": "Still processing the previous recording — one moment…",
        "status_stt_unblocked": "Dictation unblocked — go ahead.",
        "dlg_stt_failed_title": "Dictation did not arrive",
        "dlg_stt_failed_msg": ("The recording was not recognised, so nothing was typed into the command field.\n\n"
                               "Reason: {reason}\n\nPlease say it again."),
        "dlg_anthropic_key_title": "Anthropic API key",
        "dlg_anthropic_key_prompt": "Enter your Anthropic (Claude) API key:\n\nCurrent: {key}",
        "dlg_anthropic_key_saved": "The Anthropic API key has been saved.",
        "dlg_claude_cmd_title": "Claude Code command",
        "dlg_claude_cmd_desc": "Enter the command that launches Claude Code in the terminal.\nThis command will be typed automatically when the program starts.",
        "dlg_claude_cmd_command_label": "Command:",
        "dlg_claude_cmd_autorun": "Run automatically when the program starts",
        "dlg_claude_cmd_saved": "The Claude Code command has been saved.\n\nCommand: {command}\nAuto-run: {autorun}",
        "dlg_yes": "Yes",
        "dlg_no": "No",
        "dlg_qa_manage_title": "Manage quick actions",
        "dlg_qa_manage_header": "Manage your quick actions",
        "dlg_qa_col_label": "Label",
        "dlg_qa_col_command": "Command",
        "dlg_qa_up": "▲ Up",
        "dlg_qa_down": "▼ Down",
        "dlg_qa_add_group": "Add new action",
        "dlg_qa_label_label": "Label:",
        "dlg_qa_restore_defaults": "Restore defaults",
        "dlg_qa_select_to_edit": "Select an action to edit.",
        "dlg_qa_edit_title": "Edit action",
        "dlg_qa_select_to_delete": "Select an action to delete.",
        "dlg_qa_confirm_delete_msg": "Are you sure you want to delete the action \"{label}\"?",
        "dlg_qa_no_label_title": "No label",
        "dlg_qa_no_label_msg": "Enter a label for the action.",
        "dlg_qa_no_command_title": "No command",
        "dlg_qa_no_command_msg": "Enter a command for the action.",
        "dlg_qa_restore_confirm_msg": "Are you sure you want to restore the default actions?\nAll your actions will be removed.",
        "dlg_skin_title": "Skin settings - Colors and icons",
        "dlg_skin_header": "Customize the app's colors and icons",
        "dlg_skin_import": "📥 Import skin",
        "dlg_skin_export": "📤 Export skin",
        "dlg_skin_help_btn": "❓ Help - Icons",
        "dlg_skin_group_main": "Main elements",
        "dlg_skin_group_borders": "Borders and effects",
        "dlg_skin_group_text": "Text and buttons",
        "dlg_skin_group_terminal": "Terminal - background and text",
        "dlg_skin_group_icon_colors": "Button icon colors",
        "dlg_skin_group_icons": "Button icons",
        "dlg_skin_reset": "Restore defaults (Ubuntu)",
        "dlg_skin_apply": "Apply",
        "dlg_skin_pick_color": "Pick color: {name}",
        "dlg_skin_icon_normal_tooltip": "Normal icon (click to change)",
        "dlg_skin_icon_active_tooltip": "Active icon (click to change)",
        "dlg_skin_icon_processing_tooltip": "Processing icon (click to change)",
        "dlg_skin_change_icon_title": "Change icon: {name}",
        "dlg_skin_icon_input_label": "Enter an emoji or text for the '{state}' state:\n(e.g. 🎤 or text)",
        "dlg_skin_pick_icon_color_tooltip": "Change icon color",
        "dlg_skin_pick_icon_color_title": "Pick icon color",
        "dlg_skin_help_body": "\n<h2>🎨 How to change button icons</h2>\n\n<h3>📝 Instructions:</h3>\n<ol>\n<li>Click the button with the icon you want to change</li>\n<li>Enter a new emoji or text</li>\n<li>Click OK</li>\n</ol>\n\n<p><b>The \"normal\" icon</b> - shown when the button is inactive<br>\n<b>The \"active\" icon</b> - shown when the button is pressed/active</p>\n\n<h3>⌨️ How to enter an emoji:</h3>\n<ul>\n<li><b>Windows:</b> Press <code>Win + .</code> (dot)</li>\n<li><b>Linux:</b> Press <code>Ctrl + .</code> or <code>Ctrl + Shift + E</code></li>\n<li><b>macOS:</b> Press <code>Ctrl + Cmd + Space</code></li>\n</ul>\n\n<h3>🌐 Icon websites (copy and paste):</h3>\n<ul>\n<li><a href=\"https://emojipedia.org\">emojipedia.org</a> - all emoji</li>\n<li><a href=\"https://getemoji.com\">getemoji.com</a> - emoji to copy</li>\n<li><a href=\"https://symbl.cc/en/\">symbl.cc</a> - Unicode symbols</li>\n<li><a href=\"https://unicode-table.com\">unicode-table.com</a> - Unicode table</li>\n<li><a href=\"https://fontawesome.com/search?o=r&m=free\">fontawesome.com</a> - icons (copy as Unicode)</li>\n</ul>\n\n<h3>💡 Example icons:</h3>\n<table>\n<tr><td><b>Microphone:</b></td><td>🎤 🎙️ 🎚️ 📢 🔴</td></tr>\n<tr><td><b>Speaker:</b></td><td>🔊 🔉 🔈 🔇 📣 🎵</td></tr>\n<tr><td><b>Pause/Play:</b></td><td>⏸️ ▶️ ⏯️ ⏹️ ⏺️</td></tr>\n<tr><td><b>Stop:</b></td><td>⬜ ⏹️ 🛑 ❌ ✖️</td></tr>\n<tr><td><b>Copy:</b></td><td>⧉ 📋 📄 📑 ✂️</td></tr>\n<tr><td><b>Send:</b></td><td>↵ ➡️ 📤 📨 ✈️</td></tr>\n<tr><td><b>Actions:</b></td><td>⚡ ⭐ 💫 🔥 ✨</td></tr>\n</table>\n\n<h3>📁 Import/Export skin:</h3>\n<p>You can save your skin to a <code>.skin.json</code> file and share it with others,\nor load a skin from someone else.</p>\n",
        "dlg_skin_help_title": "Help - Icons and skins",
        "dlg_skin_import_title": "Import skin",
        "dlg_skin_filter": "Skin files (*.skin.json);;All files (*)",
        "dlg_skin_success_title": "Success",
        "dlg_skin_loaded_msg": "Skin loaded from:\n{path}",
        "dlg_skin_load_failed_msg": "Failed to load the skin:\n{error}",
        "dlg_skin_export_title": "Export skin",
        "dlg_skin_default_name": "My skin",
        "dlg_skin_saved_msg": "Skin saved to:\n{path}",
        "dlg_skin_save_failed_msg": "Failed to save the skin:\n{error}",
        "dlg_settings_title": "Settings",
        "dlg_settings_groq_label": "Groq API key:",
        "dlg_license_title": "License",
        "dlg_license_status": "Status: {status}",
        "dlg_license_email": "Email: {email}",
        "dlg_license_trial_days": "Trial days left: {days}",
        "dlg_license_key_label": "Enter license key:",
        "dlg_license_activate": "Activate license",
        "dlg_license_buy": "Buy license",
        "dlg_license_success_title": "Success",
        # skin color names
        "skin_color_main_window_bg": "Main window background",
        "skin_color_menu_bar_bg": "Menu bar background",
        "skin_color_status_bar_bg": "Status bar background",
        "skin_color_bottom_panel_bg": "Button panel background",
        "skin_color_border_color": "Border color",
        "skin_color_hover_color": "Highlight color (hover)",
        "skin_color_splitter_color": "Splitter color",
        "skin_color_text_color": "Interface text color",
        "skin_color_button_bg": "Button background",
        "skin_color_button_hover": "Button on hover",
        "skin_color_input_bg": "Text field background",
        "skin_color_inactive_panel_bg": "Inactive panel",
        "skin_color_terminal_bg": "Terminal background",
        "skin_color_terminal_fg": "Terminal text",
        "skin_color_terminal_color_0": "Black",
        "skin_color_terminal_color_1": "Red",
        "skin_color_terminal_color_2": "Green",
        "skin_color_terminal_color_3": "Yellow",
        "skin_color_terminal_color_4": "Blue",
        "skin_color_terminal_color_5": "Magenta (purple)",
        "skin_color_terminal_color_6": "Cyan (teal)",
        "skin_color_terminal_color_7": "White",
        "skin_color_terminal_color_0_bright": "Bright black (gray)",
        "skin_color_terminal_color_1_bright": "Bright red",
        "skin_color_terminal_color_2_bright": "Bright green",
        "skin_color_terminal_color_3_bright": "Bright yellow",
        "skin_color_terminal_color_4_bright": "Bright blue",
        "skin_color_terminal_color_5_bright": "Bright magenta",
        "skin_color_terminal_color_6_bright": "Bright cyan",
        "skin_color_terminal_color_7_bright": "Bright white",
        "skin_color_icon_dictate_color": "Microphone icon color",
        "skin_color_icon_read_color": "Speaker icon color",
        "skin_color_icon_pause_color": "Pause icon color",
        "skin_color_icon_stop_color": "Stop icon color",
        "skin_color_icon_copy_color": "Copy icon color",
        "skin_color_icon_clear_input_color": "Clear icon color",
        "skin_color_icon_add_media_color": "Add media icon color",
        "skin_color_icon_send_color": "Send icon color",
        "skin_color_icon_quick_actions_color": "Quick actions icon color",
        "skin_color_icon_search_color": "Search icon color",
        # skin icon names
        "skin_icon_dictate": "Microphone (dictation)",
        "skin_icon_read": "Speaker (reading)",
        "skin_icon_pause": "Pause",
        "skin_icon_stop": "Stop",
        "skin_icon_copy": "Copy",
        "skin_icon_clear_input": "Clear field",
        "skin_icon_add_media": "Add media",
        "skin_icon_send": "Send",
        "skin_icon_quick_actions": "Quick actions",
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
    """Ustaw globalny język interfejsu (tylko jeśli mamy dla niego tłumaczenia).

    Zgodność wstecz: zlikwidowany wariant brytyjski (en-GB) mapujemy na
    amerykański (en-US), żeby użytkownik z zapisanym en-GB nie wypadł na język
    domyślny."""
    global _CURRENT_UI_LANGUAGE
    if code == "en-GB":
        code = "en-US"
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

    Reguła (ustalona z użytkownikiem 2026-06-15): DOMYŚLNIE angielski (en-US);
    rozpoznany polski system → pl-PL. (Wariant brytyjski zlikwidowany 2026-06-18 —
    jeden angielski; brytyjskie locale też → en-US.)
    Czyta `locale` oraz zmienne środowiskowe LANG/LC_*.
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
    # Domyślnie ANGIELSKI; tylko rozpoznany polski system → polski.
    if norm.startswith("pl"):
        return "pl-PL"
    return "en-US"


def apply_model_catalog(models: dict) -> None:
    """Nakłada świeżo pobrany katalog na ŻYWE słowniki modeli.

    ⚠️ Mutujemy słowniki W MIEJSCU (`clear`+`update`), a NIE podmieniamy
    przypisania. Inne moduły zrobiły `from config import CLAUDE_MODELS`
    i trzymają REFERENCJĘ do tego obiektu — podmiana nazwy w tym module
    byłaby dla nich niewidoczna i lista w oknie agenta zostałaby stara."""
    try:
        from core.model_catalog import merge_into
    except Exception:
        return
    names, limits = merge_into(CLAUDE_MODELS, CLAUDE_MODEL_CONTEXT_LIMITS, models or {})
    CLAUDE_MODELS.clear()
    CLAUDE_MODELS.update(names)
    CLAUDE_MODELS_SHORT.clear()
    CLAUDE_MODELS_SHORT.update(names)
    CLAUDE_MODEL_CONTEXT_LIMITS.clear()
    CLAUDE_MODEL_CONTEXT_LIMITS.update(limits)
    _rebuild_api_id_map(models or {})


def _model_desc_key(key: str) -> str:
    """'claude-opus-4-8' → 'model_claude_opus_4_8_desc' (klucz tłumaczenia opisu)."""
    safe = key.lower().replace("-", "_").replace(".", "_")
    return f"model_{safe}_desc"


def model_label(key: str) -> str:
    """Pełna etykieta modelu: NAZWA (z katalogu) + OPIS (z tłumaczeń).

    Rozdzielenie jest celowe — nazwa niesie numer wersji i przychodzi z sieci,
    opis jest językowy i siedzi w słowniku. Dzięki temu nowy model nie wymaga
    poprawek w tłumaczeniach. Nieznany klucz (własny model wpisany przez
    użytkownika) → pokazujemy go takim, jaki jest."""
    if key == "default":
        return t("model_default_full")
    name = CLAUDE_MODELS.get(key, key)
    dkey = _model_desc_key(key)
    desc = t(dkey)
    return f"{name} ({desc})" if desc != dkey else name


def model_label_short(key: str) -> str:
    """Krótka etykieta modelu (pasek statusu, panel agentów) — sama nazwa."""
    if key == "default":
        return t("model_default_short")
    return CLAUDE_MODELS_SHORT.get(key, key)


def model_default_prefix() -> str:
    """Prefiks 'Domyślny — ' / 'Default — ' (do skracania etykiety na pasku statusu)."""
    return t("model_default_prefix")


def _pretty_api_id(api_id: str) -> str:
    """'claude-opus-5' → 'Opus 5' — awaryjne ładne nazywanie NIEZNANEGO modelu.

    Używane, gdy identyfikatora z dziennika nie ma w katalogu (nowa rodzina
    wydana po ostatnim odświeżeniu, model spoza listy). Nazwa jest WYPROWADZONA
    z samego identyfikatora — nic nie zgadujemy o modelu, tylko go czytelnie
    zapisujemy. Data wydania na końcu (`-20251001`) idzie precz.
    """
    text = re.sub(r"-\d{8}$", "", (api_id or "").strip())
    if text.startswith("claude-"):
        text = text[len("claude-"):]
    parts = [p for p in text.split("-") if p]
    if not parts:
        return api_id or ""
    family = parts[0][:1].upper() + parts[0][1:]
    numbers = [p for p in parts[1:] if p.isdigit()]
    return f"{family} {'.'.join(numbers)}" if numbers else family


def model_name_for_api_id(api_id: str) -> str:
    """Ludzka nazwa modelu dla identyfikatora z dziennika sesji ('Opus 5').

    Pusty ciąg, gdy nie ma czego tłumaczyć — wołający ma wtedy NIC nie
    twierdzić o modelu (lepiej samo „Domyślny" niż zmyślona nazwa)."""
    raw = (api_id or "").strip()
    if not raw:
        return ""
    key = CLAUDE_MODEL_API_IDS.get(raw)
    if key:
        return CLAUDE_MODELS_SHORT.get(key, key)
    return _pretty_api_id(raw)


def context_limit_for_api_id(api_id: str):
    """Okno kontekstu (w tokenach) dla identyfikatora z dziennika albo None.

    None = nie wiemy (model spoza katalogu) → licznik tokenów zostaje przy
    swojej dotychczasowej wartości zamiast liczyć procent z wymyślonej liczby.
    """
    key = CLAUDE_MODEL_API_IDS.get((api_id or "").strip())
    if not key:
        return None
    return CLAUDE_MODEL_CONTEXT_LIMITS.get(key)


def install_guide_url(name: str) -> str:
    """URL instrukcji „krok po kroku" dla danej strony.

    Instrukcje instalacji 3 systemów są SCALONE w jedną stronę z górnym menu
    (`instrukcja-instalacja.html`) — dla macos/linux/windows zwracamy ją z kotwicą
    systemu (#macos itd.). Pozostałe strony (agenci, dyktowanie) mają własne pliki.
    Gdy interfejs po angielsku → wersja '-en'. Wszystkie leżą na publicznym /cva."""
    suffix = "-en" if current_ui_language().startswith("en") else ""
    if name in ("macos", "linux", "windows"):
        return f"{INSTALL_GUIDE_BASE_URL}instrukcja-instalacja{suffix}.html#{name}"
    return f"{INSTALL_GUIDE_BASE_URL}instrukcja-{name}{suffix}.html"


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
