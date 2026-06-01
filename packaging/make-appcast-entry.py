#!/usr/bin/env python3
"""
Generator wpisu do appcast.json (Etap M4 — domyka pętlę auto-aktualizacji z M3).

Liczy sha256 i rozmiar zbudowanej paczki, składa wpis dla danej platformy i
albo wypisuje gotowy JSON, albo wstawia/aktualizuje wpis w istniejącym
appcast.json. Opcjonalnie dokłada podpis Ed25519 (gdy podasz klucz prywatny i
masz zainstalowane `cryptography`).

Format odpowiada packaging/appcast.example.json oraz core/update_manager.py.

Przykłady:
  # tylko wypisz wpis na ekran
  python3 packaging/make-appcast-entry.py \
      dist/ClaudeVoiceAssistant-1.0.0-macos-arm64.dmg \
      --version 1.0.0 --base-url https://srv1251441.hstgr.cloud/cva/

  # wstaw/zaktualizuj wpis w pliku appcast.json
  python3 packaging/make-appcast-entry.py \
      dist/ClaudeVoiceAssistant-1.0.0-macos-arm64.dmg \
      --version 1.0.0 --base-url https://srv1251441.hstgr.cloud/cva/ \
      --appcast packaging/appcast.json --merge

  # z podpisem (opcjonalnie)
  ... --sign-key packaging/update_private.key
"""
import argparse
import base64
import hashlib
import json
import os
import sys

KNOWN_PLATFORMS = ("macos-arm64", "macos-x64", "linux-x64", "windows-x64")


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def guess_platform(filename: str):
    for pid in KNOWN_PLATFORMS:
        if pid in filename:
            return pid
    return None


def sign_file(path: str, key_path: str) -> str:
    """Podpis Ed25519 bajtów pliku → base64. Klucz: surowe 32 B albo base64.
    Brak `cryptography`/klucza → pusty podpis (z ostrzeżeniem)."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        raw = open(key_path, "rb").read()
        key = (Ed25519PrivateKey.from_private_bytes(raw) if len(raw) == 32
               else Ed25519PrivateKey.from_private_bytes(base64.b64decode(raw.strip())))
        return base64.b64encode(key.sign(open(path, "rb").read())).decode()
    except Exception as e:  # noqa: BLE001
        print(f"OSTRZEŻENIE: podpis pominięty ({e})", file=sys.stderr)
        return ""


def main():
    ap = argparse.ArgumentParser(description="Generator wpisu appcast.json")
    ap.add_argument("artifact", help="ścieżka do zbudowanej paczki (.dmg/.exe/.tar.gz)")
    ap.add_argument("--version", required=True, help="wersja, np. 1.0.0")
    ap.add_argument("--base-url", required=True,
                    help="URL katalogu z paczkami (z / na końcu lub bez)")
    ap.add_argument("--platform", default=None,
                    help=f"wymuś platformę {KNOWN_PLATFORMS} (domyślnie z nazwy pliku)")
    ap.add_argument("--notes-url", default="")
    ap.add_argument("--mandatory", action="store_true")
    ap.add_argument("--sign-key", default=None, help="klucz prywatny Ed25519 (opcjonalnie)")
    ap.add_argument("--appcast", default=None, help="appcast.json do aktualizacji")
    ap.add_argument("--merge", action="store_true",
                    help="z --appcast: wstaw/zaktualizuj wpis dla platformy")
    args = ap.parse_args()

    if not os.path.isfile(args.artifact):
        ap.error(f"Nie ma pliku: {args.artifact}")

    fname = os.path.basename(args.artifact)
    platform_id = args.platform or guess_platform(fname)
    if not platform_id:
        ap.error("Nie rozpoznano platformy z nazwy pliku — podaj --platform")

    size = os.path.getsize(args.artifact)
    digest = sha256_of(args.artifact)
    signature = sign_file(args.artifact, args.sign_key) if args.sign_key else ""
    url = args.base_url.rstrip("/") + "/" + fname

    entry = {"url": url, "size": size, "sha256": digest, "signature": signature}

    if args.appcast and args.merge:
        data = {}
        if os.path.exists(args.appcast):
            with open(args.appcast, encoding="utf-8") as f:
                data = json.load(f)
        latest = data.setdefault("latest", {})
        latest["version"] = args.version
        latest.setdefault("notes_url", args.notes_url)
        latest["mandatory"] = bool(args.mandatory)
        latest.setdefault("platforms", {})[platform_id] = entry
        with open(args.appcast, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Zaktualizowano {args.appcast}: {platform_id} -> {fname} "
              f"({size} B, sha256={digest[:12]}…)")
    else:
        block = {"latest": {"version": args.version, "notes_url": args.notes_url,
                            "mandatory": bool(args.mandatory),
                            "platforms": {platform_id: entry}}}
        print(json.dumps(block, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
