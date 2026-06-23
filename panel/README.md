# VCA — Panel administracyjny (frontend)

Panel admina Vibe Coding Assistant. Przetłumaczony z makiety **cloud.co.design**
(Voltra Admin) na samodzielny, statyczny frontend (czysty HTML/JS, bez budowania)
i podpięty pod backend `../server/` (FastAPI).

## Co jest realne, a co makietą
| Sekcja | Dane |
|--------|------|
| **Klienci** | ✅ realne — licencje z `/api/admin/licenses` (filtry, „Dodaj licencję", „Odbierz") |
| **Pobrania** | ✅ realne — wersje `/api/admin/versions` + statystyki `/api/admin/downloads/stats` |
| **Dashboard** | ✅ realne KPI (subskrypcje/pobrania/licencje/trial, pobrania wg OS) · MRR = DEMO |
| **Subskrypcje** | ✅ realne (licencje Pro) · ceny/MRR = DEMO |
| **Ustawienia** | ✅ połączenie z serwerem · integracje płatności = DEMO |
| **Finanse**, **Wiadomości** | 🟡 DEMO / makieta (Faza B) — oznaczone znaczkiem `DEMO` |

## Uruchomienie
1. Uruchom backend (patrz `../server/README.md`), np. `http://localhost:8088`.
2. Otwórz panel — wystarczy statyczny serwer:
   ```bash
   cd panel && python3 -m http.server 9000
   # → http://localhost:9000
   ```
   (albo otwórz `index.html` wprost w przeglądarce).
3. W oknie logowania podaj **adres API** i **token administratora** (`ADMIN_TOKEN` serwera).
   Dane zapisują się w `localStorage`.

## Uwagi
- Motyw jasny/ciemny + PL/EN (przełączniki w pasku górnym), zapamiętywane lokalnie.
- Token admina trzymany w `localStorage` przeglądarki — używaj na zaufanym urządzeniu.
- Zweryfikowane e2e w headless Chromium: logowanie → realne dane (licencje, wersje,
  pobrania) bez błędów konsoli.
- Faza B: po wpięciu płatności (Paddle/Stripe) i wiadomości — podmienimy sekcje DEMO na realne.
