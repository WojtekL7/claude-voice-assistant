#!/usr/bin/env python3
"""Test odsłuchowy: czy trzeszczenie lektora robi APLIKACJA, czy SYSTEM.

Uruchom:  python3 tools/diagnoza-trzeszczenia-tts.py

Odtwarza TO SAMO zdanie cztery razy, za każdym razem inaczej. Wystarczy słuchać
i zapamiętać, które próbki trzeszczą:

  1. tak jak dziś robi to apka   (pygame, bufor 512 — wartość domyślna)
  2. apka z większym buforem     (pygame, bufor 2048)
  3. apka bez przepróbkowania    (24 kHz mono — dokładnie to, co daje edge-tts)
  4. odtwarzacz systemowy        (ffplay — całkiem poza naszą aplikacją)

JAK CZYTAĆ WYNIK:
  • trzeszczy TYLKO 1  → wina naszego kodu (za mały bufor) — naprawialne u nas
  • 1 i 2 trzeszczą, 3 czysta → przepróbkowanie 24→44 kHz
  • trzeszczą WSZYSTKIE, łącznie z 4 → wina systemu (PipeWire/jądro/sterownik),
    nie aplikacji — poprawka idzie poza kod apki
  • żadna nie trzeszczy → objaw jest przerywany; powtórz przy obciążonym
    komputerze (kilka pracujących zakładek)
"""

import asyncio
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

ZDANIE = ("To jest próbka głosu lektora. Sprawdzamy, czy w tle słychać "
          "trzeszczenie, przydźwięk albo trzaski. Zdanie jest celowo długie, "
          "żeby dało się tego posłuchać przez dłuższą chwilę.")


def glos() -> str:
    """Ten sam głos, którego używa aplikacja (z jej konfiguracji)."""
    try:
        import config
        v = getattr(config, "TTS_VOICE", None) or getattr(config, "DEFAULT_TTS_VOICE", None)
        if isinstance(v, str) and v:
            return v
        choices = getattr(config, "TTS_VOICE_CHOICES", None)
        if choices:
            for vid, _label in choices:
                if str(vid).startswith("pl-"):
                    return vid
    except Exception:
        pass
    return "pl-PL-MarekNeural"


async def _syntezuj(tekst: str, plik: str, voice: str) -> None:
    import edge_tts
    await edge_tts.Communicate(tekst, voice).save(plik)


def odtworz_pygame(plik: str, opis: str, **init_kwargs) -> None:
    import pygame
    print(f"\n▶  {opis}")
    print("   (słuchaj...)", flush=True)
    try:
        pygame.mixer.quit()
    except Exception:
        pass
    pygame.mixer.init(**init_kwargs)
    got = pygame.mixer.get_init()
    print(f"   mikser: {got[0]} Hz, kanały: {got[2]}, bufor: {init_kwargs.get('buffer', 'domyślny')}")
    pygame.mixer.music.load(plik)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    pygame.mixer.quit()


def main() -> int:
    voice = glos()
    print("=" * 62)
    print("  TEST TRZESZCZENIA LEKTORA — cztery próbki tego samego zdania")
    print("=" * 62)
    print(f"  głos: {voice}")
    print("  Podkręć głośność do normalnego poziomu słuchania.\n")

    tmp = Path(tempfile.mkdtemp(prefix="tts-trzeszczenie-"))
    plik = str(tmp / "probka.mp3")
    print("Pobieram próbkę głosu...", flush=True)
    try:
        asyncio.run(_syntezuj(ZDANIE, plik, voice))
    except Exception as e:
        print(f"BŁĄD: nie udało się pobrać próbki ({e})")
        print("Sprawdź internet — edge-tts pobiera głos z sieci.")
        return 1
    rozmiar = os.path.getsize(plik)
    print(f"Gotowe ({rozmiar/1024:.0f} KB).")

    odtworz_pygame(plik, "PRÓBKA 1/4 — tak jak dziś robi to apka (bufor 512)")
    time.sleep(1.0)
    odtworz_pygame(plik, "PRÓBKA 2/4 — apka z większym buforem (2048)", buffer=2048)
    time.sleep(1.0)
    odtworz_pygame(plik, "PRÓBKA 3/4 — bez przepróbkowania (24 kHz mono, bufor 4096)",
                   frequency=24000, size=-16, channels=1, buffer=4096)
    time.sleep(1.0)

    print("\n▶  PRÓBKA 4/4 — odtwarzacz systemowy, POZA naszą aplikacją (ffplay)")
    print("   (słuchaj...)", flush=True)
    try:
        subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", plik],
                       timeout=120, check=False)
    except FileNotFoundError:
        print("   ffplay niedostępny — pomijam (ten test sprawdzał system)")
    except Exception as e:
        print(f"   nie udało się odtworzyć: {e}")

    print("\n" + "=" * 62)
    print("  KTÓRE PRÓBKI TRZESZCZAŁY? Napisz numery, np. „1 i 4”.")
    print("=" * 62)
    print("  1 = obecne ustawienia apki | 2 = większy bufor")
    print("  3 = bez przepróbkowania    | 4 = poza apką (system)")
    try:
        for f in tmp.iterdir():
            f.unlink()
        tmp.rmdir()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
