#!/bin/bash
# Build macOS .app + .dmg dla Vibe Coding Assistant (Etap M4).
#
# URUCHAMIAĆ NA macOS (Apple Silicon lub Intel). Z Linuksa NIE zbuduje się .app.
# Krok podpisu/notaryzacji jest opcjonalny i sterowany przez ../signing.conf
# (gdy go brak lub MACOS_SIGN=false → build niepodpisany; działa, ale przy
# pierwszym uruchomieniu: prawy klik na aplikacji → „Otwórz").
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
SRC_DIR="$PROJECT_DIR/src"
DIST_DIR="$PROJECT_DIR/dist"
BUILD_DIR="$PROJECT_DIR/build"
SPEC="$SCRIPT_DIR/ClaudeVoiceAssistant.spec"
ENTITLEMENTS="$SCRIPT_DIR/entitlements.plist"
SIGNING_CONF="$SCRIPT_DIR/../signing.conf"

APP_NAME="Vibe Coding Assistant"
APP_VERSION="$(grep -E '^APP_VERSION' "$SRC_DIR/config.py" | head -1 | sed -E 's/.*["'"'"']([^"'"'"']+)["'"'"'].*/\1/')"
ARCH="$(uname -m)"
case "$ARCH" in
  arm64)  PLATFORM_ID="macos-arm64" ;;
  x86_64) PLATFORM_ID="macos-x64" ;;
  *)      PLATFORM_ID="macos-$ARCH" ;;
esac

echo "=========================================="
echo "Build: $APP_NAME v$APP_VERSION  ($PLATFORM_ID)"
echo "=========================================="

if [[ "$(uname)" != "Darwin" ]]; then
  echo "BŁĄD: ten skrypt buduje TYLKO na macOS (uname=$(uname))."
  exit 1
fi

# 1) Środowisko + zależności
# Wybierz Pythona — preferuj 3.12 (cel projektu), w razie czego inny 3.x.
PY=""
for c in python3.12 python3.13 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [[ -z "$PY" ]]; then
  echo "BŁĄD: nie znaleziono Pythona. Zainstaluj Python 3.12 z python.org."
  exit 1
fi
echo "== Python: $PY ($($PY --version 2>&1)) =="
if [[ ! -d "$PROJECT_DIR/venv" ]]; then
  echo "== Tworzę venv =="
  "$PY" -m venv "$PROJECT_DIR/venv"
fi
# shellcheck disable=SC1091
source "$PROJECT_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$PROJECT_DIR/requirements.txt"
pip install pyinstaller

# 2) Ikona PNG -> ICNS (jeśli jeszcze nie istnieje)
ICON_PNG="$SRC_DIR/assets/icon.png"
ICON_ICNS="$SRC_DIR/assets/icon.icns"
if [[ -f "$ICON_PNG" && ! -f "$ICON_ICNS" ]]; then
  echo "== Konwersja ikony PNG -> ICNS =="
  TMP_ICONSET="$(mktemp -d)/icon.iconset"
  mkdir -p "$TMP_ICONSET"
  for s in 16 32 64 128 256 512; do
    sips -z "$s" "$s"   "$ICON_PNG" --out "$TMP_ICONSET/icon_${s}x${s}.png"    >/dev/null
    d=$((s * 2))
    sips -z "$d" "$d"   "$ICON_PNG" --out "$TMP_ICONSET/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$TMP_ICONSET" -o "$ICON_ICNS"
fi

# 3) Czysty build
echo "== PyInstaller =="
rm -rf "$BUILD_DIR" "$DIST_DIR"
pyinstaller --noconfirm --clean "$SPEC"

APP_PATH="$DIST_DIR/$APP_NAME.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "BŁĄD: nie powstał $APP_PATH"
  exit 1
fi
echo "== Zbudowano: $APP_PATH =="

# 4) Opcjonalny podpis (hardened runtime) — wg ../signing.conf
if [[ -f "$SIGNING_CONF" ]]; then
  # shellcheck disable=SC1090
  source "$SIGNING_CONF"
fi
if [[ "${MACOS_SIGN:-false}" == "true" && -n "${MACOS_DEVELOPER_ID:-}" ]]; then
  echo "== Podpisywanie (hardened runtime) =="
  codesign --deep --force --options runtime \
    --entitlements "$ENTITLEMENTS" \
    --sign "$MACOS_DEVELOPER_ID" "$APP_PATH"
  codesign --verify --deep --strict --verbose=2 "$APP_PATH"
else
  echo "== Build NIEPODPISANY (pierwsze uruchomienie: prawy klik -> Otwórz) =="
fi

# 5) DMG (z aliasem do /Applications, by przeciągnąć ikonę) — dla NOWYCH instalacji
DMG="$DIST_DIR/VibeCodingAssistant-$APP_VERSION-$PLATFORM_ID.dmg"
echo "== Tworzenie DMG =="
STAGING="$(mktemp -d)/dmg"
mkdir -p "$STAGING"
cp -R "$APP_PATH" "$STAGING/"
ln -s /Applications "$STAGING/Applications"
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGING" -ov -format UDZO "$DMG"

# 5b) ZIP pakietu .app — dla SAMO-AKTUALIZACJI w aplikacji (Etap 2)
# .dmg nie nadaje się do podmiany w miejscu; updater rozpakowuje .zip przez
# `ditto -x -k`. `ditto -c -k --keepParent` zachowuje symlinki/uprawnienia i
# trzyma pakiet „Foo.app" jako katalog nadrzędny w archiwum (tak jak Sparkle).
ZIP="$DIST_DIR/VibeCodingAssistant-$APP_VERSION-$PLATFORM_ID.zip"
echo "== Tworzenie ZIP (samo-aktualizacja) =="
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP"

# 6) Notaryzacja DMG (tylko gdy podpis włączony)
if [[ "${MACOS_SIGN:-false}" == "true" && -n "${MACOS_NOTARY_PROFILE:-}" ]]; then
  echo "== Notaryzacja DMG =="
  xcrun notarytool submit "$DMG" --keychain-profile "$MACOS_NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG"
fi

echo ""
echo "=========================================="
echo "GOTOWE"
echo "  App: $APP_PATH"
echo "  DMG: $DMG   (nowe instalacje — strona pobierania)"
echo "  ZIP: $ZIP   (samo-aktualizacja w aplikacji)"
echo "=========================================="
echo ""
echo "Wpis do appcast.json generuj z PACZKI ZIP (to jej używa samo-aktualizacja):"
echo "  python3 \"$PROJECT_DIR/packaging/make-appcast-entry.py\" \\"
echo "    \"$ZIP\" --version $APP_VERSION \\"
echo "    --base-url https://srv1251441.hstgr.cloud/cva/ \\"
echo "    --appcast \"$PROJECT_DIR/packaging/appcast.json\" --merge"
echo ""
echo "Wgraj na serwer OBA pliki (.zip do samo-aktualizacji, .dmg na stronę):"
echo "  scp \"$ZIP\" \"$DMG\" root@168.231.127.133:/opt/cva-web/html/cva/"
