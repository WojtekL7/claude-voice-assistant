"""Kolorowe ikony SVG dla przycisków dolnego panelu — spójne na Linux/Mac/Windows.

Zastępują emoji, których wygląd zależał od czcionki systemowej (Apple Color Emoji
na macOS = kolorowe; na Linuksie monochromatyczne). QIcon z silnika SVG renderuje
się ostro w każdym rozmiarze i DPI, zachowując własne kolory ikony.

Mapowanie (klucz przycisku, stan) → plik SVG odzwierciedla DEFAULT_SKIN_ICONS
w main_window (te same klucze i stany), tyle że zamiast glifu zwraca QIcon.
"""
from PyQt5.QtGui import QIcon

import config

_ICON_DIR = config.ASSETS_DIR / "icons"
_cache = {}

# (klucz, stan) → nazwa pliku SVG (bez rozszerzenia).
_STATE_TO_FILE = {
    ('dictate', 'normal'): 'mic',
    ('dictate', 'active'): 'mic',          # nagrywanie sygnalizuje czerwona ramka (styl)
    ('dictate', 'processing'): 'hourglass',
    ('read', 'normal'): 'speaker-high',
    ('read', 'active'): 'speaker-mid',
    ('pause', 'normal'): 'pause',
    ('pause', 'active'): 'play',
    ('stop', 'normal'): 'stop',
    ('copy', 'normal'): 'copy',
    ('copy', 'active'): 'check',
    ('clear_input', 'normal'): 'close',
    ('add_media', 'normal'): 'clip',
    ('quick_actions', 'normal'): 'bolt',
}

# Poziomy głośnika do animacji czytania (odpowiednik 🔈 🔉 🔊).
SPEAKER_LEVELS = ['speaker-low', 'speaker-mid', 'speaker-high']


def icon_by_name(name: str) -> QIcon:
    """QIcon dla pliku <name>.svg (z cache). Pusta ikona, jeśli pliku brak."""
    if name not in _cache:
        path = _ICON_DIR / f"{name}.svg"
        _cache[name] = QIcon(str(path)) if path.exists() else QIcon()
    return _cache[name]


def button_icon(key: str, state: str = 'normal') -> QIcon:
    """QIcon dla przycisku o danym kluczu i stanie (fallback na stan 'normal')."""
    name = _STATE_TO_FILE.get((key, state)) or _STATE_TO_FILE.get((key, 'normal'))
    return icon_by_name(name) if name else QIcon()


def has_icon(key: str) -> bool:
    """Czy dany klucz przycisku ma ikonę SVG (vs przycisk tekstowy jak 'send')."""
    return (key, 'normal') in _STATE_TO_FILE
