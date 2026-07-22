#!/usr/bin/env python3
"""Próbnik: KIEDY nowa wypowiedź Claude'a staje się widoczna w dzienniku .jsonl.

Cel: zmierzyć okno, w którym przycisk 🔊 (czyta OSTATNI wpis tekstowy z pliku)
przeczytałby jeszcze POPRZEDNIĄ wypowiedź, mimo że na ekranie widać już nową.

Loguje:
  [NOWY TEKST]  gdy w pliku pojawi się wpis assistant/text — z czasem ściennym,
                znacznikiem samego wpisu i różnicą między nimi,
  [CO-BY-PRZECZYTAL] co 2 s — podgląd tekstu, który 🔊 zwróciłby W TEJ CHWILI.
"""
import calendar
import json
import os
import sys
import time

JOURNAL = sys.argv[1]
OUT = sys.argv[2]
DURATION = float(sys.argv[3]) if len(sys.argv) > 3 else 3600.0


def is_agent_text(obj):
    """Ta sama reguła co TranscriptReader._extract_text."""
    if obj.get("type") != "assistant":
        return None
    if obj.get("isSidechain") or obj.get("isApiErrorMessage"):
        return None
    content = (obj.get("message") or {}).get("content")
    if not isinstance(content, list):
        return None
    parts = [b.get("text") for b in content
             if isinstance(b, dict) and b.get("type") == "text" and b.get("text")]
    return "\n\n".join(parts) if parts else None


def log(fh, line):
    fh.write(line + "\n")
    fh.flush()


def main():
    end = time.time() + DURATION
    offset = os.path.getsize(JOURNAL) if os.path.exists(JOURNAL) else 0
    last_text = None
    last_text_seen_at = None
    last_snapshot = 0.0

    with open(OUT, "a", encoding="utf-8") as fh:
        log(fh, f"=== start {time.strftime('%H:%M:%S')} offset={offset} ===")
        while time.time() < end:
            try:
                size = os.path.getsize(JOURNAL)
            except OSError:
                time.sleep(0.5)
                continue

            if size < offset:            # skurczenie = kompaktowanie
                offset = size
            if size > offset:
                with open(JOURNAL, encoding="utf-8", errors="replace") as f:
                    f.seek(offset)
                    chunk = f.read()
                # tylko KOMPLETNE linie (ostatnia bez \n = zapis w toku)
                cut = chunk.rfind("\n")
                if cut >= 0:
                    complete, offset = chunk[:cut + 1], offset + len(
                        chunk[:cut + 1].encode("utf-8"))
                    for line in complete.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except Exception:
                            continue
                        txt = is_agent_text(obj)
                        now = time.time()
                        if txt:
                            ts = obj.get("timestamp", "")
                            delta = ""
                            if ts:
                                try:
                                    # ⚠️ znaczniki w .jsonl są w UTC — licz w UTC,
                                    # inaczej wynik jest przesunięty o całą strefę
                                    # (objaw: „opóźnienie +3601 s" zamiast +1 s).
                                    ent = calendar.timegm(time.strptime(
                                        ts[:19], "%Y-%m-%dT%H:%M:%S"))
                                    delta = f" opoznienie_zapisu={now - ent:+.1f}s"
                                except Exception:
                                    pass
                            log(fh, f"[NOWY TEKST] {time.strftime('%H:%M:%S')} "
                                    f"wpis_ts={ts[11:19]}{delta} | "
                                    f"{txt[:70].replace(chr(10), ' ')}")
                            last_text, last_text_seen_at = txt, now
                        else:
                            blocks = []
                            c = (obj.get("message") or {}).get("content")
                            if isinstance(c, list):
                                blocks = [b.get("type") for b in c
                                          if isinstance(b, dict)]
                            log(fh, f"[inny wpis ] {time.strftime('%H:%M:%S')} "
                                    f"typ={obj.get('type')} bloki={','.join(filter(None, blocks)) or '-'}")

            now = time.time()
            if now - last_snapshot >= 2.0:
                last_snapshot = now
                if last_text:
                    wiek = now - last_text_seen_at
                    log(fh, f"[CO-BY-PRZECZYTAL] {time.strftime('%H:%M:%S')} "
                            f"(w pliku od {wiek:.0f}s) {last_text[:70].replace(chr(10), ' ')}")
            time.sleep(0.5)
        log(fh, f"=== koniec {time.strftime('%H:%M:%S')} ===")


if __name__ == "__main__":
    main()
