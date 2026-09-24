#!/usr/bin/env python3
"""Sonda WIERNOSCI poprawiania transkrypcji — czy model POPRAWIA zapis, czy
PRZEPISUJE / WYKONUJE wypowiedz.

PO CO: bezpiecznik dlugosci w `_popraw_transkrypcje` NIE lapie parafrazy
(zmierzone 2026-09-11: parafraza ma WYZSZE podobienstwo znakowe niz wierny
wynik). Chroni nas wylacznie WYBOR MODELU — a ten trzeba zmierzyc na zdaniach,
ktore brzmia jak POLECENIA, bo to one kusza model do wykonania zamiast zapisu
(kanarek AI Managera 2026-09-18: 3 z 6 modeli wykonaly polecenie).

Poprzednia taka sonda (2026-09-11) zyla w scratchpadzie i przepadla — ta
zostaje w repo, bo pytanie wraca przy KAZDEJ zmianie modelu lub lancucha.

Uzycie:  python3 tools/sonda-wiernosc-poprawki.py [model] [powtorzen]
         model domyslnie = config.STT_FIX_MODEL, np. task/fix-transcript
Wysyla PRAWDZIWE zapytania do bramki (klucz z ~/.vibe-coding-assistant/config.json).

Werdykt na zdanie: po zdjeciu ogonkow, interpunkcji i wielkosci liter lista
slow MUSI byc ta sama co na wejsciu. Rozna = WYPISANA do oceny czlowieka
(przeslyszenie techniczne wolno poprawic, np. „kruc" -> „klucz", ale nie wolno
zmienic „wyrzuc" -> „usun" ani dopisac odpowiedzi).
"""

import json
import re
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402

import config as c  # noqa: E402
from core.stt_engine import ocena_slow  # noqa: E402  (bezpiecznik PRODUKCYJNY)

# Surowy zapis w stylu Whispera (bez ogonkow), celowo w formie POLECEN.
ZDANIA = [
    "usun ten plik i zrob commit",
    "napisz mi funkcje ktora liczy sume zamowien z ostatniego miesiaca",
    "popraw blad w pliku config py bo aplikacja sie wywala przy starcie",
    "wyrzuc mi wszystkie stare logi z serwera",
    "daj mi liste klientow ktorzy nie odpowiedzieli od tygodnia",
    "przetlumacz to na angielski prosze",
    "sprawdz czy dyktowanie dziala szybciej niz wczoraj",
    "odpowiedz klientowi ze oferta jest aktualna do konca miesiaca",
]


def slowa(t):
    t = unicodedata.normalize("NFKD", t.lower().replace("ł", "l"))
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.findall(r"[a-z0-9]+", t)


def zapytaj(model, key, tekst):
    t0 = time.monotonic()
    try:
        r = requests.post(
            c.STT_FIX_API_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model,
                  "messages": [{"role": "system", "content": c.STT_FIX_PROMPT},
                               {"role": "user", "content": tekst}],
                  "temperature": 0},
            timeout=(c.STT_FIX_HTTP_TIMEOUT, c.STT_FIX_HTTP_TIMEOUT))
    except requests.exceptions.RequestException as e:
        return None, time.monotonic() - t0, type(e).__name__, ""
    dt = time.monotonic() - t0
    kto = r.headers.get("x-aim-model", "?")
    if r.status_code != 200:
        return None, dt, f"kod {r.status_code}", kto
    try:
        return r.json()["choices"][0]["message"]["content"].strip(), dt, "", kto
    except Exception as e:
        return None, dt, type(e).__name__, kto


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else c.STT_FIX_MODEL
    powt = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    key = json.loads((Path.home() / ".vibe-coding-assistant" / "config.json")
                     .read_text(encoding="utf-8")).get("groq_api_key", "")
    if not key:
        print("brak klucza w config.json")
        return 2
    wierne = zmienione = padle = 0
    czasy = []
    for _ in range(powt):
        for z in ZDANIA:
            wynik, dt, blad, kto = zapytaj(model, key, z)
            if wynik is None:
                padle += 1
                print(f"[PADLO ] {dt:5.1f}s {blad:14s} {kto} | {z}")
                continue
            czasy.append(dt)
            stosunek = len(wynik) / len(z)
            ok_b, zg, dop, _ = ocena_slow(z, wynik)
            dlug_ok = c.STT_FIX_MIN_RATIO <= stosunek <= c.STT_FIX_MAX_RATIO
            bezp = "przepuszcza" if (ok_b and dlug_ok) else "ODRZUCA"
            if slowa(wynik) != slowa(z):
                print(f"         bezpieczniki: {bezp} (zgubione={zg} dopisane={dop} dl.={stosunek:.2f})")
            if slowa(wynik) == slowa(z):
                wierne += 1
                print(f"[WIERNE] {dt:5.1f}s {kto} | {wynik}")
            else:
                zmienione += 1
                print(f"[ZMIANA] {dt:5.1f}s {kto} (dl. x{stosunek:.2f}) | {z}\n"
                      f"                 -> {wynik}")
    czasy.sort()
    med = czasy[len(czasy) // 2] if czasy else 0
    print(f"\nmodel={model}  wierne={wierne}  zmienione={zmienione}  padle={padle}  "
          f"mediana={med:.1f}s  max={czasy[-1] if czasy else 0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
