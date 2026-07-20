#!/usr/bin/env python3
"""Retencja kanału aktualizacji na VPS — kasuje stare paczki, chroni potrzebne.

Powód powstania: `/opt/cva-web` urósł do 11 GB i wypchnął VPS do 93% zajętego dysku,
zagrażając WSZYSTKIM aplikacjom na tej maszynie (bazy, poczta, WordPress). Sprzątanie
ręczne załatwia dziś, automat załatwia na zawsze. (Zgłoszenie: agent SEO Managera,
2026-07-20.)

DOMYŚLNIE PRÓBA NA SUCHO — kasuje dopiero z `--apply`.

Trzy zasady, każda okupiona osobną rundą analizy — nie upraszczaj ich:

1. **Chroń po MANIFEŚCIE, nie po dacie.** Lista nietykalnych powstaje z plików, które
   NA PACZKI WSKAZUJĄ (`appcast.json` + strony `*.html`). Kasowanie „po dacie" prędzej
   czy później usunie plik, do którego ktoś się odwołuje.
2. **„N najnowszych" licz W GRUPIE aplikacja+platforma.** Globalnie skasowałoby JEDYNY
   instalator Windows (`.exe` bywa starszy niż kilka `.AppImage`) → użytkownicy Windows
   zostają bez pobrania.
3. **Weryfikuj pod adresem `https://pobierz.srv1251441.hstgr.cloud/cva/`.** Adres
   `srv1251441.hstgr.cloud/cva/` jest NIEAKTUALNY (brak trasy w Traefiku → 404 +
   certyfikat zastępczy), co przy diagnozie wygląda jak „skasowałem za dużo".

Użycie na VPS::

    python3 prune-release-channel.py                 # próba na sucho
    python3 prune-release-channel.py --apply         # realne kasowanie
    python3 prune-release-channel.py --keep 5 --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CHANNEL_DIR = Path("/opt/cva-web/html/cva")
HTML_DIRS = [Path("/opt/cva-web/html")]
APPCAST = CHANNEL_DIR / "appcast.json"
PACKAGE_SUFFIXES = (".AppImage", ".exe", ".dmg", ".zip")

# Kopie i wersje uszkodzone — do skasowania niezależnie od retencji.
JUNK_RE = re.compile(r"(\.bak\b|\.bak-|broken)", re.IGNORECASE)
VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def platform_of(name: str) -> str:
    """Grupa platformy — po rozszerzeniu, bo nazwy plików bywają niespójne."""
    low = name.lower()
    if low.endswith(".exe"):
        return "windows"
    if low.endswith(".appimage"):
        return "linux"
    if low.endswith(".dmg"):
        return "macos-dmg"      # .dmg i .zip to OSOBNE grupy: .zip niesie
    if low.endswith(".zip"):
        return "macos-zip"      # self-update, .dmg jest do ręcznej instalacji
    return "inne"


def app_of(name: str) -> str:
    """Nazwa aplikacji (przed wersją). Po rebrandingu istnieją DWIE naraz."""
    return VERSION_RE.split(name, maxsplit=1)[0].rstrip("-").replace("-Setup", "")


def version_of(name: str):
    m = VERSION_RE.search(name)
    return tuple(int(g) for g in m.groups()) if m else (0, 0, 0)


def protected_names() -> set[str]:
    """Pliki, na które ktokolwiek WSKAZUJE — nietykalne (zasada 1)."""
    keep: set[str] = set()
    try:
        feed = json.loads(APPCAST.read_text(encoding="utf-8"))
        for entry in feed.get("latest", {}).get("platforms", {}).values():
            url = entry.get("url", "")
            if url:
                keep.add(url.rsplit("/", 1)[-1])
    except (OSError, ValueError) as exc:
        # Nie zgadujemy: bez manifestu nie wiemy, co jest w użyciu.
        sys.exit(f"BŁĄD: nie mogę odczytać {APPCAST} ({exc}) — przerywam dla bezpieczeństwa.")

    for d in HTML_DIRS:
        for html in d.rglob("*.html"):
            try:
                text = html.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for f in CHANNEL_DIR.iterdir():
                if f.name in text:
                    keep.add(f.name)
    return keep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="realnie kasuj (domyślnie próba na sucho)")
    ap.add_argument("--keep", type=int, default=3, help="ile najnowszych zostawić w KAŻDEJ grupie")
    ap.add_argument("--drop-app", action="append", default=[], metavar="NAZWA",
                    help="skasuj WSZYSTKIE paczki tej aplikacji (np. porzucona nazwa sprzed "
                         "rebrandingu). Pliki chronione przez manifest i tak zostają.")
    args = ap.parse_args()

    if not CHANNEL_DIR.is_dir():
        sys.exit(f"BŁĄD: brak katalogu {CHANNEL_DIR}")

    protected = protected_names()
    packages = [f for f in CHANNEL_DIR.iterdir()
                if f.is_file() and f.name.endswith(PACKAGE_SUFFIXES)]

    groups: dict[tuple[str, str], list[Path]] = {}
    junk: list[Path] = []
    for f in packages:
        (junk if JUNK_RE.search(f.name) else
         groups.setdefault((app_of(f.name), platform_of(f.name)), [])).append(f)

    to_delete: list[Path] = [f for f in junk if f.name not in protected]
    print(f"Chronione przez manifest/strony ({len(protected)}): {sorted(protected)}\n")
    print(f"Grupy aplikacja+platforma (zostawiam {args.keep} najnowszych w każdej):")
    for key in sorted(groups):
        files = sorted(groups[key], key=lambda p: version_of(p.name), reverse=True)
        if key[0] in args.drop_app:
            # Porzucona nazwa aplikacji — kasujemy CAŁĄ grupę. Ochrona z manifestu
            # nadal obowiązuje (gdyby feed wciąż na coś tu wskazywał).
            keep, drop = [], [f for f in files if f.name not in protected]
            print(f"  {key[0]:24} {key[1]:10} razem {len(files):2}  "
                  f"PORZUCONA NAZWA → kasuję wszystkie ({len(drop)})")
            to_delete.extend(drop)
            continue
        keep, drop = files[:args.keep], files[args.keep:]
        drop = [f for f in drop if f.name not in protected]
        print(f"  {key[0]:24} {key[1]:10} razem {len(files):2}  "
              f"zostaje {[p.name.split('-')[-2] if '-' in p.name else p.name for p in keep]}")
        to_delete.extend(drop)

    if junk:
        print(f"\nKopie/uszkodzone do skasowania: {[f.name for f in junk]}")

    total = sum(f.stat().st_size for f in to_delete)
    print(f"\n{'KASUJĘ' if args.apply else 'PRÓBA NA SUCHO — skasowałbym'}: "
          f"{len(to_delete)} plików, {total / 1e9:.2f} GB")
    for f in sorted(to_delete):
        print(f"   - {f.name} ({f.stat().st_size / 1e6:.0f} MB)")

    if not to_delete:
        print("Nic do sprzątania.")
        return 0
    if not args.apply:
        print("\nUruchom z --apply, żeby skasować.")
        return 0

    freed = 0
    for f in to_delete:
        try:
            size = f.stat().st_size
            f.unlink()
            freed += size
        except OSError as exc:
            print(f"   ! nie udało się skasować {f.name}: {exc}")
    print(f"\nOdzyskane: {freed / 1e9:.2f} GB")
    print("SPRAWDŹ TERAZ kanał: curl -sI https://pobierz.srv1251441.hstgr.cloud/cva/appcast.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
