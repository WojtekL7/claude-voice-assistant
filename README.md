# Claude Voice Assistant

Asystent głosowy dla Claude Code - dyktuj polecenia i słuchaj odpowiedzi.

## Funkcje

- **Dyktowanie głosem** - mów, a Claude Code otrzyma tekst (Groq Whisper)
- **Czytanie odpowiedzi** - słuchaj odpowiedzi Claude Code (edge-tts)
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

# Zainstaluj zależności
pip install -r requirements.txt

# Uruchom aplikację
python src/main.py
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
