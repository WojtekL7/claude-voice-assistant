"""
Claude Voice Assistant — wskaźnik zużycia pamięci RAM (pasek statusu).

Rysowana ikona „kości RAM" (moduł DIMM) zmienia kolor wg obciążenia pamięci
CAŁEGO komputera (RAM + swap):
  🟢 zielony     < 70 %    — luz
  🟡 żółty       70–84 %   — rośnie
  🟠 pomarańcz.  85–94 %   — wysoko
  🔴 czerwony    ≥ 95 %    — blisko zawieszenia (swap/OOM)

Obok ikony procent zużycia. Dymek (tooltip): ile RAM zużywa SAM program (razem
z procesami Claude Code w zakładkach — to one potrafią zjeść 3–5 GB każdy) oraz
ile cały system (+ swap).

Pomiar przez `psutil` — OPCJONALNY: brak biblioteki = widżet po prostu się nie
pokazuje, a reszta aplikacji działa bez zmian (jak z `pygame`).
"""
import os
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, QSize, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt5.QtWidgets import QWidget

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import t as tr

# psutil jest opcjonalny — bez niego wskaźnik się nie pokazuje (graceful).
try:
    import psutil
    PSUTIL_AVAILABLE = True
except Exception:  # ImportError lub błąd ładowania natywnego rozszerzenia
    psutil = None
    PSUTIL_AVAILABLE = False

# Progi kolorów (procent obciążenia pamięci → kolor ikony).
_GREEN = QColor(0x4a, 0xde, 0x80)
_YELLOW = QColor(0xfa, 0xcc, 0x15)
_ORANGE = QColor(0xfb, 0x92, 0x3c)
_RED = QColor(0xef, 0x44, 0x44)

# Co ile odświeżać pomiar (ms). 2,5 s = na bieżąco, bez obciążania CPU.
_REFRESH_MS = 2500


def _human_bytes(n: float) -> str:
    """Bajty → czytelny zapis (GB/MB) bez żargonu."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "—"
    gb = n / (1024 ** 3)
    if gb >= 1.0:
        return f"{gb:.1f} GB"
    mb = n / (1024 ** 2)
    return f"{mb:.0f} MB"


def _color_for(pressure: float) -> QColor:
    """Kolor ikony wg łącznego obciążenia pamięci (0–100)."""
    if pressure >= 95:
        return _RED
    if pressure >= 85:
        return _ORANGE
    if pressure >= 70:
        return _YELLOW
    return _GREEN


class ResourceMonitorWidget(QWidget):
    """Ikona kości RAM + procent zużycia, kolorowana wg obciążenia pamięci.

    Siedzi w pasku statusu obok licznika tokenów. Sama odświeża się co ~2,5 s.
    Jest niezależna od aktywnej zakładki (mierzy CAŁY komputer i CAŁE drzewo
    procesów aplikacji)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pct = 0          # % zużycia RAM (do pokazania jako liczba)
        self._pressure = 0     # łączne obciążenie (RAM + swap) → kolor
        self._available = PSUTIL_AVAILABLE
        self._proc = None
        if self._available:
            try:
                self._proc = psutil.Process(os.getpid())
            except Exception:
                self._available = False

        self.setVisible(self._available)
        if not self._available:
            return

        self.setMinimumHeight(20)
        self.setToolTip(tr('ram_indicator_loading'))

        self._timer = QTimer(self)
        self._timer.setInterval(_REFRESH_MS)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        # Pierwszy pomiar od razu (bez czekania na timer).
        QTimer.singleShot(300, self._refresh)

    # ---------------------------------------------------------------- pomiar
    def _process_tree_rss(self) -> int:
        """Suma pamięci (RSS) procesu aplikacji i WSZYSTKICH jego dzieci.

        Dzieci to m.in. procesy `claude` (Claude Code) w zakładkach, Node.js,
        QtWebEngineProcess i powłoki terminala — czyli realne zużycie „programu"."""
        total = 0
        try:
            total += self._proc.memory_info().rss
        except Exception:
            return 0
        try:
            for child in self._proc.children(recursive=True):
                try:
                    total += child.memory_info().rss
                except Exception:
                    continue  # proces mógł właśnie zniknąć — pomiń
        except Exception:
            pass
        return total

    def _refresh(self):
        if not self._available:
            return
        try:
            vm = psutil.virtual_memory()
            sm = psutil.swap_memory()
        except Exception:
            return

        mem_pct = float(vm.percent)
        swap_pct = float(sm.percent) if getattr(sm, "total", 0) else 0.0

        # Łączne obciążenie do koloru: użycie swapu = system JUŻ się dusi,
        # więc podbijamy „groźność" niezależnie od samego % RAM.
        pressure = mem_pct
        if swap_pct >= 25:
            pressure = max(pressure, 90)
        if swap_pct >= 60:
            pressure = max(pressure, 96)

        self._pct = int(round(mem_pct))
        self._pressure = pressure

        prog = _human_bytes(self._process_tree_rss())
        used = _human_bytes(vm.used)
        total = _human_bytes(vm.total)
        if getattr(sm, "total", 0):
            swap = f"{_human_bytes(sm.used)} / {_human_bytes(sm.total)} ({int(round(swap_pct))}%)"
        else:
            swap = tr('ram_indicator_swap_none')

        self.setToolTip(tr('ram_indicator_tooltip').format(
            prog=prog, used=used, total=total, pct=self._pct, swap=swap))
        self.update()  # przemaluj ikonę nowym kolorem/liczbą

    # -------------------------------------------------------------- rysowanie
    def _text(self) -> str:
        return f"{self._pct}%"

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance("100%")
        # 22 px na ikonę kości + odstęp + tekst.
        return QSize(22 + 6 + text_w + 6, 20)

    def paintEvent(self, event):
        if not self._available:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        color = _color_for(self._pressure)
        h = self.height()

        # --- ikona „kość RAM" (moduł DIMM) ---
        icon_w, icon_h = 20, 13
        x0 = 1
        y0 = (h - icon_h) / 2.0
        body = QRectF(x0, y0, icon_w, icon_h)

        # Korpus modułu — wypełniony kolorem obciążenia, ciemny obrys.
        p.setPen(QPen(color.darker(160), 1.2))
        p.setBrush(QBrush(color))
        p.drawRoundedRect(body, 2.0, 2.0)

        # Układ scalony (ciemne prostokąty na kości) — czytelnie „RAM".
        chip_color = color.darker(200)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(chip_color))
        chip_w = 3.0
        chip_h = 6.0
        chip_y = y0 + 2.0
        for i in range(3):
            cx = x0 + 3.0 + i * (chip_w + 2.0)
            p.drawRect(QRectF(cx, chip_y, chip_w, chip_h))

        # Złote „nóżki" (styki) u dołu kości.
        p.setPen(QPen(color.darker(220), 1.0))
        pins_y = y0 + icon_h - 1.0
        for i in range(6):
            px = x0 + 2.0 + i * 3.0
            p.drawLine(int(px), int(pins_y), int(px), int(pins_y + 2.0))

        # --- procent obok ikony ---
        f = QFont(self.font())
        f.setPointSizeF(max(8.0, f.pointSizeF()))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(color))
        text_rect = QRectF(x0 + icon_w + 6, 0, self.width() - (x0 + icon_w + 6), h)
        p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self._text())
        p.end()

    def stop(self):
        """Zatrzymaj odświeżanie (przy zamykaniu aplikacji)."""
        if getattr(self, "_timer", None) is not None:
            self._timer.stop()
