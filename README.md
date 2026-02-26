# Claude Voice Assistant

Asystent głosowy dla Claude Code - dyktuj polecenia i słuchaj odpowiedzi.

## Funkcje

- **Prawdziwy terminal** - pełny emulator terminala VT100 (QTermWidget)
- **Dyktowanie głosem** - mów, a polecenia wpisują się w terminalu (Groq Whisper)
- **Czytanie odpowiedzi** - słuchaj odpowiedzi z terminala (edge-tts)
- **Pauza/Wznów** - kontroluj czytanie w dowolnym momencie
- **70+ języków** - wielojęzyczność interfejsu i głosów
- **Szybkie akcje** - dropdown z często używanymi poleceniami
- **Auto-czytanie** - automatyczne czytanie każdej odpowiedzi
- **Licencjonowanie** - 30-dniowy trial, potem płatna subskrypcja

## Wymagania

- Python 3.9+
- Claude Code CLI (`claude` lub `ai`)
- Klucz API Groq (do rozpoznawania mowy)
- Linux (Ubuntu 20.04+)
- **QTermWidget** (dla prawdziwego terminala)

## Instalacja

### Z AppImage (zalecane)

1. Pobierz `Claude_Voice_Assistant-1.0.0-x86_64.AppImage`
2. Nadaj uprawnienia: `chmod +x Claude_Voice_Assistant*.AppImage`
3. Uruchom: `./Claude_Voice_Assistant*.AppImage`

### Ze źródeł

```bash
# Klonuj repozytorium
git clone https://github.com/WojtekL7/claude-voice-assistant.git
cd claude-voice-assistant

# Utwórz środowisko wirtualne
python3 -m venv venv
source venv/bin/activate

# Zainstaluj zależności systemowe (Ubuntu/Debian)
sudo apt-get install -y libqtermwidget5-1-dev qtbase5-dev

# Zainstaluj zależności Python
pip install -r requirements.txt

# Zainstaluj QTermWidget (z dołączonego wheel)
pip install wheels/qtermwidget-1.4.0-cp310-abi3-manylinux_2_17_x86_64.whl

# Uruchom aplikację
python src/main.py
```

### Budowanie QTermWidget ze źródeł (opcjonalne)

Jeśli dołączony wheel nie działa, możesz zbudować QTermWidget samodzielnie:

```bash
# Zainstaluj narzędzia do budowania
pip install sip pyqt-builder

# Sklonuj QTermWidget (wersja 1.4.0 dla Qt5)
git clone https://github.com/lxqt/qtermwidget.git /tmp/qtermwidget
cd /tmp/qtermwidget
git checkout 1.4.0

# Dodaj ścieżkę do nagłówków w pyqt/project.py
# W metodzie apply_user_defaults dodaj:
# self.include_dirs.append('/usr/include/qtermwidget5')

# Zbuduj wheel
cd pyqt
sip-wheel --qmake /usr/bin/qmake

# Zainstaluj
pip install qtermwidget-1.4.0-*.whl
```

## Konfiguracja

### Klucz API Groq

1. Uzyskaj klucz API na https://console.groq.com/
2. W aplikacji: Ustawienia (⚙️) → Wprowadź klucz API

### Alias Claude Code

Domyślnie aplikacja uruchamia polecenie `ai`. Jeśli używasz innego aliasu,
zmień wartość `CLAUDE_COMMAND` w pliku `src/config.py`.

## Budowanie

```bash
cd build/linux
./build.sh
```

Wyniki będą w katalogu `dist/`:
- `claude-voice-assistant` - plik wykonywalny
- `Claude_Voice_Assistant-1.0.0-x86_64.AppImage` - AppImage

## Licencja

Copyright © 2024 Fulfillment Polska. Wszelkie prawa zastrzeżone.

- 30 dni darmowego trial
- Płatna licencja po okresie próbnym
