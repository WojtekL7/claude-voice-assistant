#!/bin/bash
# Claude Voice Assistant — uruchomienie z limitem pamięci (ochrona systemu)
#
# Dlaczego:
#   System (Ubuntu 24.04, Lenovo Z51-70, ~11 GB RAM, Intel HD 5500) zawieszał
#   się hard wraz z Voice Assistant + Chrome + Claude CLI. Każda AKTYWNA
#   zakładka-agent uruchamia osobny proces `claude` (Node.js) ~1.5–2 GB;
#   kilku agentów naraz wyczerpuje RAM. Memory pressure → Mutter (kompozytor)
#   zalewany → freeze całego desktopu.
#
# Ten skrypt uruchamia apkę w izolowanym cgroup z miękkim progiem 7 GB
# i twardym bezpiecznikiem 9 GB RAM:
#   - MemoryHigh=7G (miękki próg): powyżej 7 GB system zaczyna apkę zwalniać
#     (spycha do swapu), ale jej NIE zabija — daje pełen kontekst agentów luz.
#   - MemoryMax=9G (twardy bezpiecznik): dopiero przy 9 GB OOM-killer zabije
#     TYLKO apkę, a NIE zamrozi systemu. Bez limitu killer wybiera losowo,
#     czasem celuje w gnome-shell.
#   - Na poziomie całego systemu działa już zram+earlyoom, więc ten twardy
#     limit to tylko ostatnia siatka. Sama apka dodatkowo OSTRZEGA przy
#     aktywacji >3 agentów (config.MAX_ACTIVE_AGENTS).
#
# ⚠️ ZALEŻNOŚĆ: na maszynie z ~11 GB RAM twardy limit 9G zostawia mało
#   marginesu dla reszty systemu. Bezpieczny jest TYLKO dlatego, że pulpit
#   chroni systemowy earlyoom z `--avoid (gnome-shell|mutter|Xorg|Xwayland|
#   gdm3?|systemd)` + `--prefer (claude|node|chrome|...)` (sprawdź:
#   `systemctl is-active earlyoom`). Jeśli earlyoom padnie/zmieni config,
#   ten skrypt SAM 11-GB maszyny przed freezem już nie obroni — wtedy obniż
#   MemoryMax (np. do 6-7G, jak przed tą zmianą było 4G).
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

# Limit pamięci. systemd-run --user --scope tworzy efemeryczny cgroup
# pod systemd usera. MemoryHigh=7G to miękki próg (throttling do swapu),
# MemoryMax=9G to twardy limit (OOM-killer zabije apkę zanim pamięć
# systemu się skończy).
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
    -p MemoryHigh=7G \
    -p MemoryMax=9G \
    -p MemorySwapMax=2G \
    -p CPUQuota=300% \
    setsid python3 src/main.py "$@"
