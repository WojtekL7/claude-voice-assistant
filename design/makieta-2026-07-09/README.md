# Makieta „Vibe Coding Assistant" (Cloud Design, 2026-07-09)

Eksport z cloud.co.design. **To MAKIETA z danymi demo, NIE kod do uruchomienia** —
przy wdrażaniu tłumaczy się ją na realny stack apki (PyQt5), a nie kopiuje.
Format: `<x-dc>`, `<sc-if>`, `<sc-for>`, `{{ }}`, klasa `DCLogic` w
`<script type="text/x-dc">`; `support.js` to runtime tego formatu.

| Plik | Co to |
|------|-------|
| `Vibe Coding Assistant.dc.html` | sama makieta (ekrany, stan, tłumaczenia PL/EN) |
| `support.js` | runtime Cloud Design — bez niego makieta się nie wyrenderuje |

## Stan wdrożenia

- ✅ **Redesign „Vibe Purple" — WDROŻONY** (wydanie 1.0.27, commity `bc81a03` + `410c9ab`).
  Paleta żyje w `src/gui/theme.py`; zmiana kolorów wymaga podbicia `SKIN_VERSION`.
- ⬜ **Ekran Ustawień jako JEDEN modal z bocznym menu** (`settingsTabs` w makiecie) —
  **NIEWDROŻONY**, świadomie odłożony: to zmiana UKŁADU, nie wyglądu, więc była poza
  zakresem redesignu. Dziś ustawienia to menu górne + osobne dialogi.
  To jedyny powód, dla którego ta makieta wciąż jest w repo.

## Czego tu NIE MA

Zrzuty ekranu z oryginalnego eksportu (`screenshots/`, `uploads/`) zostały pominięte —
repo jest **publiczne**, a zrzuty pokazują nazwy zakładek i projektów użytkownika.
Pełny eksport (razem ze zrzutami) leży poza repo: `~/Projekty/makiety/vca-redesign-2026-07-09.zip`.

Ogólny przepis „jak przełożyć `.dc.html` na działający kod" → `CLAUDE-COMMON.md`,
sekcja „CLOUD DESIGN / MAKIETY".
