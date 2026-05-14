# DIAGNOZA: Klawisz Enter nie działa gdy w terminalu są podpowiedzi

**Data:** 2026-05-11 (pierwsze zgłoszenie) · **Aktualizacja:** 2026-05-14 (re-diagnoza — to nie był bug aplikacji)
**Status:** Fix `a2f7b5b` (QT_IM_MODULE=none) z 2026-05-11 zostaje. Drugie zgłoszenie z 2026-05-14 okazało się NIE być bugiem aplikacji — to UX Claude Code (ghost text).

---

## 🔄 Re-diagnoza 2026-05-14 — to NIE był bug aplikacji

### Zgłoszenie

Po 3 dniach normalnej pracy użytkownik zgłosił: „Enter w klawiaturze nie zatwierdza
zaproponowanego tekstu w Claude Code (typu *Sprawdź czy nadal działa po restarcie*).
Klik w przycisk ↵ Enter działa." Pierwsza hipoteza: powrót bug-u iBus z 2026-05-11.

### Wykonane testy diagnostyczne

| Test | Wynik | Wniosek częściowy |
|------|-------|-------------------|
| Klik w przycisk „↵ Enter" w UI | działa | Programowe `sendText` omija warstwę klawiatury — działa |
| Enter w pole input GDY brak podpowiedzi | działa | Klawiatura/IM nie jest globalnie zepsuta |
| Enter w multi-choice picker (↑↓ Tab) | działa | Nie wszystkie popupy łapią bug — tylko „zaproponowany tekst" |
| Rozszerzenie env: `XMODIFIERS=""` + `GTK_IM_MODULE=""` | nie pomogło | Trzy kanały IM wyciszone, mimo to bug stoi |
| `ibus exit` — twardy ubój daemona, test bez restartu apki | nie pomogło | **iBus NIE jest winowajcą tym razem** |
| `claude` w czystym gnome-terminal (poza Voice Assistant), ten sam scenariusz | Enter nie działa, **Tab/→ akceptuje propozycję** | Bug nie istnieje w aplikacji — to UX Claude Code |

### Faktyczna przyczyna — UX Claude Code 2.1.14 (nie bug)

Claude Code od wersji 2.x ma feature **ghost text / autocomplete** — identyczny pattern
jak `fish` i `zsh autosuggestions`:

| Klawisz | Akcja |
|---------|-------|
| **Tab** lub **→** (right arrow) | „Akceptuje" propozycję — wkleja zaproponowany tekst do prompta |
| **Enter** | Wysyła to, co JEST w prompcie (jeśli pusty + ghost text — wysyła pusty wpis, propozycja przepada) |

