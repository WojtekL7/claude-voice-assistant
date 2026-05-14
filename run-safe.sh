#!/bin/bash
# Claude Voice Assistant — uruchomienie z limitem pamięci (ochrona systemu)
#
# Dlaczego:
#   System (Ubuntu 24.04, Lenovo Z51-70, 7.7 GB RAM, Intel HD 5500) zawieszał
#   się hard wraz z Voice Assistant + Chrome + Claude CLI (łącznie >5 GB).
#   Memory pressure → Mutter (kompozytor) zalewany → freeze całego desktopu.
#
# Ten skrypt uruchamia apkę w izolowanym cgroup z limitem 2 GB RAM:
#   - Jeśli apka zacznie ciec lub żreć pamięć — OOM-killer zabije TYLKO ją,
#     a NIE zamrozi systemu.
#   - Bez limitu OOM-killer wybiera losowo, czasem celuje w gnome-shell.
#
# Użycie:
#   ./run-safe.sh                  # X11/XWayland (domyślny, stabilny)
#   VOICE_USE_WAYLAND=1 ./run-safe.sh   # natywny Wayland (test)

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# Aktywacja venv (jeśli istnieje)
if [ -f venv/bin/activate ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

# Limit pamięci 2 GB. systemd-run --user --scope tworzy efemeryczny cgroup
# pod systemd usera. MemoryMax=2G to hard limit (OOM-killer zabije apkę
# zanim pamięć systemu się skończy).
# CPUQuota=300% pozwala użyć do 3 z 4 rdzeni (zostaw 1 dla GNOME shell).
#
# setsid: aplikacja startuje w NOWEJ sesji procesów, bez controlling TTY.
# Skutek: zamknięcie okna terminala NIE wysyła SIGHUP do aplikacji, więc
# aplikacja przeżywa zamknięcie terminala (jak normalna apka GUI). Bez tego
# aplikacja jest dzieckiem bash i ginie razem z terminalem (cały stan
# QTermWidget / sesje Claude Code w zakładkach przepadają).
exec systemd-run \
    --user \
    --scope \
    --unit="claude-voice-assistant-$$" \
    -p MemoryMax=2G \
    -p MemorySwapMax=1G \
    -p CPUQuota=300% \
    setsid python3 src/main.py "$@"
