#!/bin/bash
# Build Linux AppImage dla Claude Voice Assistant.
#
# URUCHAMIAĆ NA Linuksie x86_64. Produkuje jeden przenośny plik .AppImage
# (użytkownik: chmod +x i klik — bez instalacji). Terminalem w paczce jest
# WebTerminal (xterm.js + QtWebEngine); QTermWidget jest wykluczony ze .spec.
#
# Zmienne sterujące:
#   CVA_SKIP_DEPS=1   — pomiń instalację zależności (gdy venv już gotowy; do testów lokalnych)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
SRC_DIR="$PROJECT_DIR/src"
DIST_DIR="$PROJECT_DIR/dist"
BUILD_DIR="$PROJECT_DIR/build"
SPEC="$SCRIPT_DIR/ClaudeVoiceAssistant.spec"

APP_NAME="Claude Voice Assistant"
APP_BIN="claude-voice-assistant"
APP_VERSION="$(grep -E '^APP_VERSION' "$SRC_DIR/config.py" | head -1 | sed -E 's/.*["'"'"']([^"'"'"']+)["'"'"'].*/\1/')"
PLATFORM_ID="linux-x64"
APPIMAGE="$DIST_DIR/ClaudeVoiceAssistant-$APP_VERSION-$PLATFORM_ID.AppImage"

echo "=========================================="
echo "Build: $APP_NAME v$APP_VERSION  ($PLATFORM_ID)"
echo "=========================================="

if [[ "$(uname)" != "Linux" ]]; then
  echo "BŁĄD: ten skrypt buduje TYLKO na Linuksie (uname=$(uname))."
  exit 1
fi

# 1) Środowisko + zależności
PY=""
for c in python3.12 python3.13 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [[ -z "$PY" ]]; then
  echo "BŁĄD: nie znaleziono Pythona 3.x."
  exit 1
fi
echo "== Python: $PY ($($PY --version 2>&1)) =="
if [[ ! -d "$PROJECT_DIR/venv" ]]; then
  echo "== Tworzę venv =="
  "$PY" -m venv "$PROJECT_DIR/venv"
fi
# shellcheck disable=SC1091
source "$PROJECT_DIR/venv/bin/activate"
if [[ "${CVA_SKIP_DEPS:-0}" != "1" ]]; then
  pip install --upgrade pip
  pip install -r "$PROJECT_DIR/requirements.txt"
  pip install pyinstaller
else
  echo "== Pomijam instalację zależności (CVA_SKIP_DEPS=1) =="
  command -v pyinstaller >/dev/null 2>&1 || pip install pyinstaller
fi

# 2) Czysty build (onedir)
echo "== PyInstaller =="
rm -rf "$BUILD_DIR" "$DIST_DIR"
pyinstaller --noconfirm --clean "$SPEC"

ONEDIR="$DIST_DIR/$APP_BIN"
if [[ ! -x "$ONEDIR/$APP_BIN" ]]; then
  echo "BŁĄD: nie powstał $ONEDIR/$APP_BIN"
  exit 1
fi
echo "== Zbudowano onedir: $ONEDIR =="

# 3) Złóż AppDir
echo "== Składanie AppDir =="
APPDIR="$DIST_DIR/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
# Cała paczka PyInstallera (binarka + _internal) ląduje w usr/bin — binarka
# znajduje _internal obok siebie.
cp -a "$ONEDIR/." "$APPDIR/usr/bin/"

# 3a) Ikona (na korzeniu AppDir + .DirIcon — wymóg AppImage)
ICON_SRC="$SRC_DIR/assets/icon.png"
if [[ -f "$ICON_SRC" ]]; then
  cp "$ICON_SRC" "$APPDIR/$APP_BIN.png"
  cp "$ICON_SRC" "$APPDIR/.DirIcon"
  mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
  cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_BIN.png"
else
  echo "OSTRZEŻENIE: brak $ICON_SRC — AppImage bez ikony."
fi

# 3b) Plik .desktop (na korzeniu AppDir + w usr/share/applications)
DESKTOP_CONTENT="[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=Asystent głosowy dla Claude Code
Exec=$APP_BIN
Icon=$APP_BIN
Categories=Development;Utility;
Terminal=false
"
mkdir -p "$APPDIR/usr/share/applications"
printf '%s' "$DESKTOP_CONTENT" > "$APPDIR/usr/share/applications/$APP_BIN.desktop"
printf '%s' "$DESKTOP_CONTENT" > "$APPDIR/$APP_BIN.desktop"

# 3c) AppRun — uruchamia binarkę z usr/bin
# QTWEBENGINE_DISABLE_SANDBOX: sandbox Chromium nie współpracuje z układem
# katalogów AppImage/PyInstallera (jak na Windows w 1.0.13). Wyświetlamy WYŁĄCZNIE
# lokalny terminal.html (zero treści z sieci), więc wyłączenie sandboxa jest tu
# bezpieczne i konieczne, by WebTerminal w ogóle wstał.
cat > "$APPDIR/AppRun" << 'APPRUN_EOF'
#!/bin/bash
SELF="$(readlink -f "$0")"
HERE="${SELF%/*}"
# CVA_WEBTERMINAL=1: w AppImage NIE pakujemy QTermWidgetu, więc terminalem jest
# WebTerminal (xterm.js + QtWebEngine) — jak na macOS/Windows. Ta flaga sprawia,
# że main.py ustawi Qt.AA_ShareOpenGLContexts i zaimportuje QtWebEngineWidgets
# PRZED QApplication (twardy wymóg QtWebEngine). Bez niej WebTerminal nie wstaje.
export CVA_WEBTERMINAL=1
# Sandbox Chromium nie współpracuje z układem katalogów AppImage/PyInstallera
# (jak na Windows w 1.0.13). Wyświetlamy tylko lokalny terminal.html (zero treści
# z sieci), więc wyłączenie sandboxa jest tu bezpieczne i konieczne.
export QTWEBENGINE_DISABLE_SANDBOX=1
exec "$HERE/usr/bin/claude-voice-assistant" "$@"
APPRUN_EOF
chmod +x "$APPDIR/AppRun"

# 4) appimagetool → AppImage
echo "== appimagetool =="
TOOL="$DIST_DIR/appimagetool-x86_64.AppImage"
if [[ ! -f "$TOOL" ]]; then
  echo "== Pobieram appimagetool =="
  curl -fsSL -o "$TOOL" \
    "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
  chmod +x "$TOOL"
fi

# --appimage-extract-and-run: działa też bez FUSE (kontener/CI).
echo "== Tworzenie AppImage =="
( cd "$DIST_DIR" && APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 \
    "$TOOL" --appimage-extract-and-run "$APPDIR" "$APPIMAGE" )

echo ""
echo "=========================================="
echo "GOTOWE"
echo "  AppImage: $APPIMAGE"
echo "=========================================="
echo ""
echo "Test lokalny:  chmod +x \"$APPIMAGE\" && \"$APPIMAGE\""
echo ""
echo "Wpis do appcast.json:"
echo "  python3 \"$PROJECT_DIR/packaging/make-appcast-entry.py\" \\"
echo "    \"$APPIMAGE\" --version $APP_VERSION --platform linux-x64 \\"
echo "    --base-url https://pobierz.srv1251441.hstgr.cloud/cva/ \\"
echo "    --appcast \"$PROJECT_DIR/packaging/appcast.json\" --merge"
