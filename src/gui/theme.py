"""Paleta i typografia interfejsu — JEDNO źródło prawdy dla kolorów GUI.

Przed tym modułem kolory żyły w trzech miejscach naraz: słowniku skórki
(reagował na zmianę motywu), arkuszach stylów okna głównego oraz — najgorzej —
w kilkuset literałach hex rozsianych po `dialogs.py`, które na skórkę nie
reagowały wcale. Stąd „wyspy" starego motywu po przeskórkowaniu aplikacji.

Zasada: NIC w warstwie GUI nie zapisuje koloru dosłownie. Wszystko sięga po
token stąd, a `skin_colors()` składa z tokenów słownik, którego oczekuje
`MainWindow` (klucze bez zmian — dialog edycji skórki działa jak działał).

Motyw: „Vibe Purple" (redesign 2026-07) — ciemne tło z fioletowym akcentem.
Od 2026-10 także wariant JASNY (paleta `_LIGHT`, wybór przy starcie programu).
"""
import json
import os


# === Tła (od najciemniejszego) ===
BG_CANVAS = '#0a080e'    # terminal / obszar rozmowy — najgłębszy
BG_WINDOW = '#0e0b14'    # korpus okna
BG_PANEL = '#0d0a13'     # pasek menu, pasek zakładek, panel dolny
BG_BAR = '#100c18'       # pasek tytułu i pasek statusu
BG_INPUT = '#120e1a'     # pole wpisywania polecenia

# === Powierzchnie wypukłe (przyciski, karty, aktywna zakładka) ===
SURFACE = '#171221'
SURFACE_ALT = '#141020'  # karty w dialogach
SURFACE_HOVER = '#1d1729'

# --- Dwa odcienie NIOSĄCE SYGNAŁ (nie zwykłe powierzchnie) ---------------------
# Oba muszą być WYRAŹNIE jaśniejsze od BG_PANEL (#0d0a13), bo ich jedynym
# zadaniem jest odróżnić się od sąsiedztwa. Redesign „Vibe Purple" ustawił je
# zbyt blisko tła (różnica ~10/255 = 4%) i sygnał przestał być czytelny —
# user zgłosił „praktycznie nie ma różnicy" dla OBU naraz (2026-07-20).
# Przywrócona różnica ~30/255 (12%), czyli poziom sprzed redesignu (było 39),
# tyle że w fiolecie zamiast dawnej szarości. Zmiana wymagała podbicia
# SKIN_VERSION → 4 (config.json usera przykrywa paletę).
# ⛔ PODNIESIONE 2026-09-14 NA ŻĄDANIE WŁAŚCICIELA — i to jest nauka o samym
# progu, nie o kolorach. Oba sygnały MIEŚCIŁY SIĘ w regule „≥20/255": zakładka
# miała 26, panel nieaktywny 31. A mimo to właściciel zgłosił oba naraz jako
# „za mało widoczne". Wniosek: 20/255 to PODŁOGA, poniżej której sygnał na
# pewno ginie — nie poziom, przy którym na pewno widać. Na bardzo ciemnym tle
# (pasek ma jasność 14/255) trzeba wyraźnie więcej.
# Zmierzone po zmianie: zakładka +49, panel nieaktywny +55 wobec tła paska.
# Odcień zostaje w rodzinie „Vibe Purple" — zmienia się WYŁĄCZNIE jasność.
TAB_ACTIVE = '#3a2d57'        # wypełnienie AKTYWNEJ zakładki (kontra reszta paska)
SURFACE_INACTIVE = '#413659'  # panel dolny, gdy okno straciło fokus

# === Akcent ===
ACCENT = '#a855f7'         # fiolet wiodący
ACCENT_LIGHT = '#c084fc'   # ikony, linki, tekst akcentowany
ACCENT_DEEP = '#7c3aed'    # ciemniejszy koniec gradientu
ACCENT_GLOW = '#e879f9'    # różowy koniec gradientu (paski, podkreślenia)

