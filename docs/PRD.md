# PRD: Claude Voice Assistant — Roadmap komercjalizacji 2026

| Pole | Wartość |
|------|---------|
| **Wersja dokumentu** | 2.2 (DRAFT) — wstępna walidacja nazw (CVA/VibeCode/VoiceForge OUT, top 3 do walidacji w Fazie 0) |
| **Data utworzenia** | 2026-05-09 |
| **Data aktualizacji** | 2026-05-09 (v2.2) |
| **Autor** | Wojciech Lipiec (kontakt@fulfillment-polska.pl) |
| **Status** | Do zatwierdzenia |
| **Repozytorium** | https://github.com/WojtekL7/claude-voice-assistant |
| **Lokalizacja kodu** | `/home/hdkrytbhdkf/Projekty/claude-voice-assistant/` |
| **Następna recenzja** | po Fazie 0 (planowana 2026-05-25) |

---

## ⚠️ Ważna notka — co się zmieniło między v1.0 a v2.0

PRD v1.0 (2026-05-09) został napisany na podstawie wysokopoziomowego dokumentu `CLAUDE-VOICE-ASSISTANT.md`, **bez czytania faktycznego kodu**. Audit kodu (też 2026-05-09) wykazał, że aplikacja jest inną architekturą niż założono w v1.0:

- ❌ v1.0 zakładało, że produkt to "Multi-AI hub" z `AIProvider` abstraction. **W kodzie jest tylko Claude Code CLI bridge.**
- ❌ v1.0 nie wspominało o pełnym MCP managerze i Skills managerze, **a one są w kodzie i są jednymi z głównych mocnych stron produktu**.
- ❌ v1.0 zakładało implementację 22 funkcji. **Audit wykazał, że ~9% jest zrobione, reszta to prawdziwe zadania.**

PRD v2.0 jest **realignmentem PRD do faktycznej architektury kodu**, z **Claude Code + MCP + Skills jako rdzeniem**, a nie multi-AI providers.

---

## Spis treści

