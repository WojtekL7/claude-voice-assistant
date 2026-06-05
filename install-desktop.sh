#!/bin/bash
# Install Claude Voice Assistant desktop entry for Ubuntu/GNOME

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_FILE="$HOME/.local/share/applications/claude-voice-assistant.desktop"

# Create applications directory if not exists
mkdir -p "$HOME/.local/share/applications"

# Create desktop entry
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Claude Voice Assistant
GenericName=Voice Assistant
Comment=Voice interaction with Claude Code CLI
# Uruchamiamy przez run-safe.sh (cgroup z limitem RAM), a NIE bezpośrednio
# przez python — bez limitu kilku agentów potrafiło wyczerpać pamięć i
# zamrozić cały pulpit GNOME. run-safe.sh izoluje apkę, więc OOM-killer
# ubije tylko ją, a nie system.
Exec=$SCRIPT_DIR/run-safe.sh
Icon=$SCRIPT_DIR/src/assets/icon.png
Terminal=false
Categories=Utility;Development;
Keywords=voice;assistant;claude;ai;speech;
StartupNotify=true
StartupWMClass=claude-voice-assistant
EOF

chmod +x "$DESKTOP_FILE"

# Update desktop database
update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true

echo "Claude Voice Assistant installed!"
echo "You can now find it in 'Show Applications' menu."