# === Ramki i separatory ===
# Odpowiedniki rgba(168,85,247,0.22) i rgba(255,255,255,0.05) zmieszane z tłem —
# QSS Qt obsługuje rgba(), ale dialog skórki pokazuje próbniki kolorów, więc
# trzymamy nieprzezroczyste hexy (inaczej color picker dostaje wartość, której
# nie umie odwzorować).
BORDER = '#301b46'         # ramka fioletowa (na tle okna)
BORDER_SUBTLE = '#241933'  # separator/rozdzielacz
HOVER = '#3a2a5a'          # podświetlenie menu; też zaznaczenie w terminalu

# === Tekst ===
TEXT = '#eae6f2'        # główny
TEXT_DIM = '#9b93a8'    # drugorzędny (podpisy, nieaktywne zakładki)
TEXT_FAINT = '#605868'  # monospace w pasku statusu, metadane

# === Kolory znaczeniowe ===
# Niosą ZNACZENIE, nie dekorację: czerwony = groźne/błąd, zielony = OK/zapisz,
# żółty = uwaga, niebieski = informacja. Nigdy nie zastępuj ich akcentem —
# „Usuń agenta" nie może wyglądać jak „Anuluj".
DANGER = '#f0616d'
DANGER_LIGHT = '#f0868f'
SUCCESS = '#3ecf8e'
WARNING = '#e6b053'
ALERT = '#f08b4c'   # pośredni stopień ostrzeżenia (skala obciążenia RAM)
INFO = '#5b9dd9'
TEAL = '#4fb3a8'

# === Tory pasków (np. zużycie kontekstu na pasku statusu) ===
TRACK_BG = '#2a2a2e'
TRACK_BORDER = '#3a3a3e'

# === Terminal ===
# Barwy tekstu w terminalu, których nie da się wziąć z tokenów wyżej (tekst
# terminala jest celowo ciemniejszy niż TEXT, a „jasne" warianty ANSI mają
# własne odcienie). Trzymane jako tokeny, żeby tryb jasny mógł je podmienić.
TERM_FG = '#b8b2c4'
TERM_BLACK = '#1a1622'
TERM_BLACK_BRIGHT = '#4a4356'
TERM_GREEN_BRIGHT = '#5fe0a6'
TERM_YELLOW_BRIGHT = '#f0c979'
TERM_BLUE_BRIGHT = '#7db8e8'
TERM_TEAL_BRIGHT = '#6fd0c4'

# === Typografia ===
# Nazwy rodzin tak, jak rejestruje je QFontDatabase z plików w assets/fonts.
FONT_UI = 'IBM Plex Sans'
FONT_MONO = 'JetBrains Mono'
# Awaryjne, gdy pliki .ttf nie wejdą do paczki (np. własny build bez assets).
FONT_UI_FALLBACK = 'Ubuntu'
FONT_MONO_FALLBACK = 'Ubuntu Mono'

# === Geometria ===
RADIUS_SM = 6    # drobne elementy (znaczki, X zakładki)
RADIUS = 10      # przyciski narzędziowe
RADIUS_LG = 12   # pole wpisywania, przycisk Enter
RADIUS_XL = 14   # okna modalne


# === TRYB JASNY ===
# Druga paleta w tej samej rodzinie „Vibe Purple": jasne liliowe tła, ciemny
# tekst, ciemniejszy fiolet akcentu (jasny fiolet z trybu ciemnego ginie na
# bieli). Tryb startowy wybieramy przy imporcie tego modułu; od 2026-10-20
# przełącza się też W LOCIE (`set_appearance`, bez restartu programu).
# ⚠️ Zasada dla całej warstwy GUI: sięgaj po kolor jako `theme.X` W CHWILI
# rysowania/stylowania. Kopia zrobiona przy imporcie (`_X = theme.Y` na górze
# modułu, wartość domyślna parametru) zostaje przy starym trybie — to dokładnie
# te miejsca wymagały przeróbki przy przełączaniu w locie. Pilnuje tego
# tools/test-theme-live.py (okno przełączone w locie = okno uruchomione od razu
# w tym trybie, co do piksela).
# Kontrast pilnuje tools/test-theme-light.py (tekst ≥ 4,5:1, drobne ≥ 3:1).
APPEARANCE_DARK = 'dark'
APPEARANCE_LIGHT = 'light'