1. [Executive Summary](#1-executive-summary-tldr)
2. [Wizja produktu](#2-wizja-produktu)
3. [Problem Statement](#3-problem-statement)
4. [Persony użytkowników](#4-persony-użytkowników)
5. [Cele biznesowe i metryki sukcesu](#5-cele-biznesowe-i-metryki-sukcesu)
6. [Model biznesowy (Freemium Open Core)](#6-model-biznesowy-freemium-open-core)
7. [Obecny stan aplikacji (audit)](#7-obecny-stan-aplikacji-audit)
8. [Pełen scope funkcji](#8-pełen-scope-funkcji-27-pozycji)
9. [Architektura techniczna](#9-architektura-techniczna)
10. [Plan faz z task breakdown](#10-plan-faz-z-task-breakdown)
11. [Ryzyka i mitygacja](#11-ryzyka-i-mitygacja)
12. [Zależności i założenia](#12-zależności-i-założenia)
13. [Otwarte pytania](#13-otwarte-pytania-do-uzgodnienia)
14. [Future scope (poza PRD)](#14-future-scope-poza-tym-prd)
15. [Changelog dokumentu](#15-changelog-dokumentu)
16. [Brand naming — 10 propozycji do walidacji w Fazie 0](#16-brand-naming--10-propozycji-do-walidacji-w-fazie-0)

---

## 1. Executive Summary (TL;DR)

Claude Voice Assistant przekształcamy z **osobistego narzędzia developerskiego** w **komercyjny produkt freemium (open-core) dla użytkowników Claude Code** dostępny na Linux (faza 0-1), Windows + macOS (faza 2), a docelowo także na mobile (faza 4).

**Wizja:** *"Claude Code Voice Studio z MCP & Skills — premium GUI dla Claude Code z głosem, MCP serverami i ekosystemem Skills."*

**Plan: 5 faz w okresie 6-9 miesięcy:**

| Faza | Czas | Kluczowy rezultat |
|------|------|-------------------|
| **0: Stabilizacja** | 2 tyg | Aplikacja gotowa do testów u zaufanych klientów (security + reliability) |
| **1: Komercjalizacja Linux** | 3-4 tyg | Pierwsze 5 płatnych klientów (€45 MRR) |
| **2: Cross-platform desktop** | 6-8 tyg | Aplikacja na Linux + Windows + macOS, 30+ klientów |
| **3: Power features + MCP/Skills marketplace** | 4-6 tyg | Pełen produkt Pro, 60+ klientów |
| **4: Mobile (PWA → native) + Multi-AI proxy** | 8-12 tyg | Obecność mobile, opcjonalnie multi-AI przez MCP gateway |

**Każda faza ma decyzję go/no-go** — nie idziemy dalej, jeśli kryteria poprzedniej fazy nie są spełnione.

**North Star Metric:** **MRR (Monthly Recurring Revenue)**.

**Główny wyróżnik produktu:** *"Jesteś już użytkownikiem Claude Code? Daj sobie GUI z głosem, multi-agent w zakładkach, MCP managerem i Skills marketplace."*

---

## 2. Wizja produktu

### Wizja w 1 zdaniu
> *"Claude Code Voice Studio — premium GUI dla Claude Code, z dyktowaniem głosem, multi-agent w zakładkach, ekosystemem MCP i Skills."*

### Hasło marketingowe
> *"Claude Code mówi i słucha. Dla developerów którzy nie chcą wracać do CLI."*

### Pozycjonowanie konkurencyjne

| Konkurent | Co oferuje | Czego nie ma |
|-----------|------------|--------------|
| **Goły Claude Code CLI** (free) | Pełen Claude Code w terminalu | Brak GUI, brak głosu, brak multi-agent w zakładkach, MCP/Skills wymaga ręcznej konfiguracji |
| Cursor ($20/mc) | AI w edytorze kodu | Brak terminala, brak głosu, tylko 1 model, brak Claude Code |
| Warp ($20/mc) | Terminal z AI | Słabe AI vs Claude Code, brak głosu, tylko macOS/Linux |
| Claude Desktop (free) | Czat z Claude (chat-only) | Brak terminala, brak Claude Code, brak głosu |
| **Claude Voice Assistant** | **Claude Code w GUI + głos + multi-agent + MCP/Skills manager + freemium** | (to nasz wyróżnik) |

### Target market (kolejność priorytetów)
1. **Solo deweloperzy używający Claude Code** (główny target — power users Anthropic, którzy już płacą za Claude Code)
2. **Vibe coders** (hobbyści z Claude Code)
3. **Product managerzy** używający Claude Code do dokumentacji
4. **Polski/europejski rynek** (i18n PL/EN, Polish text encoding fix — accessibility w polskim)

### Czego NIE robimy (anti-vision)
- ❌ **Nie konkurujemy z Cursor o edytor kodu** — Claude Code już ma edycję plików
- ❌ **Nie robimy własnego AI** — używamy Claude Code, który ma Anthropic API
- ❌ **Nie robimy multi-AI w Fazie 1** — to byłby refactor `claude_bridge.py` na `AIProvider` ABC. W zamian: **multi-AI przez MCP gateway proxy w Fazie 4** (otwarte pytanie Q1)
- ❌ **Nie robimy kalendarza i front-end designera** w tym PRD — to scope creep, przesunięte do *Future scope* (sekcja 14)

---

## 3. Problem Statement

### Główny problem

**Claude Code jest świetny, ale CLI-only.** Power users Claude Code mają realne pain points:

1. **Brak GUI** — wszystko w terminalu, bez wizualnego managera projektów
2. **Brak głosu** — pisanie długich promptów na klawiaturze męczy
3. **Multi-agent jest pain** — żonglowanie 5 oknami terminala dla 5 projektów
4. **MCP servers ręczna konfiguracja** — edycja JSON w `~/.claude/settings.json` per server
5. **Skills wymagają git clone i SKILL.md edition** — brak GUI managera
6. **Brak podsumowania kosztów** — ile tokenów spaliłem dziś w Claude Code? Brak licznika

### Dla kogo to jest problem?
- **Solo developerzy** intensywnie używający Claude Code (płacą Anthropic za API tokens)
- **Polski rynek** — Polish text encoding bug w terminalu, brak natywnego polskiego UI
- **Osoby z niepełnosprawnościami** — głos to accessibility, którego Claude Code CLI nie oferuje
- **Product managerzy** — chcą używać AI do dokumentacji bez zostawania devs (potrzebują GUI)

### Dlaczego teraz?
- **Claude Code zyskuje popularność** — Anthropic agresywnie rozwija (Skills, MCP, Agent SDK) → rośnie pool potencjalnych klientów
- **Brak konkurencji** dla "Claude Code GUI z głosem" — first-mover advantage
- **MCP standard** zyskuje adopcję (Microsoft, OpenAI, Atlassian, Figma, Stripe, Notion w 2026 q1) — kto zaoferuje **najlepszy MCP manager**, ten wygrywa devs

---

## 4. Persony użytkowników

### Persona 1: "Power User Claude Code Wojtek" (Free → Pro conversion target)
- **Profil:** Solo dev, Python/JS, 5+ lat doświadczenia, używa Claude Code 3-8h dziennie
- **Codzienne działanie:** Otwiera 3-5 terminali z Claude Code dla różnych projektów, traci kontekst który projekt to który
- **Frustracja:** Brak GUI, brak głosu (długie prompty męczą), brak licznika tokenów, MCP wymaga edycji JSON ręcznie
- **Funkcje krytyczne:** Multi-agent w zakładkach, MCP manager, token counter, skinowanie
- **Wartość Pro:** Multi-agent + premium voices + premium MCP templates >> €9/mc

### Persona 2: "PM z polskim rynku Anna" (Pro tier €9/mc)
- **Profil:** PM w polskiej firmie, używa Claude Code do PRD/raportów (jak ten PRD!)
- **Codzienne działanie:** Pisze dokumentację z AI, dyktuje głosem, odbiera odpowiedzi audio
- **Frustracja:** Polish encoding bugs w terminalu, brak natywnie polskiego UI, brak eksportu do PDF
- **Funkcje krytyczne:** Polish encoding fix, polski UI, premium voices PL, eksport PDF/MD
- **Wartość Pro:** Czas zaoszczędzony przez dyktowanie >> €9/mc

### Persona 3: "Skill Builder Tomek" (Pro tier - high-value user)
- **Profil:** Senior dev, buduje własne Claude Code skills i MCP servers
- **Codzienne działanie:** Testuje nowe skille, debugguje MCP, pisze własne agent workflows
- **Frustracja:** Brak GUI managera Skills (musi git clone + SKILL.md edit), brak Skills marketplace
- **Funkcje krytyczne:** Skills manager (jest!), Skills marketplace browser (Faza 3), Agent templates
- **Wartość Pro:** Premium skills bundle + marketplace integration

### Persona 4: "Mobile User Piotr" (Faza 4 — nowy rynek)
- **Profil:** Knowledge worker mobilny, dużo podróżuje, używa Claude.ai z telefonu
- **Codzienne działanie:** Pyta AI z telefonu, robi notatki głosem
- **Frustracja:** Claude Desktop nie ma mobile, Claude Code nie ma mobile, Claude.ai nie ma głosu
- **Funkcje krytyczne:** Mobile chat z Claude (przez naszą PWA) + dyktowanie + szybki dostęp przez homescreen
- **Wartość:** Mobile-first AI assistant z polskim językiem (PWA wystarczy w MVP)

---

## 5. Cele biznesowe i metryki sukcesu

### Cele biznesowe (12 miesięcy od startu Fazy 0)

| # | Cel | Termin |
|---|-----|--------|
| C1 | Pierwsze przychody (5 płatnych klientów) | Koniec Fazy 1 (~6 tyg) |
| C2 | Cross-platform: aplikacja działa na 3 desktop OS | Koniec Fazy 2 (~14 tyg) |
| C3 | Skala 60+ płatnych klientów (€540 MRR) | Koniec Fazy 3 (~20 tyg) |
| C4 | Obecność mobile (PWA min.) | Koniec Fazy 4 (~32 tyg) |
| C5 | Product/Market Fit signal: NPS > 30 | Koniec Fazy 3 |

### Metryki sukcesu (KPI tracking)

| Metryka | Baseline (dziś) | Cel Faza 1 | Cel Faza 2 | Cel Faza 3 | Cel Faza 4 |
|---------|-----------------|------------|------------|------------|------------|
| Liczba użytkowników (free) | 1 (ja) | 50 | 200 | 500 | 1000 |
| Liczba płatnych | 0 | 5 | 30 | 60 | 100 |
| MRR (€) | 0 | 45 | 270 | 540 | 900 |
| Crash rate | nieznany | <2% | <1% | <0.5% | <0.5% |
| Conversion rate (free→pro) | n/a | n/a | 15% | 12% | 8% |
| Średni czas onboardingu | n/a | <5 min | <5 min | <5 min | <5 min |
| NPS (Net Promoter Score) | n/a | n/a | n/a | >30 | >40 |

### North Star Metric
**MRR (Monthly Recurring Revenue)** — bo mierzy realny komercyjny sukces.

---

## 6. Model biznesowy (Freemium Open Core)

### Free tier
| Pole | Wartość |
|------|---------|
| **Cena** | €0 |
| **Claude Code integration** | ✅ Pełna (wszystko co Claude Code CLI) |
| **Liczba agentów (zakładek)** | **1 agent** (limit) |
| **MCP servers** | **Max 3 globalnie** (limit) |
| **Skills** | **Max 5 globalnie** (limit) |
| **Premium MCP templates** | ❌ Brak (tylko 7 darmowych — Filesystem, GitHub, PG, SQLite, Brave, n8n, Semantic Scholar) |
| **Skills marketplace** | ❌ Brak browsera (manualnie git clone) |
| **Voices TTS** | Tylko edge-tts (Microsoft) |
| **Reklamy** | ✅ Banner 300x100 na dole (rotacja własnych reklam CRM/n8n/AleSprzedawca + AdSense fallback) |
| **Eksport rozmów** | ❌ Brak |
| **Search w historii** | ❌ Brak |
| **Support** | Tylko community (GitHub Issues) |

### Pro tier
| Pole | Wartość |
|------|---------|
| **Cena** | **€9/miesiąc** lub **€79/rok** (-27%) |
| **Liczba agentów** | **Bez limitu** |
| **MCP servers** | **Bez limitu** |
| **Skills** | **Bez limitu** |
| **Premium MCP templates** | ✅ (Stripe, SendGrid, Slack, Twilio, Notion, ClickUp, Linear, Jira, GitHub Enterprise) |
| **Skills marketplace browser** | ✅ Faza 3 |
| **Premium voices TTS** | ✅ ElevenLabs / OpenAI TTS / neural Polish voices |
| **Reklamy** | ❌ Brak |
| **Eksport PDF/Markdown** | ✅ |
| **Search w historii (FTS5)** | ✅ |
| **Szablony promptów + Agent templates** | ✅ |
| **Lokalne TTS/STT (offline mode)** | ✅ |
| **Email support** | ✅ Reply <48h |

### Enterprise tier (poza zakresem PRD — Faza 5+)
- Wycena indywidualna
- Multi-user, SSO, custom MCP, on-premise license server, audit logs

### Lifetime license (do uzgodnienia, otwarte pytanie Q7)
- Hipotetycznie €299 jednorazowo
- Plus: szybki cash, marketing buzz dla early adopters
- Minus: traci compounding MRR, "support forever" obligation

---

## 7. Obecny stan aplikacji (audit)

> *Sekcja na podstawie auditu kodu z 2026-05-09 — fakty, nie domysły.*

### 7.1 Tech stack faktyczny

```
Python 3.12
PyQt5 >=5.15.0 (GUI framework)
QTermWidget 1.4.0 (terminal — Linux only, instalowany z wheel)
edge-tts >=6.1.0 (TTS — Microsoft, wymaga internetu)
pygame >=2.5.0 (audio playback)
sounddevice >=0.4.6, scipy, numpy (nagrywanie + przetwarzanie audio)
requests, aiohttp, asyncio (HTTP)
pyenchant >=3.2.0 (słownik do czyszczenia TTS — Polish)
pyinstaller >=6.0.0 (pakowanie)
```

**BRAK w requirements.txt** (planowane w Fazie 0/1):
- `keyring` (encrypted API keys)
- `pynput` (global hotkey)
- `reportlab` (PDF export)
- `piper-tts` (lokalne TTS)
- `faster-whisper` (lokalne STT)
- `flask` (license server backend)
- `stripe` (payment integration)

### 7.2 Faktyczna struktura kodu (~11 800 linii Python)

```
src/
├── main.py (67 linii)                    # Entry point, Qt init, exception hook
├── config.py (210)                       # Ścieżki, API URLs, agenci, tłumaczenia, modele
├── core/                                 # ⬅ NIE BYŁO W PRD v1.0
│   ├── claude_bridge.py (210)            # Claude Code CLI wrapper (subprocess)
│   ├── tts_engine.py (295)               # TTS z pause/resume (edge-tts)
│   ├── stt_engine.py (296)               # STT przez Groq Whisper API
│   ├── text_cleaner.py (743)             # Czyszczenie tekstu (Polish, ANSI, MD, URL) ⚠️ czy podpięty?
│   ├── license_manager.py (302)          # License (trial 30d, offline cache 7d) — STUB
│   ├── mcp_manager.py (404)              # ⭐ MCP CLI wrapper (list/add/remove/edit)
│   ├── mcp_templates.py (293)            # ⭐ 7 szablonów MCP
│   ├── skills_manager.py (198)           # ⭐ Instalacja skilli z ZIP/folder
│   ├── agent_mcp_settings.py (161)       # Per-agent MCP gating (settings.local.json)
│   └── agent_skills_settings.py (118)    # Per-agent Skills gating
└── gui/
    ├── main_window.py (4062)             # Menu, tabs, terminal, TTS/STT, settings, skin
    ├── agent_tab.py (763)                # Terminal, splitter, input, quick actions, auto-read
    ├── dialogs.py (3450)                 # 4-tab agent config (Basic/Memory/Skills/MCP), MemoryProjects
    └── mcp_status_widget.py (514)        # ⭐ Token counter + MCP status w pasku
```

### 7.3 Co już działa ✅

- **Claude Code CLI bridge** — pełna integracja z `claude --print`
- **Multi-agent w zakładkach** (kod gotowy, ale w Fazie 1 zostanie ograniczony do 1 dla free tier)
- **MCP Manager** — globalne + per-agent włączanie/wyłączanie, 7 szablonów, status widget
- **Skills Manager** — instalacja z ZIP/folder, parser SKILL.md, per-agent gating
- **Token counter** — per-agent + globalny licznik, throttling 5 Hz
- **Multi-language UI** — pl-PL, en-US, en-GB
- **Polish text encoding fix** — `text_cleaner.py:fix_polish_encoding`
- **Memory Projects** z UI dialogiem
- **Quick Actions** — predefiniowane prompts
- **Skinowanie** kolorów
- **STT** przez Groq Whisper API
- **TTS** przez edge-tts (Microsoft)
- **Auto-czytanie odpowiedzi** (z ekstrakcją ostatniej odpowiedzi Claude z terminala)

### 7.4 Co NIE działa lub ma poważne braki ❌

- 🔴 **API keys w plain text** w `~/.claude-voice-assistant/config.json` (`keyring` nie jest używany)
- 🔴 **Brak walidacji API keys** przy starcie (cichy fail jeśli klucz niepoprawny)
- 🔴 **Crash reporter** to tylko basic `sys.excepthook` — nie zapisuje do pliku
- 🔴 **Brak toast notyfikacji** o błędach
- 🔴 **TTS text cleaner** istnieje (`text_cleaner.py` 743 linii!), ALE **nie jest jasne czy faktycznie podpięty do TTS pipeline** — Faza 0 to weryfikuje
- ❌ **License manager** to stub (trial 30d + device_id), brak Stripe integration, brak server-side validation
- ❌ **Brak feature gating** (`@requires_pro` decorator)
- ❌ **Brak banner reklam** w GUI
- ❌ **Brak update mechanizmu**
- ❌ **Brak onboarding wizard**
- ❌ **Cross-platform:** tylko Linux (QTermWidget Linux-only, brak Windows/macOS testów)
- ❌ **Brak globalnej hotkey** dyktowania (wymaga focused window)
- ❌ **Brak premium voices** (tylko edge-tts)
- ❌ **Brak Skills/MCP marketplace browser** (manualna instalacja z ZIP)

### 7.5 Konfiguracja użytkownika (faktyczna)

```
~/.claude-voice-assistant/
├── config.json                 # Język, głos, skin + 🔴 API keys (plain text!)
├── agents.json                 # Lista agentów z konfiguracją
├── memory_projects.json        # Projekty pamięci
├── quick_actions.json          # Quick actions
├── license.json                # Status licencji (z license_manager)
├── device.json                 # Device ID dla license
├── debug.log                   # Debug log z ClaudeBridge
└── (BRAK katalogu crashes/)    # Crash reporter nie istnieje
```

---

## 8. Pełen scope funkcji (27 pozycji)

> *Funkcje przesunięte do "Future scope" (kalendarz, designer, multi-AI providers) są wymienione w sekcji 14, nie tutaj.*

### A. Core / Claude Code Bridge (już zaimplementowane — sekcja 7.3)
*Te funkcje są w kodzie, dokumentujemy je dla pełności PRD.*

| ID | Funkcja | Status | Tier |
|----|---------|--------|------|
| F-CORE-001 | Claude Code CLI bridge (subprocess) | ✅ Gotowe | Free + Pro |
| F-CORE-002 | Terminal (QTermWidget Linux) | ✅ Gotowe | Free + Pro |
| F-CORE-003 | TTS przez edge-tts (Microsoft) | ✅ Gotowe | Free + Pro |
| F-CORE-004 | STT przez Groq Whisper | ✅ Gotowe | Free + Pro |
| F-CORE-005 | Skinowanie kolorów | ✅ Gotowe | Free + Pro |
| F-CORE-006 | Quick actions (predefiniowane prompts) | ✅ Gotowe | Free + Pro |
| F-CORE-007 | Memory Projects z UI | ✅ Gotowe | Free + Pro |
| F-CORE-008 | Token counter per-agent + globalny | ✅ Gotowe | Free + Pro |

### B. MCP / Skills (już częściowo, Pro features dodawane) — wyróżnik produktu

| ID | Funkcja | Status | Faza | Tier |
|----|---------|--------|------|------|
| F-MCP-001 | MCP Manager (list/add/remove/edit, 7 templates) | ✅ Gotowe | — | Free + Pro |
| F-MCP-002 | Per-agent MCP gating | ✅ Gotowe | — | Free + Pro |
| F-MCP-003 | **Premium MCP templates** (Stripe, SendGrid, Slack, Twilio, Notion, etc.) | ❌ | 1 | **Pro** |
| F-MCP-004 | **MCP Marketplace browser** (search + install z official registry) | ❌ | 3 | Free + Pro |
| F-SKL-001 | Skills Manager (install z ZIP, parser SKILL.md) | ✅ Gotowe | — | Free + Pro |
| F-SKL-002 | Per-agent Skills gating | ✅ Gotowe | — | Free + Pro |
| F-SKL-003 | **Premium skills bundles** (PM bundle, DevOps bundle, ML bundle) | ❌ | 1 | **Pro** |
| F-SKL-004 | **Skills marketplace browser** (awesome-claude-skills integration) | ❌ | 3 | Free + Pro |

### C. Agent / Multi-agent (już częściowo, Pro feature)

| ID | Funkcja | Status | Faza | Tier |
|----|---------|--------|------|------|
| F-AGT-001 | Multi-agent w zakładkach | ✅ Gotowe | 1 | **Free=1, Pro=∞** |
| F-AGT-002 | **Agent templates / workflows** (np. "PM agent z PRD skill + GitHub MCP") | ❌ | 3 | **Pro** |

### D. Stabilność (Faza 0)

| ID | Funkcja | Status | Faza | Tier |
|----|---------|--------|------|------|
| F-STA-001 | Crash reporter z lokalnym logiem | ❌ | 0 | Free + Pro |
| F-STA-002 | Walidacja API keys przy starcie | ❌ | 0 | Free + Pro |
| F-STA-003 | Encrypted storage dla API keys (system keyring) | ❌ | 0 | Free + Pro |
| F-STA-004 | Toast notyfikacje błędów w GUI | ❌ | 0 | Free + Pro |

### E. Voice / TTS / STT (Faza 0 + 3)

| ID | Funkcja | Status | Faza | Tier |
|----|---------|--------|------|------|
| F-VOI-001 | Voice Activity Detection (auto-stop dyktowania) | ❌ | 3 | **Pro** |
| F-VOI-002 | Global hotkey dyktowania (Ctrl+Shift+Space) | ❌ | 3 | **Pro** |
| F-VOI-003 | Lokalne TTS (Piper) jako fallback | ❌ | 3 | **Pro** |
| F-VOI-004 | Lokalne STT (Whisper offline) jako fallback | ❌ | 3 | **Pro** |
| F-VOI-005 | Wybór głosu TTS per-agent | ❌ | 3 | **Pro** |
| F-VOI-006 | **Premium voices** (ElevenLabs / OpenAI TTS / neural PL) | ❌ | 1 | **Pro** |
| F-VOI-007 | **Verify text_cleaner.py podpięcie do TTS pipeline** + ev. fix | 🟡 Częściowo | 0 | Free + Pro |

### F. UX / Produktywność (Faza 3)

| ID | Funkcja | Status | Faza | Tier |
|----|---------|--------|------|------|
| F-UX-001 | Eksport rozmowy do PDF/Markdown | ❌ | 3 | **Pro** |
| F-UX-002 | Search w historii rozmów (SQLite + FTS5) | ❌ | 3 | **Pro** |
| F-UX-003 | Szablony promptów (snippets manager) | ❌ | 3 | **Pro** |
| F-UX-004 | Tray icon (background mode + notyfikacje) | ❌ | 3 | Free + Pro |

### G. Komercjalizacja (Faza 1)

| ID | Funkcja | Status | Faza | Tier |
|----|---------|--------|------|------|
| F-COM-001 | License key system (offline + online check) | 🟡 Stub | 1 | (system) |
| F-COM-002 | Feature gating (`@requires_pro` decorator) | ❌ | 1 | (system) |
| F-COM-003 | Update checker (GitHub releases API) | ❌ | 1 | Free + Pro |
| F-COM-004 | Onboarding wizard (5-step) | ❌ | 1 | Free + Pro |
| F-COM-005 | **Reklamy banner** (free tier, CMS na CRM) | ❌ | 1 | Free only |

### H. Lokalizacja (już zaimplementowana — dokumentujemy)

| ID | Funkcja | Status | Faza | Tier |
|----|---------|--------|------|------|
| F-LNG-001 | Multi-language UI (pl-PL, en-US, en-GB) + Polish encoding fix | ✅ Gotowe | — | Free + Pro |

### I. Branding (nowe w v2.1) — blocker dla landing page i komercjalizacji

| ID | Funkcja | Status | Faza | Tier |
|----|---------|--------|------|------|
| F-BRD-001 | **Brand naming** — wybór nazwy bez "Claude" + trademark check | ❌ | 0 | (system) |
| F-BRD-002 | **Logo + ikona aplikacji** — DIY generator AI, wszystkie rozmiary (PNG/ICO/ICNS) | ❌ | 1 | (system) |
| F-BRD-003 | **Domena .app** + DNS Cloudflare + SSL Let's Encrypt | ❌ | 0 | (system) |
| F-BRD-004 | **Brand guidelines** (kolory, typografia, tone of voice) | ❌ | 1 | (system) |

**Razem: 31 funkcji w PRD v2.1** (+ 6 z Future scope = 37 wszystkich rozważanych)

---

## 9. Architektura techniczna

### 9.1 Stack — bez zmian (zachowujemy obecną architekturę)

- **GUI:** PyQt5 (cross-platform, sprawdzone)
- **Terminal:** QTermWidget (Linux) → custom QPlainTextEdit + QProcess (Windows/macOS w Fazie 2)
- **AI engine:** **Claude Code CLI (subprocess)** — *NIE* multi-AI providers
- **TTS:** edge-tts (free) + ElevenLabs/OpenAI TTS (Pro voices, Faza 1)
- **STT:** Groq Whisper API (free + Pro) + lokalny faster-whisper (Pro offline, Faza 3)

### 9.2 Multi-platform strategy

#### Linux (obecnie) ✅
- **Terminal:** QTermWidget 1.4.0 (wheel)
- **Dystrybucja:** PyInstaller → AppImage / .deb / Flatpak (Faza 1)

#### Windows (Faza 2) 🔧
- **Terminal:** Custom `QPlainTextEdit + QProcess + winpty` (zastąpienie QTermWidget)
- **Pakowanie:** PyInstaller + NSIS installer
- **Code signing:** Authenticode (~$200/rok)
- **Auto-update:** Squirrel.Windows

#### macOS (Faza 2) 🔧
- **Terminal:** Custom `QPlainTextEdit + pty.fork()` (Unix pty — reuse z Linux)
- **Pakowanie:** PyInstaller + py2app + .dmg
- **Code signing:** Apple Developer ID ($99/rok) + notarization
- **Auto-update:** Sparkle

#### Mobile (Faza 4) 📱
- **Strategia:** PWA pierwsza → ocena → opcjonalnie native (Flutter)
- **PWA stack:** Vue 3 + Vite + Web Speech API + service worker
- **Backend:** Lekki Flask (reuse z license server) + Anthropic API proxy

### 9.3 License system architecture (Faza 1)

```
┌─────────────────────┐         ┌─────────────────────┐
│  Aplikacja desktop  │  HTTPS  │  License Server     │
│  (klient)           │ ──────► │  (Flask na VPS)     │
│                     │         │                     │
│  Cache: 7 dni       │ ◄────── │  PostgreSQL: keys   │
│  device_id          │         │  Stripe webhook     │
└─────────────────────┘         └─────────────────────┘
```

- **Stub w kodzie:** `core/license_manager.py` (302 linii) — trial 30d, offline cache, device_id
- **Brakuje:** Stripe integration, Flask server, server-side validation endpoint
- **License key format:** UUID v4 hex (32 znaki: `XXXX-XXXX-XXXX-XXXX`)
- **Endpoint:** `POST /api/v1/license/validate { key, device_id }` → `{ tier, expires_at }`
- **Anti-piracy:** device_id (hash MAC + hostname), max 3 urządzenia per klucz

### 9.4 Storage encryption (Faza 0)

- **Lib:** `keyring` (Python, cross-platform)
- **Backendy:** Linux=Secret Service, macOS=Keychain, Windows=Credential Manager
- **Migracja:** Skrypt one-shot przy pierwszym starcie po update — przeniesie API keys z `config.json` → keyring, wyczyści JSON
- **Klucze do migracji:** `groq_api_key`, `anthropic_api_key`, `elevenlabs_api_key` (Faza 1), `openai_tts_api_key` (Faza 1)

### 9.5 Reklamy (Faza 1)

- **Backend:** Endpoint `https://crm.srv1251441.hstgr.cloud/api/ads/banner` (JSON z tablicą reklam, rotacja co 30s)
- **Format banner:** 300x100 (IAB compliant) na dole głównego okna
- **Provider podstawowy:** Własne reklamy (CRM, AleSprzedawca, n8n, Sellmanager) — kontrola 100% + monetyzacja krzyżowa
- **Fallback:** Google AdSense (jeśli własne wypadną z rotacji)
- **Click tracking:** Każdy klik → POST `/api/ads/click { banner_id }` → analityka

### 9.6 Telemetria (Q8 — otwarte pytanie)
- **Opcja A:** Brak telemetrii — szanujemy GDPR by-design
- **Opcja B:** Sentry (open source) — tylko crashe, opt-in w onboardingu
- **Opcja C:** Własna telemetria — eventy do `/api/telemetry`, GDPR-compliant

### 9.7 Multi-AI proxy via MCP gateway (Faza 4 — opcjonalne)

Zamiast refactorować `claude_bridge.py` na `AIProvider` ABC (4-6 tyg pracy + ryzyko regresji), w Fazie 4 możemy dodać **MCP server** który proxy'uje requesty do GPT/Gemini/Ollama:

```
┌──────────────────┐    MCP    ┌─────────────────────┐
│ Claude Code CLI  │ ────────► │  multi-ai-proxy MCP │
└──────────────────┘           │  (nasz MCP server)  │
                                │  ↓                  │
                                │  OpenAI / Gemini    │
                                │  / Ollama / etc.    │
                                └─────────────────────┘
```

**Zaleta:** Brak refactoru, używamy MCP jako abstraction. Działa na każdej wersji Claude Code.
**Wada:** Latency (extra hop), wymaga pisania własnego MCP servera.

---

## 10. Plan faz z task breakdown

### 🔵 FAZA 0: Stabilizacja (2 tygodnie)

**Cel biznesowy:** Aplikacja gotowa do "testowych pierwszych klientów" — bez crashów, bez plain-text API keys, bez znikających błędów.

**Czas:** 14 dni (2026-05-12 → 2026-05-25)

**Zadania (w kolejności wykonania):**

| ID | Zadanie | Czas | Acceptance Criteria |
|----|---------|------|---------------------|
| T0.1 | Setup PRD v2.0 + git tag baseline `v0.9-pre-prd` | 0.5d | Tag istnieje, PRD scommitowany |
| T0.2 | **F-VOI-007:** Audit `text_cleaner.py` — sprawdzić gdzie/czy jest podpięty do TTS pipeline | 0.5d | Raport: Used / Unused / Partially used z file:line |
| T0.3 | **F-VOI-007:** Jeśli unused — podpiąć do TTS pipeline w `tts_engine.py` | 1d | Tekst trafiający do TTS jest przepuszczany przez `text_cleaner` |
| T0.4 | **F-VOI-007:** Test końcowy — markdown, kod, URL, ANSI faktycznie odfiltrowane | 0.5d | TTS nie wymawia "gwiazdka gwiazdka", "https slash slash" itp. |
| T0.5 | **F-STA-002:** Walidacja API key Groq przy starcie (test request) | 0.5d | Bad key → toast "Klucz Groq nieprawidłowy" |
| T0.6 | **F-STA-002:** Walidacja API key Anthropic (przez test `claude --print "hello"`) | 0.5d | Bad key → toast "Claude Code nie skonfigurowany" |
| T0.7 | **F-STA-001:** Crash reporter — `sys.excepthook` + zapis do `~/.claude-voice-assistant/crashes/{timestamp}.log` | 1d | Crash → log z stacktrace zapisany, można wysłać developerowi |
| T0.8 | **F-STA-004:** Toast notification system (PyQt — własny widget overlay 5s) | 1d | Wszystkie błędy pokazują się jako toast zamiast cichego fail |
| T0.9 | **F-STA-003:** Migracja do `keyring` — wrapper module `core/secrets.py` | 1.5d | Klucze API są w system keyring, nie w `config.json` |
| T0.10 | **F-STA-003:** Migration script — przenosi stare JSON keys do keyring (one-shot) | 0.5d | Po update klucze automatycznie przeniesione, JSON wyczyszczony |
| T0.11 | Audit: wszystkie miejsca w kodzie które czytają API keys → użyć `core/secrets.get(...)` | 1d | Brak `config.get('groq_api_key')` w kodzie, tylko `secrets.get(...)` |
| T0.12 | **USER TEST CHECKPOINT:** Manual testing Fazy 0 (Wojtek 2h) | — | Wszystkie funkcje OK, brak regresji |
| T0.13 | Bug fixy + commit + tag `v1.0-phase-0-complete` | 1d | Tag istnieje, regresje naprawione |

**Branding tasks (równolegle, niezależnie od kodu):**

| ID | Zadanie | Czas | Acceptance Criteria |
|----|---------|------|---------------------|
| T0.B.1 | **F-BRD-001:** Brainstorm 10 nazw bez "Claude" — wstępna lista (sekcja 16) | 0.5d | 10 propozycji + uzasadnienie każdej (semantyka, brzmienie) |
| T0.B.2 | **F-BRD-001:** Trademark check — USPTO ([tmsearch.uspto.gov](https://tmsearch.uspto.gov)), EUIPO ([euipo.europa.eu](https://euipo.europa.eu)), WIPO Global Brand DB, Polish UPRP | 0.5d | Każda z 10 nazw oznaczona: czysta / kolizja / wymaga konsultacji prawnej |
| T0.B.3 | **F-BRD-003:** Sprawdzenie dostępności domen .app dla top 5 nazw — Namecheap / GoDaddy WHOIS | 0.5d | Tabela: nazwa → status .app (wolne/zajęte/cena) |
| T0.B.4 | **F-BRD-001 + F-BRD-003:** Decyzja final (nazwa + domena) → zakup .app na Namecheap → DNS Cloudflare → SSL Let's Encrypt | 1d | Domena działa, HTTPS aktywne, ping zwraca 200 |

**Razem (kod + branding):** ~12 dni roboczych + 2 dni buffer = **14 dni**

**Kryterium go/no-go po Fazie 0:**
- ✅ TTS czyta czysty tekst bez śmieci (F-VOI-007 ✓)
- ✅ Klucze API w system keyring, nie w `config.json` (F-STA-003 ✓)
- ✅ Błędy widoczne dla użytkownika jako toast (F-STA-004 ✓)
- ✅ Crash reporter łapie crashe (F-STA-001 ✓)
- ✅ Brak regresji w istniejących funkcjach (MCP, Skills, Token counter, Multi-language)
- ✅ **Nazwa wybrana, trademark clean, domena .app działa z HTTPS** (F-BRD-001, F-BRD-003 ✓)

→ Jeśli wszystkie ✅ → **GO** do Fazy 1.

---

### 🟢 FAZA 1: Komercjalizacja Linux (3-4 tygodnie)

**Cel biznesowy:** **Pierwsze 5 płatnych klientów na Linux (€45 MRR).**

**Czas:** 21-28 dni (2026-05-26 → 2026-06-22)

**Strategia Pro tier (bez multi-AI):**
> *"Free dostaje wszystko podstawowe, Pro dostaje: multi-agent (free=1), unlimited MCP/Skills, premium MCP templates, premium voices."*

**Zadania:**

| ID | Zadanie | Czas | Acceptance Criteria |
|----|---------|------|---------------------|
| T1.1 | **F-COM-002:** Feature gating engine (`@requires_pro` decorator + tier check) | 1d | Funkcje pro mają decorator, free dostaje toast "Upgrade do Pro" |
| T1.2 | **F-AGT-001:** Limit free=1 agent, Pro=∞ — UI pokazuje upgrade prompt przy próbie dodania 2. agenta | 1d | Free user: dodaj agenta → toast "Upgrade do Pro by mieć więcej agentów" |
| T1.3 | **F-AGT-001:** Limit free=3 MCP, Pro=∞ | 0.5d | Free user: 4-ty MCP → toast |
| T1.4 | **F-AGT-001:** Limit free=5 Skills, Pro=∞ | 0.5d | Free user: 6-ty skill → toast |
| T1.5 | **F-COM-001:** License key dialog (Settings → License) + walidacja format UUID | 1d | Settings → License key field, walidacja format |
| T1.6 | **F-COM-001:** License server — Flask app na VPS Hostinger | 2d | Endpoint `/api/v1/license/validate` zwraca tier |
| T1.7 | **F-COM-001:** Klient — sprawdzanie license offline (cache 7d) + online | 1.5d | Tier checked, persisted (encrypted via keyring) |
| T1.8 | **F-COM-001:** Stripe integration — webhook → generowanie kluczy → email | 2d | Po Stripe checkout → automatyczny email z kluczem |
| T1.9 | **F-MCP-003:** Premium MCP templates dataset (10+ szablonów: Stripe, SendGrid, Slack, Twilio, Notion, ClickUp, Linear, Jira, GitHub Enterprise, AWS CLI) | 1.5d | W `mcp_templates.py` 10+ premium templates z `tier: "pro"` |
| T1.10 | **F-MCP-003:** UI — premium templates oznaczone złotą gwiazdką, free user kliknie → upgrade prompt | 1d | Premium templates widoczne, ale wymagają Pro |
| T1.11 | **F-VOI-006:** Premium voices integration — ElevenLabs API (3 polskie, 3 angielskie głosy) | 2d | W settings można wybrać premium voice, działa |
| T1.12 | **F-VOI-006:** OpenAI TTS jako alternatywny premium provider | 1d | Action |
| T1.13 | **F-COM-005:** Banner reklam w GUI (300x100 bottom, refresh 30s) | 1d | Free tier widzi banner, Pro nie |
| T1.14 | **F-COM-005:** Reklamy CMS — endpoint `/api/ads/banner` na CRM, rotacja, click tracking | 1.5d | Banner ładuje reklamy z CRM, klika → tracking |
| T1.15 | **F-COM-004:** Onboarding wizard — 5 kroków (Welcome → API keys → License → Voice test → Done) | 2d | Pierwszy start → wizard prowadzi przez setup |
| T1.16 | **F-COM-003:** Update checker — sprawdza GitHub releases API co 24h | 1d | Toast "v1.1 dostępna, kliknij by pobrać" |
| T1.B.1 | **F-BRD-002:** Brief logo (kolory primary/secondary, koncept: terminal+mikrofon+AI mózg, mood: tech/professional) | 0.5d | Brief 1-page z requirementami |
| T1.B.2 | **F-BRD-002:** Generowanie 3 wersji logo w Looka.com / Brandmark.io / Logo.com | 0.5d | 3 koncepcje SVG/PNG do oceny |
| T1.B.3 | **F-BRD-002:** Wybór + finalizacja logo (SVG + PNG warianty kolorystyczne: na jasnym/ciemnym tle) | 0.5d | Final SVG + 2 PNG warianty (light/dark BG) |
| T1.B.4 | **F-BRD-002:** Ikona aplikacji — wszystkie rozmiary (16, 32, 48, 64, 128, 256, 512, 1024 px) + ICO (Win) + ICNS (Mac) | 1d | Wszystkie pliki w `src/assets/icons/`, gotowe do PyInstaller |
| T1.B.5 | **F-BRD-004:** Brand guidelines (1-page) — kolory hex, typografia (Google Fonts), tone of voice, logo usage rules | 0.5d | `docs/BRAND_GUIDELINES.md` |
| T1.B.6 | **F-BRD-002:** Update aplikacji — nowa ikona w window, splash screen z logo, taskbar/dock icon | 1d | Aplikacja pokazuje nowe logo wszędzie |
| T1.17 | Landing page (Hugo static site na VPS, **na zakupionej domenie .app z T0.B.4**) z logo z T1.B.3 | 2d | `https://<nazwa>.app` działa z brandingiem |
| T1.18 | Strona Stripe checkout + integracja z license server | 1d | Pricing page → checkout → klucz w mailu |
| T1.19 | **USER TEST CHECKPOINT:** Wojtek + 1-2 zaufane osoby (4h) | — | Onboarding, payment, działanie pro flow OK |
| T1.20 | Bug fixy + commit + tag `v1.0-launch` + GitHub release + .deb package | 2d | Tag, GitHub release, .deb |

**Razem:** ~29 dni roboczych + 3 dni buffer = **32 dni** (~4.5 tyg)

**Kryterium go/no-go po Fazie 1:**
- ✅ Feature gating działa (free=1 agent/3 MCP/5 skills, Pro=∞)
- ✅ License system działa end-to-end (płatność Stripe → email z kluczem → aktywacja → tier=Pro)
- ✅ Free tier ma reklamy, Pro nie ma
- ✅ Premium voices działają (ElevenLabs lub OpenAI)
- ✅ Premium MCP templates dostępne dla Pro
- ✅ Onboarding wizard prowadzi przez setup w <5 min
- ✅ **Logo + ikona w aplikacji, brand guidelines udokumentowane** (F-BRD-002, F-BRD-004 ✓)
- ✅ Landing page działa na zakupionej .app z brandingiem
- ✅ **Min. 5 płatnych klientów w 14 dni od launchu**

→ Jeśli min. 5 płatnych klientów → **GO** do Fazy 2.
→ Jeśli mniej → **STOP** — analiza market fit, pivot lub iteracje Fazy 1.

---

### 🟡 FAZA 2: Cross-platform desktop (6-8 tygodni)

**Cel biznesowy:** **Sprzedaż na 3 platformach desktop — 30+ płatnych klientów (€270 MRR).**

**Czas:** 42-56 dni (2026-06-23 → 2026-08-18)

#### Sub-faza 2A: Refactor terminala (2 tygodnie)

| ID | Zadanie | Czas | Acceptance Criteria |
|----|---------|------|---------------------|
| T2.1 | PoC: zastąpienie QTermWidget przez `QPlainTextEdit + QProcess` (Linux baseline) | 3d | PoC działa, można wpisać `ls` i zobaczyć output |
| T2.2 | Warstwa abstrakcji terminala (`TerminalBackend` ABC) — `QTermWidgetBackend`, `CustomBackend` | 1d | Backend pluggable, łatwo dodać Win/Mac |
| T2.3 | LinuxTerminal (pty.fork) — pełna implementacja, regresja vs QTermWidget | 3d | Wszystko co działało w QTermWidget, działa też tu |
| T2.4 | **USER TEST:** Custom terminal vs QTermWidget — Wojtek 2h | — | Brak regresji, można przełączyć |
| T2.5 | Bug fixy + decyzja: idziemy z custom czy zostajemy z QTermWidget na Linux | 2d | Decyzja udokumentowana |

#### Sub-faza 2B: Windows port (3-4 tygodnie)

| ID | Zadanie | Czas | Acceptance Criteria |
|----|---------|------|---------------------|
| T2.6 | WindowsTerminal (winpty wrapper) | 3d | `cmd.exe` / PowerShell uruchamia się w terminalu |
| T2.7 | Test PyQt5 na Windows (różnice w stylach, fontach DPI) | 2d | UI wygląda OK na 100% i 150% DPI |
| T2.8 | Test Claude Code CLI dostępności na Windows + testy bridge'a | 1d | Claude Code działa, bridge OK |
| T2.9 | PyInstaller dla Windows (.exe + zależności) | 2d | Pojedynczy plik .exe + folder z DLL |
| T2.10 | NSIS installer + skrypt instalatora | 2d | Klient klika .exe → wizard → zainstalowane |
| T2.11 | Authenticode signing (kupno cert ~$200) + signing pipeline | 1d | .exe podpisany, brak SmartScreen warning |
| T2.12 | Auto-update via Squirrel.Windows | 2d | Aplikacja sama się aktualizuje |
| T2.13 | **USER TEST:** Instalacja na czystym Win 11 (VM) — 2h | — | Działa od kliknięcia .exe |

#### Sub-faza 2C: macOS port (3-4 tygodnie)

| ID | Zadanie | Czas | Acceptance Criteria |
|----|---------|------|---------------------|
| T2.14 | MacOSTerminal (pty.fork — reuse z Linux) | 1d | Reuse, bo Unix |
| T2.15 | PyInstaller + py2app dla `.app` bundle | 2d | `.app` można uruchomić podwójnym kliknięciem |
| T2.16 | `.dmg` installer | 1d | Klient ściąga .dmg → drag to Applications → działa |
| T2.17 | Apple Developer ID signing ($99/rok) + notarization | 2d | Brak warninga "unidentified developer" |
| T2.18 | Sparkle framework dla auto-update | 2d | Aplikacja sama się aktualizuje |
| T2.19 | **USER TEST:** Instalacja na macOS Sonoma (VM lub fizyczny Mac) — 2h | — | Działa, brak warninga, auto-update OK |

**Razem:** ~50 dni roboczych + 6 dni buffer = **56 dni** (8 tyg)

**Kryterium go/no-go po Fazie 2:**
- ✅ Aplikacja instaluje się i uruchamia na Linux, Windows 11, macOS Sonoma
- ✅ Wszystkie funkcje Faz 0+1 działają na 3 platformach
- ✅ Auto-update działa na każdej platformie
- ✅ Code signing OK (brak warningów na Win/Mac)
- ✅ **Min. 30 płatnych klientów łącznie**

→ Jeśli min. 30 płatnych klientów → **GO** do Fazy 3.

---

### 🟠 FAZA 3: Power features + MCP/Skills marketplace (4-6 tygodni)

**Cel biznesowy:** **Pełnowartościowy produkt Pro — retencja 80% MoM, 60+ klientów (€540 MRR).**

**Czas:** 28-42 dni (2026-08-19 → 2026-09-30)

#### Group A: Voice power (1 tydzień)

| ID | Zadanie | Czas | AC |
|----|---------|------|-----|
| T3.1 | **F-VOI-002:** Global hotkey (`pynput` — cross-platform Ctrl+Shift+Space) | 2d | Hotkey działa nawet bez focusowania okna |
| T3.2 | **F-VOI-001:** VAD — automatyczne stop nagrywania przy ciszy (silero-vad) | 2d | Po 2s ciszy → auto stop nagrywania |
| T3.3 | **F-VOI-005:** Wybór głosu TTS per-agent (rozszerzenie Settings) | 1d | Każdy agent może mieć swój głos |

#### Group B: Lokalne modele (1 tydzień)

| ID | Zadanie | Czas | AC |
|----|---------|------|-----|
| T3.4 | **F-VOI-003:** Piper TTS lokalne (download voices, fallback gdy edge-tts padnie) | 2d | Offline mode działa, brak internetu = Piper |
| T3.5 | **F-VOI-004:** Whisper offline jako fallback STT (faster-whisper) | 3d | Offline mode działa, brak internetu = Whisper local |

#### Group C: Productivity (1 tydzień)

| ID | Zadanie | Czas | AC |
|----|---------|------|-----|
| T3.6 | **F-UX-001:** Eksport rozmowy do PDF (ReportLab) i Markdown | 2d | Menu File → Export → wybór formatu → plik |
| T3.7 | **F-UX-002:** Search w historii rozmów (SQLite + FTS5 full-text) | 2d | Ctrl+F otwiera search, podświetla wyniki |
| T3.8 | **F-UX-003:** Szablony promptów (snippets manager + UI w Settings) | 1d | Można dodać template, użyć przez `/template-name` |
| T3.9 | **F-UX-004:** Tray icon (background mode + notyfikacje) | 1d | Ikona w tray, click → otwiera, notyfikacja od AI |

#### Group D: MCP / Skills marketplace (1.5 tygodnia)

| ID | Zadanie | Czas | AC |
|----|---------|------|-----|
| T3.10 | **F-MCP-004:** MCP Marketplace browser — UI z listą oficjalnych MCP servers | 2d | Tab "MCP Marketplace" z listą i filtrowaniem |
| T3.11 | **F-MCP-004:** Install z marketplace przez 1-click | 2d | Klik "Install" → MCP zainstalowany i aktywny |
| T3.12 | **F-SKL-004:** Skills marketplace browser (integration z `awesome-claude-skills`) | 2d | Tab "Skills Marketplace" z listą skilli |
| T3.13 | **F-SKL-004:** Install skill z marketplace (git clone w tle) | 1.5d | Klik "Install" → skill zainstalowany i aktywny |

#### Group E: Agent templates (0.5 tygodnia)

| ID | Zadanie | Czas | AC |
|----|---------|------|-----|
| T3.14 | **F-AGT-002:** Agent templates / workflows — preset dialogs ("PM agent", "DevOps agent", "ML agent") | 2d | Wybór templatki = automatyczna konfiguracja agenta z odpowiednimi MCP/Skills |

**Razem:** ~28 dni roboczych + 6 dni buffer = **34 dni** (~5 tyg)

**Kryterium go/no-go po Fazie 3:**
- ✅ Wszystkie funkcje Pro tier dostępne i działają
- ✅ Retencja Pro 80% MoM (rozliczane z license server stats)
- ✅ Min. 60 płatnych klientów łącznie
- ✅ NPS > 30 (badanie users — survey w aplikacji)
- ✅ Marketplace MCP i Skills działają (1-click install)

→ Jeśli wszystkie ✅ → **GO** do Fazy 4.

---

### 🟣 FAZA 4: Mobile (PWA → native) + Multi-AI proxy (8-12 tygodni)

**Cel biznesowy:** **Obecność na mobile + opcjonalnie multi-AI przez MCP gateway proxy.**

**Czas:** 56-84 dni (2026-10-01 → 2026-12-22)

#### Sub-faza 4A: PWA (Progressive Web App) — 6 tygodni

| ID | Zadanie | Czas | AC |
|----|---------|------|-----|
| T4.1 | Architektura: Vue 3 + Vite + PWA plugins + TailwindCSS | 2d | Setup boilerplate, deploy hello-world |
| T4.2 | Backend API endpoint `/api/chat` (Flask, reuse z license server) — proxy do Anthropic API | 3d | POST `/api/chat` → odpowiedź Claude |
| T4.3 | UI mobilne (touch-friendly, responsive, 360-768px) | 5d | Wygląda dobrze na iPhone i Android |
| T4.4 | Web Speech API — dyktowanie w przeglądarce | 2d | Tap mikrofon → dyktowanie → tekst |
| T4.5 | AI chat — przez `/api/chat` proxy | 3d | Wybór modelu Claude, chat działa |
| T4.6 | Service Worker — offline mode (cache last 50 conversations) | 2d | Offline → można czytać historię |
| T4.7 | Add to Home Screen prompt | 1d | Pierwsza wizyta → "Dodaj do ekranu" |
| T4.8 | License integration — login do PWA = wpisanie license key | 1d | Pro user na PWA bez reklam |
| T4.9 | Beta testing — 10 użytkowników mobile | 3d | Feedback collected |
| T4.10 | **USER TEST CHECKPOINT** + bugfixes | 5d | Wszystko działa na 5+ urządzeniach |

#### Sub-faza 4B: Multi-AI proxy via MCP gateway (2 tygodnie)

| ID | Zadanie | Czas | AC |
|----|---------|------|-----|
| T4.11 | Decyzja Q1: czy implementujemy multi-AI? Jeśli TAK → idziemy dalej | — | Decyzja udokumentowana |
| T4.12 | Własny MCP server `multi-ai-proxy` (Python) | 3d | MCP server odbiera requesty, routing do GPT/Gemini/Ollama |
| T4.13 | OpenAI provider w MCP proxy (GPT-4o, GPT-4o-mini, o1) | 2d | GPT działa przez MCP |
| T4.14 | Gemini provider w MCP proxy (1.5 Pro, Flash) | 2d | Gemini działa przez MCP |
| T4.15 | Ollama provider w MCP proxy (lokalne LLM) | 2d | Ollama działa przez MCP |
| T4.16 | Dodanie `multi-ai-proxy` do premium MCP templates | 1d | Pro user widzi templatkę w MCP Manager |

#### Sub-faza 4C (opcjonalna): Native Android+iOS — 12 tygodni

| ID | Zadanie | Czas | AC |
|----|---------|------|-----|
| T4.17 | Stack decision: Flutter vs React Native (PoC obu, 1 tydz) | 5d | Decyzja udokumentowana |
| T4.18 | Reuse PWA UI / przepisać natywnie | 15d | UI w wybranym frameworku |
| T4.19 | Android: build, Google Play store ($25 jednorazowo) | 5d | App w sklepie, install OK |
| T4.20 | iOS: build, Apple App Store ($99/rok) | 7d | App w sklepie, install OK |
| T4.21 | In-app purchases (StoreKit dla iOS, Google Play Billing dla Android) | 10d | Można kupić Pro w aplikacji |
| T4.22 | **USER TEST CHECKPOINT** + release | 8d | Apps live, rating >4.0 z 10+ recenzji |

**Decyzja po Faza 4A+B:** Czy iść na native?
- **TAK** jeśli: >100 użytkowników PWA, request o "natywną" w 30%+ opiniach
- **NIE** jeśli: <50 użytkowników, PWA pokrywa use case, focus na desktop ROI lepszy

**Kryterium go/no-go po Fazie 4:**
- ✅ PWA działa offline + chat + dyktowanie
- ✅ Multi-AI proxy MCP działa (jeśli zdecydowano TAK w T4.11)
- ✅ Min. 100 użytkowników PWA
- ✅ Decyzja: native? lub stop na PWA?

---

## 11. Ryzyka i mitygacja

| # | Ryzyko | Prawdopodobieństwo | Wpływ | Mitygacja |
|---|--------|---------------------|-------|-----------|
| R1 | QTermWidget alternatywa nie sprawdzi się na Win/Mac | Średnie | Krytyczne | PoC w T2.1 przed scope completion; fallback: zostaje QTermWidget na Linux + osobne backendy Win/Mac |
| R2 | **Anthropic zmieni Claude Code CLI** (breaking changes w `claude --print` API) | Średnie | **Krytyczne** | Cały produkt opiera się na Claude Code CLI. Mitygacja: integration tests przy każdym update Claude Code, kontakt z Anthropic team, alternative bridge przez Anthropic SDK direct |
| R3 | Apple App Store odrzuci aplikację | Średnie | Wysokie | Faza 4A (PWA) jako fallback; review guidelines compliance check przed submit |
| R4 | Brak płatnych klientów po Fazie 1 | Średnie | Krytyczne | Wczesne user testing; marketing wave przed launch (Reddit r/ClaudeAI, Twitter, GitHub trending); freemium z reklamami obniża barrier of entry |
| R5 | Konkurencja (Anthropic wyda własne GUI dla Claude Code) | Wysokie | Krytyczne | Wyróżnik = głos + multi-agent + MCP/Skills marketplace + reklamy w free tier (nikt z Anthropic tego nie zrobi); szybkość wdrożenia (first-mover) |
| R6 | Koszty API ElevenLabs / OpenAI TTS za wysokie dla Pro tier | Niskie | Średnie | Free voices (edge-tts) jako fallback; rate limit per user; własny model TTS w przyszłości |
| R7 | Stripe nie działa w niektórych krajach | Niskie | Niskie | PayPal jako alternatywa; manual invoice dla wyjątków |
| R8 | Bug w license check blokuje Pro klientów | Niskie | Krytyczne | Offline cache 7 dni + manual override key (master); rollback pipeline |
| R9 | Reklamy psują UX w free tier — konwersja na Pro za niska | Średnie | Średnie | A/B testing pozycji banner; opt-out za €1/mc (mini-paid bez full pro) |
| R10 | **Wojtek nie da rady solo** — inne projekty (CRM, AleSprzedawca, Sellmanager) konkurują o czas | **Wysokie** | **Krytyczne** | Realistyczne fazowanie (6-9 mc), gates per faza, możliwość pause między fazami |
| R11 | Konflikt prawa autorskiego (brand "Claude" w nazwie) | Średnie | Wysokie | Konsultacja prawna przed launch; rebrand opcja (np. "AI Voice Studio", "Voice Code") |
| R12 | MCP standard zmieni się — nasze templates/manager przestaną działać | Niskie | Średnie | MCP version pinning; szybkie update gdy Anthropic ogłosi breaking change |
| R13 | Multi-AI proxy MCP (Faza 4) okaże się wolny / niestabilny | Średnie | Niskie | To opcjonalna funkcja (Q1 - można nie implementować); fallback: zostawiamy "Claude Code only" |

---

## 12. Zależności i założenia

### Założenia
- **Wojtek pracuje solo,** ~20h/tydzień na ten projekt
- **Claude Code CLI jest zainstalowany u użytkownika** — bez tego aplikacja nie działa (instrukcja w onboardingu)
- **Anthropic API key** użytkownik ma własny (nie my dostarczamy AI tokens — klient płaci Anthropic osobno)
- **Groq API key** (dla STT) — użytkownik ma własny
- **VPS Hostinger ma capacity** na license server + landing page + reklamy CMS + ads endpoint
- **Stripe konto można otworzyć** w Polsce
- **Faktury VAT** wystawiane przez istniejący system (CRM lub manual)

### Zależności techniczne
- **Claude Code CLI MUSI być stabilny** — to nasza dependency (R2)
- **MCP standard MUSI być stabilny** — kluczowe dla Faz 1 i 3 (R12)
- **License server MUSI być przed Fazą 1 launch** — bez niego nie ma sprzedaży
- **PWA wymaga reużywalnego API** (Anthropic API proxy w `/api/chat`) — decyzja w T4.2
- **Code signing certificates:** Authenticode (~$200/rok) + Apple Developer ($99/rok) — koszt operacyjny ~$300/rok

### Zależności biznesowe
- **Konsultacja prawna** dla Terms of Service / Privacy Policy (jednorazowo €100-300)
- **Konsultacja brandingowa:** czy "Claude Voice Assistant" jest bezpieczne? (R11) — możliwa zmiana nazwy
- **GDPR compliance** dla EU klientów — w onboardingu opt-in dla telemetrii (Q8)
- **Anthropic Partner Program** — czy aplikujemy? Ułatwia legitimacy + co-marketing

---

## 13. Otwarte pytania (do uzgodnienia)

| # | Pytanie | Kiedy zdecydować |
|---|---------|------------------|
| Q1 | **Czy implementujemy multi-AI proxy MCP w Fazie 4B?** Czy zostajemy 100% Claude Code only? | Przed T4.11 (Faza 4) |
| Q2 | Lista konkretnych modeli Claude Code (Sonnet 4.6, Opus 4.7, Haiku 4.5) — czy wybór per agent? | Przed T1.1 (już jest w kodzie!) |
| Q3 | Pricing: €9/mc i €79/rok — czy testujemy inne ceny (€7, €12)? | Przed T1.8 (Stripe) |
| Q4 | Reklamy: tylko własne (CRM, n8n) czy AdSense fallback? | Przed T1.13 |
| Q5 | Mobile native: Flutter vs React Native? | Przed Faza 4C |
| Q6 | Czy oferujemy lifetime license? (np. €299 jednorazowo) | Przed T1.8 |
| Q7 | Czy zbieramy telemetrię? (Sentry / własne / brak) — kontekst GDPR | Przed T1.15 (onboarding) |
| Q8 | **Premium voices: ElevenLabs (drogie) czy OpenAI TTS (tańsze) czy oba?** | Przed T1.11 |
| Q9 | **Premium MCP templates — które konkretnie?** (Stripe, SendGrid, Slack, Twilio, Notion...?) — lista do uzgodnienia | Przed T1.9 |
| Q10 | **Premium skills bundles — co w nich?** (PM bundle: prd-taskmaster + roadmap-planning + ...?) | Przed T1.9 |
| Q11 | **Nazwa produktu (final)** — wybór z top 3: VibeShell / VibeVox / CodeVibe (lub nowa propozycja). ⏸️ ODŁOŻONE do Fazy 0 (T0.B.1-T0.B.4). Decyzja strategiczna: bez "Claude" w nazwie publicznej. | T0.B.4 (Faza 0) |
| Q12 | Czy Faza 0 powinna sprawdzić **inne ukryte bugi** w kodzie (poza TTS pipeline)? Np. czy `pyenchant` faktycznie jest używany? | Przed T0.2 |

---

## 14. Future scope (poza tym PRD)

Funkcje **rozważane** ale przesunięte poza zakres tego PRD. Możemy do nich wrócić w **Faza 5+** lub jako osobne produkty:

### F-FUT-001 Multi-AI providers (`AIProvider` ABC)
- **Co:** Refactor `claude_bridge.py` na abstraction layer + dodanie OpenAI, Gemini, Ollama jako równorzędne providery
- **Dlaczego nie teraz:** Big refactor, ryzyko regresji, MCP gateway proxy (Faza 4B) załatwi case multi-AI z mniejszym kosztem
- **Kiedy wrócić:** Jeśli w Fazie 4B okaże się że MCP proxy jest za wolne lub niestabilne

### F-FUT-002 Kalendarz + AI scheduler
- **Co:** Wbudowany kalendarz, lista zadań z deadline, AI scheduler ("wykonaj prompt X o 9:00 codziennie"), Google Calendar sync
- **Dlaczego nie teraz:** Scope creep — to inna kategoria produktu (productivity tool, nie AI assistant), wymaga PM persona ale nie jest kluczowe dla Claude Code users
- **Kiedy wrócić:** Po Fazie 3, jeśli PM persona jest dużą grupą klientów Pro

### F-FUT-003 Front-end designer (HTML/CSS live preview)
- **Co:** Edytor kodu + QWebEngineView preview pane + AI generation HTML/Tailwind z prompta
- **Dlaczego nie teraz:** To inny produkt (vs CodePen, v0.dev, Webflow), nie pasuje do "Claude Code Voice Studio"
- **Kiedy wrócić:** Jako osobny produkt jeśli traction. Albo jako MCP server (`html-preview-mcp`)

### F-FUT-004 Enterprise tier (multi-user, SSO, on-premise)
- **Co:** SAML SSO, multi-user license, on-premise license server, audit logs
- **Dlaczego nie teraz:** Wymaga dedykowanego sales motion, brak target enterprise klientów w Fazach 1-4
- **Kiedy wrócić:** Po 100+ płatnych klientów Pro, gdy będzie sygnał z rynku

### F-FUT-005 Wbudowany code editor
- **Co:** Pełen edytor kodu (jak VS Code Lite) wewnątrz aplikacji
- **Dlaczego nie teraz:** Claude Code już ma edycję plików przez tools, dodawanie redundantnego edytora to scope creep
- **Kiedy wrócić:** Tylko jeśli sygnał z user testów

### F-FUT-006 Marketplace dla agent templates (community contributions)
- **Co:** Społeczność może publikować swoje agent templates (`PM agent`, `Code Reviewer agent`), inni mogą instalować
- **Dlaczego nie teraz:** Wymaga moderation, hosting, legal review, account system
- **Kiedy wrócić:** Faza 5+ jako część social/community features

---

## 15. Changelog dokumentu

| Data | Wersja | Autor | Zmiany |
|------|--------|-------|--------|
| 2026-05-09 | 1.0 (DRAFT) | Wojtek | Pierwsza wersja PRD: 5 faz, 22 funkcje, 6-9 miesięcy, model freemium open-core. **WADA: pisany bez czytania kodu.** |
| 2026-05-09 | 2.0 (DRAFT) | Wojtek | **MAJOR REWRITE po audicie kodu.** Wizja: Multi-AI hub → Claude Code Voice Studio. Multi-AI providers przeniesione do Future scope (F-FUT-001) lub Faza 4B przez MCP gateway proxy. Kalendarz + designer przeniesione do Future (F-FUT-002, F-FUT-003). Dodane: F-MCP-003/004 (Premium MCP templates + marketplace), F-SKL-003/004 (Premium skills bundles + marketplace), F-AGT-001/002 (multi-agent jako Pro feature, agent templates), F-VOI-006 (premium voices ElevenLabs/OpenAI), F-LNG-001 (Polish encoding fix dokumentacja). Pro tier value prop zmieniony: nie multi-AI, ale unlimited MCP/Skills + multi-agent + premium voices + premium MCP templates. Faza 0 wzbogacona o F-VOI-007 (audit czy `text_cleaner.py` jest podpięty do TTS pipeline). Razem 27 funkcji w PRD + 6 w Future scope. |
| 2026-05-09 | 2.1 (DRAFT) | Wojtek | Dodane: kategoria **Branding** (F-BRD-001 nazwa, F-BRD-002 logo+ikona, F-BRD-003 domena .app, F-BRD-004 brand guidelines). Decyzje: nazwa **bez "Claude"** (R11 mitygacja), domena **.app** (HTTPS forced), logo **DIY przez AI generator** (Looka/Brandmark/Logo.com). Faza 0: +4 taski branding (T0.B.1-T0.B.4). Faza 1: +6 tasków logo (T1.B.1-T1.B.6). Czas Fazy 1: 28d → 32d. Nowa sekcja 16 z **10 propozycjami nazw** do walidacji w Fazie 0. Razem 31 funkcji w PRD + 6 w Future scope. |
| 2026-05-09 | 2.2 (DRAFT) | Wojtek | **Sekcja 16 znacznie rozbudowana po wstępnej walidacji.** Sprawdzone: cva.app (❌ na sprzedaż premium), voiceforge.app (❌ TTS app na iOS), vibecode.app (❌ trademark conflict — Vibecode startup). Dodane 9 nowych propozycji w kategoriach Hybrydy + Vibe (CVA, VibeCode, VibeShell, VibeVox, CodeVibe, VibeWave, VibeStudio, VibeTalk, VoxAssist). Nowa top 3: **VibeShell / VibeVox / CodeVibe** (do walidacji w T0.B.3). Sekcja 16.5: notatka o wewnętrznej (claude-voice-assistant — bez zmian) vs zewnętrznej (komercyjnej) nazwie. **Status final naming: ⏸️ ODŁOŻONE do Fazy 0 (T0.B.1-T0.B.4).** |

---

**Status dokumentu:** DRAFT — czeka na review.

**Następne kroki:**
1. Wojtek czyta PRD v2.2 → feedback / akceptacja
2. Po akceptacji → odpowiedzieć na otwarte pytania Q1-Q12 (przynajmniej Q2, Q8, Q9, Q10 przed Fazą 1)
3. Start Fazy 0 (T0.1: tag baseline + T0.B.1-T0.B.4: branding — finalizacja nazwy)
4. Aktualizacja PRD po każdej fazie (kolumna Changelog)

---

## 16. Brand naming — propozycje + wstępna walidacja

> **Status:** ⏸️ **OTWARTE** — decyzja final odłożona, do walidacji w T0.B.1-T0.B.4 (Faza 0).
> **Decyzja strategiczna:** Bez "Claude" w nazwie publicznej (bezpieczeństwo prawne wobec Anthropic).
> **Decyzja TLD:** `.app` (HTTPS forced, $15-20/rok).
> **Wewnętrznie:** Folder/repo zostaje `claude-voice-assistant` (nie zmieniamy struktury kodu).

### 16.1 Propozycje rozważone do tej pory

#### Pierwotna lista (10 propozycji — brainstorm 2026-05-09)

| # | Nazwa | Etymologia / koncept | Status walidacji |
|---|-------|----------------------|------------------|
| 1 | **VocalCode** | "Vocal" + "Code" | Niewalidowane |
| 2 | **VoiceForge** | "Voice" + "Forge" | ❌ **ZAJĘTE** — voiceforge.app to TTS app na iOS (Kokoro-based) |
| 3 | **TermVox** | "Terminal" + "Vox" (łac.) | Niewalidowane |
| 4 | **DevVox** | "Dev" + "Vox" | Niewalidowane |
| 5 | **SonarCode** | "Sonar" + "Code" | ❌ **TRADEMARK CONFLICT** — SonarSource (SonarQube) |
| 6 | **AgentVox** | "Agent" + "Vox" | Niewalidowane |
| 7 | **CodeSpeak** | "Code" + "Speak" | Niewalidowane |
| 8 | **Speakly** | "Speak" + "-ly" | Wymaga walidacji (pokrewne brand'y) |
| 9 | **VocalDev** | "Vocal" + "Dev" | Niewalidowane |
| 10 | **Termly** | "Term" + "-ly" | ❌ **TRADEMARK CONFLICT** — Termly.io (privacy SaaS) |

#### Rozszerzenia po feedbacku użytkownika (2026-05-09 — kategorie Hybrydy + Vibe)

| # | Nazwa | Etymologia | Status walidacji |
|---|-------|------------|------------------|
| 11 | **CVA** (cva.app) | Skrót od Cloud/Claude Voice Assistant | ❌ **DOMENA NA SPRZEDAŻ** — cva.app na Aftermarket.com (premium, szac. $1000-10000) + 5 trademarków w innych branżach (finanse, medycyna, security) |
| 12 | **VibeCode** (vibecode.app) | "Vibe" + "Code" | ❌ **TRADEMARK CONFLICT KRYTYCZNY** — Vibecode to aktywny startup (vibecodeapp.com, vibecode.dev), AI mobile app builder, Product Hunt featured, $100M konkurent |
| 13 | **VibeShell** | "Vibe" + "Shell" (terminal) | Niewalidowane (top kandydat) |
| 14 | **VibeVox** | "Vibe" + "Vox" | Niewalidowane (top kandydat) |
| 15 | **CodeVibe** | "Code" + "Vibe" (odwrotne) | Niewalidowane (top kandydat) |
| 16 | **VibeWave** | "Vibe" + "Wave" (dźwięk) | Niewalidowane |
| 17 | **VibeStudio** | "Vibe" + "Studio" | Niewalidowane |
| 18 | **VibeTalk** | "Vibe" + "Talk" | Niewalidowane |
| 19 | **VoxAssist** | "Vox" + "Assist" | Niewalidowane |

### 16.2 🎯 Top 3 do priorytetowej walidacji w T0.B.3

> *Bazujemy na preferencji użytkownika: kategoria Hybrydy + Vibe Code/Coding, bez konfliktu z VibeCode.*

| # | Nazwa | Domena | Dlaczego top |
|---|-------|--------|--------------|
| 1 | 🏆 **VibeShell** | `vibeshell.app` | **Najlepiej opisuje produkt** — wprost mówi "vibe coding w terminalu/shell". Mniejsza konkurencja niż VibeCode |
| 2 | 🥈 **VibeVox** | `vibevox.app` | **Krótkie, brand-able**, łączy trend "vibe" z głosem (vox = łac. głos). Pewnie wolne (mniej oczywiste) |
| 3 | 🥉 **CodeVibe** | `codevibe.app` | Odwrotne do zajętego VibeCode. Nadal trendy, ale inna kolejność słów |

### 16.3 Wykluczone (potwierdzone konflikty)

| Nazwa | Powód wykluczenia |
|-------|-------------------|
| ❌ **VibeCode** / vibecode.app | Vibecode = aktywny startup (mobile app builder), bezpośrednia konkurencja |
| ❌ **VoiceForge** / voiceforge.app | VoiceForge = TTS app na iOS (Kokoro), zajęte |
| ❌ **CVA** / cva.app | Domena na sprzedaż (premium, $$$) + 5+ trademarków w innych branżach |
| ❌ **SonarCode** | Kolizja z SonarSource (SonarQube — code quality tool) |
| ❌ **Termly** | Kolizja z Termly.io (privacy policy SaaS) |
| ❌ **Helix** | Wiele firm (Helix BioPharma, Helix DNA, Helix.com) |
| ❌ **Loom** | Loom.com (Atlassian, video messaging) |
| ❌ **Echo** | Amazon Echo (HUGE trademark) |
| ❌ **Vox** | Vox Media (publishing) |

### 16.4 Walidacja krok po kroku (T0.B.1 → T0.B.2 → T0.B.3 → T0.B.4)

```
T0.B.1 — Brainstorm:
   ✅ Już mamy 19 propozycji (sekcja 16.1)
   - Można dodać kolejne jeśli top 3 nie pasują

T0.B.2 — Trademark check (bezpłatne, każda nazwa):
   - USPTO: https://tmsearch.uspto.gov
   - EUIPO TMview: https://www.tmdn.org/tmview/welcome
   - WIPO Global Brand DB: https://www3.wipo.int/branddb/en/
   - Polska UPRP: https://uprp.gov.pl/pl/przedmioty-ochrony/znaki-towarowe
   - Google search: "<nazwa>" + "trademark" / "company" / "startup"

T0.B.3 — Domain check (Namecheap WHOIS):
   - https://www.namecheap.com/domains/registration/results/?domain=NAZWA.app
   - GoDaddy: https://www.godaddy.com/domainsearch/find?domainToCheck=NAZWA.app
   - Dla każdej z top 3 (VibeShell, VibeVox, CodeVibe)
   - PLUS sprawdzenie .com / .io / .dev jako fallback

T0.B.3.bis — Social handles check (opcjonalnie):
   - https://namecheckr.com/ (Twitter, Instagram, GitHub, LinkedIn, etc.)
   - Czy @vibeshell / @vibevox / @codevibe są wolne?

T0.B.4 — Decyzja final + zakup:
   - Namecheap .app = ~$15-20/rok (najtańsze)
   - DNS Cloudflare (free)
   - SSL Let's Encrypt (free) lub Cloudflare SSL (free)
   - Konfiguracja: A record → VPS Hostinger
   - Optional: ProtonMail dla nazwa@domena.app (Pro plan ~$5/mc)
```

### 16.5 Notatka — wewnętrzna vs zewnętrzna nazwa

**Wewnętrznie (kod, repo, dokumentacja techniczna):**
- Folder: `/home/hdkrytbhdkf/Projekty/claude-voice-assistant/` — bez zmian
- Repo: `https://github.com/WojtekL7/claude-voice-assistant` — bez zmian
- Konfiguracja: `~/.claude-voice-assistant/` — bez zmian
- Klasy/moduły Python — bez zmian

**Zewnętrznie (marketing, sprzedaż, klient):**
- Nazwa produktu: do wyboru w T0.B.4 (np. "VibeShell" / "VibeVox" / "CodeVibe")
- Domena: `<nazwa>.app`
- Splash screen, README dla klienta, landing page — używają nazwy zewnętrznej

**Podstawa dla rebrand wewnętrzny później:** jeśli produkt odniesie sukces, w Fazie 5+ rozważymy:
- Rename folderu: `claude-voice-assistant` → `<nazwa>`
- Rename repo: `claude-voice-assistant` → `<nazwa>`
- Rename ścieżek konfiguracji: `~/.claude-voice-assistant/` → `~/.<nazwa>/`
- Migration script dla istniejących użytkowników

---

*Dokument żywy. Następna recenzja: po Fazie 0 (planowana 2026-05-25).*
