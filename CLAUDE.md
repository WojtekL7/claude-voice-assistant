# Claude Voice Assistant — instrukcje dla Claude Code

Ten plik jest **automatycznie ładowany** przez Claude Code przy starcie w tym katalogu. Czytaj go **przed jakąkolwiek pracą nad kodem**.

---

## ⚠️ OBOWIĄZKOWA KOLEJNOŚĆ CZYTANIA — przed pierwszą zmianą w kodzie

| Priorytet | Plik | Po co |
|-----------|------|-------|
| 🔴 **1 (MUST READ)** | [`docs/PRD.md`](docs/PRD.md) | **Roadmap komercjalizacji 2026** — wizja, model biznesowy, 5 faz, 31 funkcji, task breakdown. Bez tego nie wiadomo *co* i *po co* robić. |
| 🟠 **2** | [`../CLAUDE-COMMON.md`](../CLAUDE-COMMON.md) | Wspólne zasady pracy: procedura zmian (PODSUMUJ → ZAPYTAJ → CZEKAJ → WYKONAJ → TESTY → COMMIT+PUSH), zakaz quick-fixów, zasada prostego wyjaśnienia |
| 🟠 **3** | [`./CLAUDE-VOICE-ASSISTANT.md`](CLAUDE-VOICE-ASSISTANT.md) | Specyfika projektu: tech stack, struktura katalogów, ścieżki konfiguracji, sygnały PyQt, znane problemy |
| 🟡 **4** | [`../CLAUDE.md`](../CLAUDE.md) | Globalne instrukcje user'a (serwery, hasła, konwencje) |

---

## 🎯 Cel projektu (TL;DR z PRD)

**Claude Voice Assistant** przekształcamy z osobistego narzędzia w **komercyjny produkt freemium (open-core) dla użytkowników Claude Code**.

Pozycjonowanie: *"Claude Code Voice Studio z MCP & Skills — premium GUI dla Claude Code z głosem, multi-agent w zakładkach, ekosystemem MCP i Skills."*

**Aktualna faza:** ⏸️ **Faza 0 (Stabilizacja) — przed startem.** Czeka na zatwierdzenie PRD v2.2 i odpowiedzi na otwarte pytania Q2/Q8/Q9/Q10.

**Najbliższe zadania (T0.1 → T0.13):** patrz [PRD sekcja 10 — Faza 0](docs/PRD.md#-faza-0-stabilizacja-2-tygodnie).

---

## 🧭 Workflow przy nowych zmianach

1. **Sprawdź PRD** — czy zadanie jest w jakiejś fazie? Jakie acceptance criteria?
2. **Zastosuj procedurę z `CLAUDE-COMMON.md`** — nie pomijaj kroków
3. **Aktualizuj PRD changelog** — po każdej zakończonej fazie

---

## 🚀 Uruchomienie aplikacji

```bash
cd /home/hdkrytbhdkf/Projekty/claude-voice-assistant
source venv/bin/activate
python3 src/main.py
```

---

## 📂 Najważniejsze pliki kodu (pełna struktura w sekcji 7.2 PRD)

```
src/
├── main.py                          # Entry point
├── config.py                        # Konfiguracja
├── core/
│   ├── claude_bridge.py             # Wrapper Claude Code CLI
│   ├── tts_engine.py                # TTS (edge-tts)
│   ├── stt_engine.py                # STT (Groq Whisper)
│   ├── text_cleaner.py              # ⚠️ T0.2 audit: czy podpięty do TTS pipeline?
│   ├── license_manager.py           # License (stub - rozbudowa w Fazie 1)
│   ├── mcp_manager.py               # MCP Manager (kluczowy wyróżnik)
│   ├── mcp_templates.py             # 7 szablonów MCP (+ premium w Fazie 1)
│   ├── skills_manager.py            # Skills Manager (kluczowy wyróżnik)
│   ├── agent_mcp_settings.py        # Per-agent MCP gating
│   └── agent_skills_settings.py     # Per-agent Skills gating
└── gui/
    ├── main_window.py (4062 linii)  # Główne okno
    ├── agent_tab.py (763)           # Terminal + input
    ├── dialogs.py (3450)            # Dialogi (4-tab agent config)
    └── mcp_status_widget.py (514)   # Token counter + MCP status
```

---

*Ten plik jest auto-ładowany. Aktualizuj gdy zmienia się główne wskazówki dla Claude. Pełen kontekst zawsze w [`docs/PRD.md`](docs/PRD.md).*