Stąd zgłoszenie: user widzi ghost text „Sprawdź czy nadal działa", naciska Enter
licząc że to zatwierdzi propozycję — ale claude widzi pusty input i nic nie robi.
Trzeba **najpierw Tab/→** (tekst pojawia się w polu „na sztywno"), **dopiero potem Enter**.

### Co zrobiono z fix-em rozszerzonym

Tymczasowe dodatki w `src/main.py`:
```python
os.environ["XMODIFIERS"] = ""
os.environ["GTK_IM_MODULE"] = ""
```
**zostały cofnięte** — nie pomogły, więc nie ma powodu zostawiać hałasu w kodzie.
Wraca do stanu `a2f7b5b`: tylko `QT_IM_MODULE=none` (ten *faktycznie* zadziałał
11 maja przy klasycznym iBus „candidate window", więc go zostawiamy jako prewencję).

### Wniosek na przyszłość — wzorzec diagnostyczny

Jeśli zgłoszenie brzmi „klawisz nie działa w jednej aplikacji, ale w innej tak" —
**zanim** spojrzysz w kod, **zweryfikuj reprodukowalność poza aplikacją**.
Tu wystarczył jeden test (`claude` w gnome-terminal), żeby przesunąć diagnozę
o 180° — z „bug w QTermWidget/iBus" na „nie-bug, tylko UX". Bez tego kroku
poprzednia sesja wystrzelałaby kolejne `QT_IM_MODULE=xim`, `=compose`, event filtery,
a problem byłby tam gdzie był.

Pełna diagnoza w pierwszej części tego pliku — pozostaje aktualna **dla scenariusza
z 2026-05-11** (klasyczny iBus + popup, fix `QT_IM_MODULE=none`).

---

## Zgłoszenie użytkownika

> "Gdy są zaproponowane teksty w terminalu i naciskam Enter to nie działa.
> We wszystkich zakładkach, ale tylko gdy podpowiada podpowiedzi.
> Nie działa tylko Enter na klawiaturze, a Enter przycisk w aplikacji działa.
> Można nawet dyktować i wprowadzać teksty w ten sposób."

## Objawy (potwierdzone)

| Działanie | Efekt |
|-----------|-------|
| Klawisz Enter na klawiaturze (gdy są podpowiedzi w terminalu) | **NIE działa** |
| Klawisz Enter na klawiaturze (gdy brak podpowiedzi) | działa |
| Przycisk "↵ Enter" w aplikacji (klik myszą) | działa zawsze |
| Dyktowanie (STT) wpisuje tekst do pola | działa |
| Wpisywanie tekstu z klawiatury w pole input | działa |
| Kliknięcie myszą w pole input + Enter (test focusu) | **NIE pomaga** |

## Diagnoza techniczna

### Co wykluczono

1. **Bug w kodzie** — `git log --since="2 days ago"` pokazuje tylko commity dokumentacyjne. Ostatnia zmiana kodu: 7 maja (throttling tokenów, niezwiązane).
2. **Zawieszenie aplikacji** — `py-spy dump --pid 3863` pokazał: MainThread idle w `app.exec_()`, 7 wątków w normalnym stanie. Event loop sprawny.
3. **Focus stealing** — test: kliknięcie w `input_field` przed Enter NIE pomaga. Czyli problem nie jest w focusie Qt.
4. **`_send_message()` slot uszkodzony** — przycisk wywołuje go OK. Slot działa.
5. **Sygnał `returnPressed` rozłączony** — nie, bo gdy podpowiedzi nie ma, Enter wywołuje slot.

### Przyczyna (zidentyfikowana)

```bash
$ cat /proc/3863/environ | tr '\0' '\n' | grep IM
QT_IM_MODULE=ibus
XMODIFIERS=@im=ibus
```

**iBus** (Input Method Bus) — system tłumaczenia klawiatury dla wpisywania znaków specjalnych, języków azjatyckich, emoji.

**Mechanizm:** Gdy w terminalu (QTermWidget) pojawiają się sekwencje/popupy/podpowiedzi od Claude Code, iBus interpretuje to jako stan "candidate window" i **przechwytuje klawisz Enter do potwierdzania kandydata** — Enter nigdy nie dociera do `AutoResizeTextEdit.keyPressEvent`.

Kliknięcie myszy (`QPushButton.clicked`) omija warstwę Input Method, dlatego przycisk działa.
STT wpisuje tekst przez `cursor.insertText()` programowo, też omija iBus.

Aktywny engine: `xkb:us::eng` (przezroczysty) — ale moduł iBus dla Qt nadal pośredniczy w obsłudze klawiszy, co wystarcza, by w wybranym kontekście zablokować Enter.

### Wzorzec dla przyszłych podobnych bugów

Jeśli kiedyś zobaczysz:
- "klawisz X działa w jednej aplikacji, nie w drugiej" lub
- "tylko czasem nie działa, w pewnym kontekście"

→ sprawdź `$QT_IM_MODULE` i `ibus engine` zanim grzebniesz w kodzie aplikacji. Input Method to częsta cicha przyczyna na Linuksie z XWayland.

## Fix (wdrożony)

**Plik:** `src/main.py`, linie 11–22.

```python
# Force X11 backend to fix menu positioning on Wayland
os.environ["QT_QPA_PLATFORM"] = "xcb"

# Wyłącz iBus dla Voice Assistant — pod XWayland z aktywnym iBus klawisz Enter
# jest "zjadany" przez ibus-engine-simple, gdy w terminalu pojawiają się
# podpowiedzi/popupy (Claude Code). Skutek: Enter z klawiatury nie wywołuje
# returnPressed w AutoResizeTextEdit, klik w przycisk "↵ Enter" działa
# (pomija warstwę IM). Wymuszamy "none" — Qt bierze klawisze bezpośrednio
# bez pośrednictwa Input Method. Inne aplikacje (LibreOffice, Firefox)
# iBus nadal używają.
os.environ["QT_IM_MODULE"] = "none"
```

Ustawienie zmiennej środowiskowej **PRZED** importem `PyQt5` — Qt czyta `QT_IM_MODULE` w momencie inicjalizacji `QApplication`. Po imporcie zmiana nic nie da.

## Weryfikacja po restarcie

Po `python3 src/main.py` należy:

1. **Test podstawowy:** Wpisać tekst w pole input → nacisnąć Enter z klawiatury → tekst powinien się wysłać do terminala.
2. **Test właściwy (regresja):** Doprowadzić Claude Code w terminalu do stanu podpowiedzi/popupu (np. wpisać `/` i poczekać na listę slash-commands, albo doprowadzić do prompta "Do you want to proceed?") → nacisnąć Enter z klawiatury → powinno wysłać/zatwierdzić.
3. **Test efektów ubocznych:** Sprawdzić, czy:
   - Polskie znaki (ą, ć, ł) wpisują się normalnie (powinny — jeśli używasz standardowego układu, nie iBus dla polskiego)
   - Wklejanie Ctrl+V działa
   - Shift+Enter dodaje nową linię (zamiast wysyłać)

## Jeśli fix nie zadziała

1. Sprawdź `cat /proc/<PID>/environ | tr '\0' '\n' | grep IM` — czy `QT_IM_MODULE=none` (musi być, nie `ibus`).
2. Spróbuj `QT_IM_MODULE=xim` zamiast `none` — czasem `none` jest źle obsługiwane przez stare PyQt5.
3. Rozważ jeszcze `QT_IM_MODULE=compose` — minimalny dead-key compose bez całego iBus stack.
4. Hipoteza alternatywna: to nie iBus tylko reaguje na nowszą wersję Claude Code (2.0.76) która używa terminalowych "alternate screen" sekwencji (`\e[?1049h`) i zmienia tryb QTermWidget.

## Kontekst sesji (dla następnego Claude)

Rozmowa zaczęła się od podmiany Groq API key (`gsk_29o21...vBkg`) w:
- `~/.claude-voice-assistant/config.json` (Voice Assistant lokalnie)
- `/docker/n8n/docker-compose.yml` na VPS 168.231.127.133 (CRM)

Kontener CRM `n8n-crm-1` został zrestartowany, weryfikacja `docker exec` potwierdziła nowy klucz w env. Backup compose'a zapisany na serwerze jako `docker-compose.yml.bak-<timestamp>`.

Po tym użytkownik zgłosił bug z klawiszem Enter. Bug NIE jest związany z podmianą klucza Groq — to niezależne zjawisko (iBus + nowsza wersja Claude Code).

PID poprzedniej instancji Voice Assistant: 3863 (uruchomiony 09:14, działał ~2.5h gdy zgłoszono bug).

---

*Po pomyślnej weryfikacji ten plik można usunąć (`git rm DIAGNOSE-ENTER-FIX.md`).
W razie potrzeby dopisać znalezisko jako wpis w `~/Projekty/CLAUDE-COMMON.md`
sekcja "Częste problemy" — wzorzec iBus + Qt + interaktywne TUI to klasyczna pułapka.*