_LIGHT = {
    'BG_CANVAS': '#fcfbfe',
    'BG_WINDOW': '#f6f3fb',
    'BG_PANEL': '#f1ecf8',
    'BG_BAR': '#ebe5f4',
    'BG_INPUT': '#ffffff',
    'SURFACE': '#ffffff',
    'SURFACE_ALT': '#faf8fd',
    'SURFACE_HOVER': '#ece4f8',
    # Sygnały (patrz uwaga przy ciemnych): na jasnym tle sygnałem jest
    # PRZYCIEMNIENIE — różnica jasności wobec BG_PANEL mierzona w bramce.
    'TAB_ACTIVE': '#c6b2ea',
    'SURFACE_INACTIVE': '#c8bed6',
    'ACCENT': '#7c3aed',
    'ACCENT_LIGHT': '#6d28d9',   # ikony/linki/tekst — na bieli MUSI być ciemniejszy
    'ACCENT_DEEP': '#5b21b6',
    'ACCENT_GLOW': '#c026d3',
    'BORDER': '#d5c6ec',
    'BORDER_SUBTLE': '#e4dcef',
    'HOVER': '#e2d4f8',          # też zaznaczenie w terminalu
    'TEXT': '#1d1726',
    'TEXT_DIM': '#4f4760',
    'TEXT_FAINT': '#7f778c',
    'DANGER': '#c42b3a',
    'DANGER_LIGHT': '#d24955',
    'SUCCESS': '#12805a',
    'WARNING': '#9a6200',
    'ALERT': '#b8521a',
    'INFO': '#2566ad',
    'TEAL': '#1a7a70',
    # Terminal: „jasne" warianty ANSI mają być WYRAŹNIEJSZE, czyli na bieli
    # ciemniejsze lub nasycone — nie bledsze (jaskrawa żółć zniknęłaby).
    'TRACK_BG': '#e2dcea',
    'TRACK_BORDER': '#cfc6dc',
    'TERM_FG': '#2b2435',
    'TERM_BLACK': '#1d1726',
    'TERM_BLACK_BRIGHT': '#6b6478',
    'TERM_GREEN_BRIGHT': '#0f9963',
    'TERM_YELLOW_BRIGHT': '#a86f00',
    'TERM_BLUE_BRIGHT': '#2f78c2',
    'TERM_TEAL_BRIGHT': '#168a7e',
}


def _wanted_appearance() -> str:
    """Tryb z ustawień programu; zmienna CVA_APPEARANCE ma pierwszeństwo (testy).

    Fail-safe: nieczytelny plik, brak klucza albo dziwna wartość = ciemny,
    czyli wygląd sprzed wprowadzenia trybu jasnego.
    """
    env = (os.environ.get('CVA_APPEARANCE') or '').strip().lower()
    if env in (APPEARANCE_DARK, APPEARANCE_LIGHT):
        return env
    try:
        from config import CONFIG_FILE
        with open(CONFIG_FILE, encoding='utf-8') as f:
            value = json.load(f).get('appearance')
    except Exception:
        return APPEARANCE_DARK
    return APPEARANCE_LIGHT if value == APPEARANCE_LIGHT else APPEARANCE_DARK


# Wartości ciemne zapamiętane PRZED ewentualną podmianą — bez nich powrót
# z jasnego na ciemny w locie nie miałby skąd wziąć kolorów.
_DARK = {k: globals()[k] for k in _LIGHT}

APPEARANCE = _wanted_appearance()
if APPEARANCE == APPEARANCE_LIGHT:
    globals().update(_LIGHT)


