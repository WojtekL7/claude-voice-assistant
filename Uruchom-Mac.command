#!/bin/bash
# Uruchom-Mac.command — dwuklik uruchamia Claude Voice Assistant na macOS.
# Przy PIERWSZYM uruchomieniu sam przygotuje środowisko (kilka minut), potem
# każde kolejne uruchomienie jest szybkie. Nie trzeba nic wpisywać.

cd "$(dirname "$0")" || exit 1

echo "======================================"
echo "   Claude Voice Assistant"
echo "======================================"

# 1) Znajdź Pythona (3.12 najlepiej; w razie czego nowszy/3.x)
PY=""
for c in python3.12 python3.13 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo ""
  echo "❌ Nie znaleziono Pythona na tym Macu."
  echo "   Zainstaluj Python 3.12 z: https://www.python.org/downloads/macos/"
  echo "   (pobierz plik .pkg, kliknij dwukrotnie, zainstaluj), potem uruchom mnie ponownie."
  echo ""
  read -r -p "Naciśnij Enter, aby zamknąć to okno."
  exit 1
fi

# 2) Pierwsze uruchomienie: środowisko + części programu
if [ ! -d "venv" ] || [ ! -f "venv/.deps-ok" ]; then
  echo ""
  echo "⏳ Pierwsze uruchomienie — przygotowuję program."
  echo "   To potrwa kilka minut i poleci dużo napisów. To normalne, poczekaj..."
  echo ""
  if [ ! -d "venv" ]; then
    "$PY" -m venv venv || { echo "❌ Błąd tworzenia środowiska."; read -r -p "Enter, aby zamknąć."; exit 1; }
  fi
  ./venv/bin/python -m pip install --upgrade pip
  if ./venv/bin/python -m pip install -r requirements.txt; then
    touch venv/.deps-ok
  else
    echo ""
    echo "❌ Nie udało się zainstalować części programu."
    echo "   Skopiuj powyższy tekst i wyślij go programiście."
    read -r -p "Naciśnij Enter, aby zamknąć."
    exit 1
  fi
fi

# 3) Uruchom aplikację
echo ""
echo "🚀 Uruchamiam Claude Voice Assistant..."
exec ./venv/bin/python src/main.py
