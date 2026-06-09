"""Generuje src/assets/icon.ico z icon.png (Windows wymaga .ico).

Wydzielone z build-windows.ps1, by uniknac nawiasow [] w skrypcie PowerShell
(czytelniej i bez ryzyka parsowania). Uruchamiane przez build-windows.ps1.
"""
from PIL import Image

SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
Image.open("src/assets/icon.png").save("src/assets/icon.ico", sizes=SIZES)
print("OK: src/assets/icon.ico")