def set_appearance(mode: str) -> bool:
    """Przełącz paletę W LOCIE; zwraca True, gdy tryb faktycznie się zmienił.

    Podmienia tokeny tego modułu. Przemalowanie widżetów, które już stoją,
    należy do wołającego (MainWindow._apply_appearance). Nieznana wartość =
    ciemny (fail-safe jak przy starcie).
    """
    global APPEARANCE
    mode = APPEARANCE_LIGHT if mode == APPEARANCE_LIGHT else APPEARANCE_DARK
    if mode == APPEARANCE:
        return False
    globals().update(_LIGHT if mode == APPEARANCE_LIGHT else _DARK)
    APPEARANCE = mode
    return True


def is_light() -> bool:
    """Czy program działa teraz w trybie jasnym."""
    return APPEARANCE == APPEARANCE_LIGHT


def by_mode(dark: str, light: str) -> str:
    """Kolor zależny od trybu — dla STARYCH miejsc z kolorem wpisanym na sztywno.

    W trybie ciemnym oddaje DOKŁADNIE dawną wartość (wygląd ciemny bez zmian,
    co do piksela), w jasnym — podany token. Nowy kod niech sięga po tokeny.
    """
    return light if is_light() else dark


def _lum(hexc: str) -> float:
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast_ratio(a: str, b: str) -> float:
    """Kontrast WCAG dwóch kolorów #rrggbb (1..21)."""
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable(color: str, minimum: float = 3.0) -> str:
    """Kolor WYBRANY PRZEZ UŻYTKOWNIKA (np. kolor agenta) czytelny na tle paska.

    Paleta kolorów agentów była dobierana pod ciemne tło — jasnoszary czy żółty
    znikają na jasnym. W trybie jasnym przyciemniamy taki kolor (ten sam odcień),
    aż odetnie się od BG_PANEL co najmniej `minimum`:1. Zapisany kolor agenta się
    NIE zmienia — to tylko sposób wyświetlenia. Tryb ciemny: bez zmian.
    """
    if not is_light() or not isinstance(color, str):
        return color
    c = color.strip()
    if len(c) == 4 and c.startswith('#'):
        c = '#' + ''.join(ch * 2 for ch in c[1:])
    if len(c) != 7 or not c.startswith('#'):
        return color
    try:
        r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    except ValueError:
        return color
    k = 1.0
    out = c
    while contrast_ratio(out, BG_PANEL) < minimum and k > 0.05:
        k -= 0.05
        out = '#%02x%02x%02x' % (round(r * k), round(g * k), round(b * k))
    return out


def icon_path(path, color: str) -> str:
    """Ścieżka ikony SVG dopasowanej do trybu (do `url(...)` w QSS i QIcon).

    Pliki .svg mają kolor wpisany w środek (szary #9b93a8 albo biały) —
    dobry na ciemnym tle, niewidoczny na jasnym. W trybie ciemnym zwracamy
    oryginał bez zmian; w jasnym — kopię przemalowaną na `color`, zapisaną
    w katalogu ustawień programu. Fail-open: błąd zapisu = oryginał.
    """
    path = str(path)
    if not is_light():
        return path
    try:
        from pathlib import Path
        from config import CONFIG_DIR
        src = Path(path)
        svg = src.read_text(encoding='utf-8')
        for old in ('#9b93a8', '#ffffff', '#FFFFFF', '"white"'):
            svg = svg.replace(old, f'"{color}"' if old.startswith('"') else color)
        out_dir = CONFIG_DIR / 'theme-icons'
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f'{src.stem}-{color.lstrip("#")}{src.suffix}'
        if not out.exists() or out.read_text(encoding='utf-8') != svg:
            out.write_text(svg, encoding='utf-8')
        return str(out)
    except Exception:
        return path


