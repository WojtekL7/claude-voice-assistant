#!/bin/bash
# Zbuduj-DMG-Mac.command — dwuklik buduje gotowy plik instalacyjny .dmg na macOS.
# Pierwsze budowanie trwa kilka–kilkanaście minut. Nie trzeba nic wpisywać.

cd "$(dirname "$0")" || exit 1

echo "================================================"
echo "   Budowanie .dmg — Vibe Coding Assistant"
echo "================================================"
echo "To potrwa kilka–kilkanaście minut."
echo "Poleci DUŻO napisów — to normalne, poczekaj cierpliwie."
echo ""

bash packaging/macos/build-macos.sh
status=$?

echo ""
if [ "$status" -eq 0 ]; then
  echo "✅ GOTOWE! Plik .dmg znajdziesz w folderze 'dist'."
  echo "   Otwieram ten folder..."
  open dist 2>/dev/null
else
  echo "❌ Coś poszło nie tak podczas budowania."
  echo "   Skopiuj powyższy tekst (zwłaszcza końcówkę) i wyślij programiście —"
  echo "   pierwsze budowanie na nowym Macu czasem wymaga drobnej poprawki."
fi

echo ""
read -r -p "Naciśnij Enter, aby zamknąć to okno."
