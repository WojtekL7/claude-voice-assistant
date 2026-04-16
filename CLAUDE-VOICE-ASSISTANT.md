# CLAUDE-VOICE-ASSISTANT - Agent aplikacji desktopowej

**Przed pracą załaduj również:** `CLAUDE-COMMON.md`

---

## Projekt: Claude Voice Assistant

- **Lokalizacja:** `/home/hdkrytbhdkf/Projekty/claude-voice-assistant/`
- **Technologie:** Python 3.12, PyQt5, QTermWidget, edge-tts, Groq Whisper
- **GitHub:** https://github.com/WojtekL7/claude-voice-assistant

---

## FUNKCJE

- Prawdziwy terminal (QTermWidget) zamiast symulacji
- Dyktowanie głosem (STT) → tekst wpisuje się w terminalu
- Czytanie odpowiedzi głosem (TTS)
- Auto-czytanie nowych odpowiedzi
- Wiele agentów w zakładkach
- Pliki pamięci projektu
- Skinowanie (kolory, ikony)

---

## URUCHOMIENIE

```bash
cd /home/hdkrytbhdkf/Projekty/claude-voice-assistant
source venv/bin/activate
python3 src/main.py
```

---

## STRUKTURA PROJEKTU

```
claude-voice-assistant/
├── src/
│   ├── main.py              # Entry point
│   ├── config.py            # Konfiguracja, stałe
│   └── gui/
│       ├── main_window.py   # Główne okno aplikacji
│       ├── agent_tab.py     # Zakładka agenta z terminalem
│       └── dialogs/         # Dialogi (ustawienia, agenty)
├── wheels/
│   └── qtermwidget-*.whl    # QTermWidget wheel
└── venv/                    # Środowisko wirtualne
```

---

## KLUCZOWE PLIKI

| Plik | Opis |
|------|------|
| `src/config.py` | Konfiguracja: języki, głosy TTS, domyślni agenci, ścieżki |
| `src/gui/main_window.py` | Główne okno, menu, obsługa TTS/STT, skinowanie |
| `src/gui/agent_tab.py` | Zakładka agenta: terminal, splitter, input, przyciski |

---

## KONFIGURACJA UŻYTKOWNIKA

Pliki konfiguracyjne w: `~/.claude-voice-assistant/`

| Plik | Zawartość |
|------|-----------|
| `config.json` | Ogólne ustawienia (język, głos, skin) |
| `agents.json` | Lista agentów z konfiguracją |
| `memory_projects.json` | Projekty pamięci z plikami |
| `quick_actions.json` | Szybkie akcje użytkownika |

---

## QTERMWIDGET

Wheel: `wheels/qtermwidget-1.4.0-cp310-abi3-manylinux_2_17_x86_64.whl`

Instalacja (jeśli potrzebna):
```bash
pip install wheels/qtermwidget-1.4.0-cp310-abi3-manylinux_2_17_x86_64.whl
```

---

## ZALEŻNOŚCI

```
PyQt5
edge-tts          # Text-to-Speech (Microsoft voices)
sounddevice       # Nagrywanie audio
numpy
httpx             # HTTP client dla Groq API
```

**Groq API** (Speech-to-Text):
- URL: `https://api.groq.com/openai/v1/audio/transcriptions`
- Wymaga: `GROQ_API_KEY` w zmiennych środowiskowych

---

## WORKFLOW WDRAŻANIA

Aplikacja lokalna - nie wymaga deploy na serwer:

```bash
# 1. Git
cd /home/hdkrytbhdkf/Projekty/claude-voice-assistant
git add . && git commit -m "opis" && git push

# 2. Test
source venv/bin/activate
python3 src/main.py
```

---

## SYGNAŁY PyQt (ważne przy modyfikacjach)

**AgentTab:**
- `message_sent(str)` - wysłano wiadomość
- `terminal_output(object)` - dane z terminala
- `status_changed(str)` - zmiana statusu
- `request_tts(str)` - żądanie TTS
- `request_dictation(bool)` - start/stop dyktowania
- `splitter_changed(list)` - zmiana pozycji rozdzielacza

---

## CZĘSTE PROBLEMY

| Problem | Rozwiązanie |
|---------|-------------|
| QTermWidget not found | `pip install wheels/qtermwidget-*.whl` |
| TTS nie działa | Sprawdź połączenie internetowe (edge-tts) |
| STT nie nagrywa | Sprawdź GROQ_API_KEY, mikrofon |
| Aplikacja się nie uruchamia | `python3 -m py_compile src/main.py` |

---

*Ostatnia aktualizacja: 2026-04-16*