def toggle_icon_path(path, checked: bool) -> str:
    """Obrazek przełącznika „Auto-czytaj odpowiedzi" dopasowany do trybu.

    Pliki toggle-*.svg mają kolory trybu ciemnego wpisane na sztywno, a szyna
    wyłączonego przełącznika (#2a2435) była na jasnym panelu ciemną plamą
    (zgłoszenie właściciela 2026-10-20: „tło przełącznika powinno być jasne").
    W jasnym: szyna jasna z cienką obwódką, gałka przygaszona; włączony zostaje
    w kolorze akcentu, bo kolor niesie tu STAN. W ciemnym: oryginał bez zmian.
    """
    path = str(path)
    if not is_light():
        return path
    if checked:
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="42" height="24" '
               'viewBox="0 0 42 24">'
               f'<rect x="0" y="0" width="42" height="24" rx="12" fill="{ACCENT}"/>'
               '<circle cx="30" cy="12" r="9" fill="#ffffff"/></svg>')
    else:
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="42" height="24" '
               'viewBox="0 0 42 24">'
               f'<rect x="0.5" y="0.5" width="41" height="23" rx="11.5" '
               f'fill="{TRACK_BG}" stroke="{TRACK_BORDER}"/>'
               f'<circle cx="12" cy="12" r="9" fill="{TEXT_FAINT}"/></svg>')
    try:
        from pathlib import Path
        from config import CONFIG_DIR
        out_dir = CONFIG_DIR / 'theme-icons'
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f'{Path(path).stem}-light.svg'
        if not out.exists() or out.read_text(encoding='utf-8') != svg:
            out.write_text(svg, encoding='utf-8')
        return str(out)
    except Exception:
        return path


def _family_or_fallback(wanted: str, fallback: str) -> str:
    """Zwróć `wanted`, o ile Qt naprawdę zna tę rodzinę czcionek.

    QFontDatabase podstawia zamiennik po cichu, więc `QFont("JetBrains Mono")`
    na maszynie bez tej czcionki wygląda poprawnie w kodzie, a fatalnie na
    ekranie. Sprawdzamy jawnie i schodzimy na czcionkę, którą na pewno mamy.
    """
    try:
        from PyQt5.QtGui import QFontDatabase
        return wanted if wanted in set(QFontDatabase().families()) else fallback
    except Exception:
        return fallback


def ui_family() -> str:
    """Rodzina czcionki interfejsu (etykiety, przyciski, menu)."""
    return _family_or_fallback(FONT_UI, FONT_UI_FALLBACK)


def mono_family() -> str:
    """Rodzina czcionki o stałej szerokości (terminal, dane techniczne)."""
    return _family_or_fallback(FONT_MONO, FONT_MONO_FALLBACK)


def accent_gradient(x1=0, y1=0, x2=1, y2=1) -> str:
    """Gradient akcentu do QSS (przycisk Wyślij, paski postępu)."""
    return (f'qlineargradient(x1:{x1}, y1:{y1}, x2:{x2}, y2:{y2}, '
            f'stop:0 {ACCENT}, stop:1 {ACCENT_DEEP})')


def top_accent_gradient() -> str:
    """Poziomy pasek na górze okna: fiolet → róż → fiolet."""
    return (f'qlineargradient(x1:0, y1:0, x2:1, y2:0, '
            f'stop:0 {ACCENT_DEEP}, stop:0.4 {ACCENT}, '
            f'stop:0.6 {ACCENT_GLOW}, stop:1 {ACCENT_DEEP})')


