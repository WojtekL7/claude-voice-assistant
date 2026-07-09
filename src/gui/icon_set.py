"""Kreskowe ikony SVG dla przycisków dolnego panelu — spójne na Linux/Mac/Windows.

Zastępują emoji, których wygląd zależał od czcionki systemowej (Apple Color Emoji
na macOS = kolorowe; na Linuksie monochromatyczne). QIcon renderowany z SVG jest
ostry w każdym rozmiarze i DPI.

Ikony są JEDNOKOLOROWE i rysowane obrysem (`stroke="currentColor"`). Kolor podaje
wołający — zwykle z bieżącej skórki (`icon_*_color`). Wcześniej barwy były zaszyte
w plikach, więc ustawienia koloru ikon w oknie „Skórka" nie robiły nic; teraz
działają.

Mapowanie (klucz przycisku, stan) → plik SVG odzwierciedla DEFAULT_SKIN_ICONS
w main_window (te same klucze i stany), tyle że zamiast glifu zwraca QIcon.
"""
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer

import config

_ICON_DIR = config.ASSETS_DIR / "icons"
_cache = {}
_source_cache = {}

# Rozmiar renderowania. Ikona na przycisku ma ~17 px; renderujemy z zapasem na
# ekrany o wysokim DPI — QIcon skaluje w dół ostro, w górę byłoby rozmyte.
_RENDER_PX = 64

# Kolor używany, gdy wołający nie poda własnego (stary kod, testy).
_DEFAULT_COLOR = '#9b93a8'

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


def _svg_source(name: str) -> str:
    """Treść pliku <name>.svg (z cache). Pusty string, jeśli pliku brak."""
    if name not in _source_cache:
        try:
            _source_cache[name] = (_ICON_DIR / f"{name}.svg").read_text(encoding='utf-8')
        except OSError:
            _source_cache[name] = ''
    return _source_cache[name]


def _render(name: str, color: str) -> QIcon:
    """Wyrenderuj SVG, podmieniając `currentColor` na `color`."""
    src = _svg_source(name)
    if not src:
        return QIcon()
    renderer = QSvgRenderer(src.replace('currentColor', color).encode('utf-8'))
    if not renderer.isValid():
        return QIcon()
    pm = QPixmap(QSize(_RENDER_PX, _RENDER_PX))
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return QIcon(pm)


def icon_by_name(name: str, color: str = _DEFAULT_COLOR) -> QIcon:
    """QIcon dla pliku <name>.svg pomalowany na `color` (z cache)."""
    key = (name, color)
    if key not in _cache:
        _cache[key] = _render(name, color)
    return _cache[key]


def button_icon(key: str, state: str = 'normal', color: str = _DEFAULT_COLOR) -> QIcon:
    """QIcon dla przycisku o danym kluczu i stanie (fallback na stan 'normal')."""
    name = _STATE_TO_FILE.get((key, state)) or _STATE_TO_FILE.get((key, 'normal'))
    return icon_by_name(name, color) if name else QIcon()


def has_icon(key: str) -> bool:
    """Czy dany klucz przycisku ma ikonę SVG (vs przycisk tekstowy jak 'send')."""
    return (key, 'normal') in _STATE_TO_FILE
