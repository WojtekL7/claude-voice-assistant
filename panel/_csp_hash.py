#!/usr/bin/env python3
"""Przelicza hash CSP dla inline skryptu w panel/index.html.

Uruchom PO KAŻDEJ zmianie skryptu i podmień wartość 'sha256-…' w nagłówku
<meta http-equiv="Content-Security-Policy"> w index.html — inaczej przeglądarka
odrzuci zmieniony skrypt i panel wczyta się PUSTY.

    python3 panel/_csp_hash.py

Odporny na komentarze HTML: najpierw je usuwa (żeby dosłowne znaczniki skryptu
w komentarzu nie zafałszowały dopasowania), potem haszuje treść jedynego
prawdziwego elementu skryptu.
"""
import base64
import hashlib
import pathlib
import re
import sys

html = pathlib.Path(__file__).with_name("index.html").read_text(encoding="utf-8")
without_comments = re.sub(r"<!--.*?-->", "", html, flags=re.S)
matches = re.findall(r"<script>(.*?)</script>", without_comments, flags=re.S)
if len(matches) != 1:
    sys.exit(f"Spodziewano się 1 inline skryptu, znaleziono {len(matches)}.")
digest = hashlib.sha256(matches[0].encode("utf-8")).digest()
print("sha256-" + base64.b64encode(digest).decode())