def skin_colors() -> dict:
    """Złóż słownik skórki (klucze wymagane przez MainWindow) z tokenów palety.

    Zwraca świeży dict przy każdym wywołaniu — wołający (MainWindow, dialog
    skórki) mutują swoją kopię.
    """
    return {
        # --- Interfejs ---
        'main_window_bg': BG_WINDOW,
        'menu_bar_bg': BG_PANEL,
        'status_bar_bg': BG_BAR,
        'bottom_panel_bg': BG_PANEL,
        'border_color': BORDER,
        'hover_color': HOVER,
        'splitter_color': BORDER_SUBTLE,
        'text_color': TEXT,
        'button_bg': SURFACE,
        'button_hover': SURFACE_HOVER,
        'input_bg': BG_INPUT,
        'inactive_panel_bg': SURFACE_INACTIVE,

        # --- Ikony przycisków ---
        # Decyzja usera (2026-07-16): pasek ma być SPOKOJNY — kolor niesie STAN
        # (nagrywanie=czerwień, czytanie=zieleń), a nie sam spoczynek. Dlatego
        # mikrofon / „wyczyść pole" / akcje błyskawiczne są BIAŁE, nie kolorowe.
        # ⚠️ To wartości DOMYŚLNE skórki — zmiana jest niewidoczna bez podbicia
        # SKIN_VERSION (config.json usera je przykrywa). Patrz main_window.
        # ⚠️ IKONY PASKA TRZYMAJĄ JEDNĄ TONACJĘ (TEXT_DIM) — decyzja usera
        # 2026-08-28: „mikrofon, X i błyskawica są bardziej białe niż pozostałe”.
        # Zmierzone: rysunki ikon są identycznej jasności, różnicę robił WYŁĄCZNIE
        # kolor przypisany tutaj (cztery na TEXT, reszta na TEXT_DIM).
        # Wyjątki poniżej są CELOWE i nie wolno ich „ujednolicić”:
        #   * pause/stop niosą STAN (akcent / czerwień) — patrz konwencja koloru;
        #   * send zostaje bielą, bo leży na gradiencie akcentu.
        # Pilnuje tego tools/test-bottom-bar-icons.py.
        'icon_dictate_color': TEXT_DIM,
        'icon_read_color': TEXT_DIM,
        'icon_pause_color': ACCENT_LIGHT,
        'icon_stop_color': DANGER,
        'icon_copy_color': TEXT_DIM,
        'icon_clear_input_color': TEXT_DIM,
        'icon_add_media_color': TEXT_DIM,
        'icon_send_color': '#ffffff',   # na gradiencie akcentu
        'icon_quick_actions_color': TEXT_DIM,
        # Lupa — BIAŁA (życzenie usera 2026-08-04: „ma być jak reszta, negatyw
        # tego co było"). Klucz DODANY, nie zmieniony, więc działa bez podbijania
        # SKIN_VERSION: `_load_settings` iteruje po DEFAULT_SKIN_COLORS i bierze
        # z config.json tylko klucze, KTÓRE TAM SĄ — nowego nie ma, więc zostaje
        # ta wartość, a zapisana skórka użytkownika pozostaje nietknięta.
        'icon_search_color': TEXT_DIM,

        # --- Terminal (16 kolorów ANSI + tło/tekst) ---
        # Dobrane pod składnię, jaką rysuje Claude Code: zielony = dodane linie,
        # czerwony = usunięte, fiolet = słowa kluczowe, niebieski = nazwy plików.
        'terminal_bg': BG_CANVAS,
        'terminal_fg': TERM_FG,
        'terminal_color_0': TERM_BLACK,
        'terminal_color_1': DANGER,
        'terminal_color_2': SUCCESS,
        'terminal_color_3': WARNING,
        'terminal_color_4': INFO,
        'terminal_color_5': ACCENT,
        'terminal_color_6': TEAL,
        'terminal_color_7': TERM_FG,
        'terminal_color_0_bright': TERM_BLACK_BRIGHT,
        'terminal_color_1_bright': DANGER_LIGHT,
        'terminal_color_2_bright': TERM_GREEN_BRIGHT,
        'terminal_color_3_bright': TERM_YELLOW_BRIGHT,
        'terminal_color_4_bright': TERM_BLUE_BRIGHT,
        'terminal_color_5_bright': ACCENT_LIGHT,
        'terminal_color_6_bright': TERM_TEAL_BRIGHT,
        'terminal_color_7_bright': TEXT,
    }
