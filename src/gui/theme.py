"""Paleta i typografia interfejsu — JEDNO źródło prawdy dla kolorów GUI.

Przed tym modułem kolory żyły w trzech miejscach naraz: słowniku skórki
(reagował na zmianę motywu), arkuszach stylów okna głównego oraz — najgorzej —
w kilkuset literałach hex rozsianych po `dialogs.py`, które na skórkę nie
reagowały wcale. Stąd „wyspy" starego motywu po przeskórkowaniu aplikacji.

Zasada: NIC w warstwie GUI nie zapisuje koloru dosłownie. Wszystko sięga po
token stąd, a `skin_colors()` składa z tokenów słownik, którego oczekuje
`MainWindow` (klucze bez zmian — dialog edycji skórki działa jak działał).

Motyw: „Vibe Purple" (redesign 2026-07) — ciemne tło z fioletowym akcentem.
"""

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
SURFACE_INACTIVE = '#17141c'  # panel, gdy okno straciło fokus

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
        # W makiecie pasek narzędzi jest stonowany: wyróżnione są tylko
        # mikrofon (akcent), akcje błyskawiczne (bursztyn) i stop (czerwień).
        'icon_dictate_color': ACCENT_LIGHT,
        'icon_read_color': TEXT_DIM,
        'icon_pause_color': ACCENT_LIGHT,
        'icon_stop_color': DANGER,
        'icon_copy_color': TEXT_DIM,
        'icon_clear_input_color': DANGER,
        'icon_add_media_color': TEXT_DIM,
        'icon_send_color': '#ffffff',   # na gradiencie akcentu
        'icon_quick_actions_color': WARNING,

        # --- Terminal (16 kolorów ANSI + tło/tekst) ---
        # Dobrane pod składnię, jaką rysuje Claude Code: zielony = dodane linie,
        # czerwony = usunięte, fiolet = słowa kluczowe, niebieski = nazwy plików.
        'terminal_bg': BG_CANVAS,
        'terminal_fg': '#b8b2c4',
        'terminal_color_0': '#1a1622',
        'terminal_color_1': DANGER,
        'terminal_color_2': SUCCESS,
        'terminal_color_3': WARNING,
        'terminal_color_4': INFO,
        'terminal_color_5': ACCENT,
        'terminal_color_6': TEAL,
        'terminal_color_7': '#b8b2c4',
        'terminal_color_0_bright': '#4a4356',
        'terminal_color_1_bright': DANGER_LIGHT,
        'terminal_color_2_bright': '#5fe0a6',
        'terminal_color_3_bright': '#f0c979',
        'terminal_color_4_bright': '#7db8e8',
        'terminal_color_5_bright': ACCENT_LIGHT,
        'terminal_color_6_bright': '#6fd0c4',
        'terminal_color_7_bright': TEXT,
    }
