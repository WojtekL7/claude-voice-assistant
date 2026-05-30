#!/bin/bash
# Build script for Claude Voice Assistant (Linux)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
BUILD_DIR="$PROJECT_DIR/dist"
SRC_DIR="$PROJECT_DIR/src"

APP_NAME="Claude Voice Assistant"
APP_VERSION="1.0.0"

echo "=========================================="
echo "Building $APP_NAME v$APP_VERSION for Linux"
echo "=========================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required"
    exit 1
fi

# Create virtual environment if not exists
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/venv"
fi

# Activate virtual environment
source "$PROJECT_DIR/venv/bin/activate"

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r "$PROJECT_DIR/requirements.txt"

# Install PyInstaller if not present
pip install pyinstaller

# Clean previous builds
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Build with PyInstaller
echo "Building application with PyInstaller..."
cd "$SRC_DIR"

pyinstaller --onefile \
    --windowed \
    --name "claude-voice-assistant" \
    --icon "$SRC_DIR/assets/icon.png" \
    --add-data "config.py:." \
    --add-data "assets:assets" \
    --add-data "i18n:i18n" \
    --hidden-import "PyQt5.QtCore" \
    --hidden-import "PyQt5.QtWidgets" \
    --hidden-import "PyQt5.QtGui" \
    --hidden-import "edge_tts" \
    --hidden-import "pygame" \
    --hidden-import "sounddevice" \
    --hidden-import "numpy" \
    --hidden-import "scipy" \
    --hidden-import "requests" \
    --distpath "$BUILD_DIR" \
    --workpath "$BUILD_DIR/build" \
    --specpath "$BUILD_DIR" \
    main.py

# Create AppImage
echo "Creating AppImage..."
cd "$BUILD_DIR"

# Create AppDir structure
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps

# Copy binary
cp claude-voice-assistant AppDir/usr/bin/

# Create desktop file
cat > AppDir/usr/share/applications/claude-voice-assistant.desktop << EOF
[Desktop Entry]
Name=Claude Voice Assistant
Comment=Voice assistant for Claude Code
Exec=claude-voice-assistant
Icon=claude-voice-assistant
Terminal=false
Type=Application
Categories=Development;Utility;
EOF

# Copy icon (create placeholder if not exists)
if [ -f "$SRC_DIR/assets/icon.png" ]; then
    cp "$SRC_DIR/assets/icon.png" AppDir/usr/share/icons/hicolor/256x256/apps/claude-voice-assistant.png
else
    # Create simple placeholder icon
    echo "Warning: icon.png not found, skipping icon..."
fi

# Create AppRun
cat > AppDir/AppRun << 'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin/:${PATH}"
exec "${HERE}/usr/bin/claude-voice-assistant" "$@"
EOF
chmod +x AppDir/AppRun

# Download appimagetool if not present
if [ ! -f appimagetool-x86_64.AppImage ]; then
    echo "Downloading appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x appimagetool-x86_64.AppImage
fi

# Build AppImage
./appimagetool-x86_64.AppImage AppDir "Claude_Voice_Assistant-${APP_VERSION}-x86_64.AppImage"

echo ""
echo "=========================================="
echo "Build complete!"
echo "=========================================="
echo "Output files:"
echo "  - $BUILD_DIR/claude-voice-assistant (binary)"
echo "  - $BUILD_DIR/Claude_Voice_Assistant-${APP_VERSION}-x86_64.AppImage"
echo ""
