"""Skan okien dialogowych: czy któryś widżet jest ŚCIŚNIĘTY (niższy niż jego
naturalna wysokość) — czyli czy ucina tekst (ogonki liter, urwane opisy).

Uruchamianie (z katalogu projektu):

    env -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH QT_QPA_PLATFORM=offscreen \
        ./venv/bin/python tools/scan-dialog-clipping.py

Po co: redesign podniósł czcionki, a sztywne wysokości wpisane pod stare czcionki
zostały w kodzie → Qt po cichu ściska rzędy i przycina glify (bez błędu, bez
suwaka). Ten skan wyłapuje takie miejsca ZANIM zobaczy je użytkownik.

⚠️ Pułapka pomiaru: dla etykiety z zawijaniem `sizeHint().height()` KŁAMIE
(opisuje jedną linię przy innej szerokości) — właściwą miarą jest
`heightForWidth(width)`. Bez tego skan sypie fałszywymi alarmami.
"""
import sys, traceback
sys.path.insert(0, 'src')
from PyQt5.QtWidgets import (QApplication, QLineEdit, QLabel, QPushButton,
                             QComboBox, QCheckBox, QRadioButton, QGroupBox, QTextEdit)
from PyQt5.QtGui import QFontDatabase, QFont

app = QApplication([])
from config import ASSETS_DIR
for n in ("IBMPlexSans-Regular.ttf","IBMPlexSans-Medium.ttf","IBMPlexSans-SemiBold.ttf",
          "IBMPlexSans-Bold.ttf","JetBrainsMono-Regular.ttf","UbuntuMono.ttf","Ubuntu.ttf"):
    p = ASSETS_DIR/"fonts"/n
    if p.exists(): QFontDatabase.addApplicationFont(str(p))
import gui.theme as theme
app.setFont(QFont(theme.ui_family(), 10))

import gui.dialogs as D
import gui.search_dialog as SD
import gui.main_window as MW

# Widżety, w których tekst REALNIE ginie, gdy zabraknie miejsca.
# ⚠️ QTextEdit świadomie POMINIĘTY (2026-07-25): jego `sizeHint()` to stała
# 256x192 NIEZALEŻNIE od treści (zmierzone dla 0, 1 i 50 linii), więc porównanie
# z nią nie mówi nic o ucinaniu — a pole tekstowe i tak się PRZEWIJA, zamiast
# gubić tekst. Zostawienie go dawało fałszywy alarm w każdym oknie z podglądem
# treści (wyszło przy oknie „Szukaj w rozmowie"). Kryterium ma pilnować rzeczy
# BEZ suwaka: etykiet, pól jednoliniowych, przycisków, list rozwijanych.
TYPES = (QLineEdit, QLabel, QPushButton, QComboBox, QCheckBox, QRadioButton)

def needed_height(w):
    """Ile pikseli widżet NAPRAWDĘ potrzebuje przy swojej obecnej szerokości.

    ⚠️ Dla etykiet z zawijaniem `sizeHint().height()` jest MYLĄCE (opisuje tekst
    w jednej linii przy innej szerokości) — właściwą miarą jest heightForWidth().
    Bez tego skan daje lawinę fałszywych alarmów."""
    if w.hasHeightForWidth() and w.width() > 0:
        return w.heightForWidth(w.width())
    return w.sizeHint().height()

def squeezed(dlg):
    bad = []
    for w in dlg.findChildren(TYPES):
        if not w.isVisible():
            continue
        need = needed_height(w)
        dh = need - w.height()
        if need > 0 and dh > 0:
            txt = (w.text()[:30] if hasattr(w, 'text') else '')
            bad.append(('WYS', type(w).__name__, txt, w.height(), need, dh))
    return bad

class FakeUM:
    def __init__(self): pass
class FakeInfo:
    version = "1.0.99"; notes = "Testowe wydanie"; size = 1234567
    url = "https://example/x.AppImage"; sha256 = "ab"*32
    def __getattr__(self, k): return ""

def build_all():
    from core.mcp_templates import MCP_TEMPLATES
    tpl = MCP_TEMPLATES[0]
    cases = [
        ("MemoryProjectsDialog",   lambda: D.MemoryProjectsDialog(None)),
        ("ProjectEditDialog",      lambda: D.ProjectEditDialog(None, project=None)),
        ("AgentConfigDialog",      lambda: D.AgentConfigDialog(None, memory_projects=[])),
        ("AgentsManagerDialog",    lambda: D.AgentsManagerDialog(None, agents=[{'name':'Agent Testowy','working_directory':'/tmp'}], memory_projects=[])),
        ("SkillsManagerDialog",    lambda: D.SkillsManagerDialog(None)),
        ("McpManagerDialog",       lambda: D.McpManagerDialog(None)),
        ("_McpTemplatePickerDialog", lambda: D._McpTemplatePickerDialog(None)),
        ("_McpTemplateConfigDialog", lambda: D._McpTemplateConfigDialog(None, tpl, 'user', False)),
        ("_McpAddManualDialog",    lambda: D._McpAddManualDialog(None, 'user', False)),
        ("_McpJsonImportDialog",   lambda: D._McpJsonImportDialog(None, 'user', False)),
        ("UpdateAvailableDialog",  lambda: D.UpdateAvailableDialog(FakeUM(), FakeInfo(), "1.0.26", None)),
        ("ClaudeSetupDialog",      lambda: D.ClaudeSetupDialog(None)),
        ("QuickActionsDialog",     lambda: MW.QuickActionsDialog(None, [{'label':'Test','text':'echo hi'}])),
        ("SkinSettingsDialog",     lambda: MW.SkinSettingsDialog(None, dict(theme.DEFAULT_SKIN) if hasattr(theme,'DEFAULT_SKIN') else {}, {})),
        ("SettingsDialog",         lambda: MW.SettingsDialog(None, "")),
        ("SearchDialog",           lambda: SD.SearchDialog("Agent Testowy", None)),
    ]
    return cases

total_bad = 0
skipped = []
for name, ctor in build_all():
    try:
        d = ctor()
    except Exception as e:
        skipped.append((name, f"{type(e).__name__}: {e}"))
        continue
    try:
        d.resize(d.sizeHint())
        d.show()
        for _ in range(6): app.processEvents()
        bad = squeezed(d)
        total_bad += len(bad)
        status = "OK " if not bad else "UCIĘTE"
        print(f"[{status}] {name:26s} {d.width():4d}x{d.height():4d}  ściśniętych: {len(bad)}")
        for b in bad[:6]:
            print(f"          └─ {b[1]:14s} '{b[2]}'  ma {b[3]}px, potrzebuje {b[4]}px (brak {b[5]}px)")
        d.close()
    except Exception as e:
        skipped.append((name, f"przy pomiarze: {type(e).__name__}: {e}"))

print("\n--- POMINIĘTE (nie dało się zbudować bez pełnego okna głównego) ---")
for n, why in skipped:
    print(f"  {n}: {why}")
print(f"\nRAZEM ściśniętych widżetów: {total_bad}")
