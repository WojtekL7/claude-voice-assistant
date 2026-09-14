"""Lekarz skilli — ile kontekstu kosztuje każdy skill i czy ktokolwiek go używa.

PO CO TO JEST
-------------
Każdy zainstalowany skill dokłada swoją linijkę do promptu systemowego
**przy KAŻDEJ turze rozmowy** — niezależnie od tego, czy Claude kiedykolwiek
go użyje. Lista rośnie latami, nikt jej nie przegląda, a rachunek rośnie po
cichu. Claude Code od wersji 2.1.252 potrafi to policzyć (`/skill-doctor`);
my to uruchamiamy, czytamy i pokazujemy w oknie, bo w terminalu nikt tego
sam nie odpali.

Zmierzone u właściciela 2026-09-14: **23 skille, 16 nigdy nieużytych.**

JAK SIĘ WYŁĄCZA SKILL — ZMIERZONE, NIE ZGADNIĘTE
------------------------------------------------
⛔ Mechanizm, który VCA miała już wcześniej (`permissions.deny` → `Skill(nazwa)`,
`core/agent_skills_settings.py`), **NIE zdejmuje kosztu kontekstu** — blokuje
uruchomienie, ale skill dalej stoi na liście z pełną ceną. Sprawdzone wprost:
po dopisaniu `Skill(pdf)`, `Skill(docx)`, `Skill(pptx)` do `deny` raport
pokazywał je z kosztem `~150`, `~260`, `~230`. Podpięcie przycisku „wyłącz"
do tamtej drogi obiecywałoby oszczędność, której nie ma.

Działa `skillOverrides` w ustawieniach Claude Code (cztery stany):
    "on"                  — nazwa i opis w kontekście (stan domyślny)
    "name-only"           — sama nazwa (u nas z ~260 zrobiło się < 20)
    "user-invocable-only" — UKRYTY przed Claude, ale DALEJ wywołasz go `/nazwa`
    "off"                 — ukryty zupełnie, także z menu `/`
Zmierzone na żywym `/skill-doctor`: przy `user-invocable-only` i `off` koszt
kontekstu spada do zera (`-`), przy nietkniętym skillu zostaje `~230`.

⭐ Dlatego domyślnie proponujemy `user-invocable-only`, a nie `off`: użytkownik
przestaje płacić za skill w każdej turze, a NIC NIE TRACI — może go nadal
wywołać ręcznie. „off" zostaje jako świadomy wybór.
"""

from __future__ import annotations

import os
import re
import subprocess

# Stany, które rozumie Claude Code (kolejność = od najtańszego dla kontekstu).
OVERRIDE_STATES = ("off", "user-invocable-only", "name-only", "on")

# Stan proponowany przy „wyłącz nieużywane": zero kosztu, zero straty.
DEFAULT_OFF_STATE = "user-invocable-only"

# Wiersz raportu: nazwa, źródło, koszt kontekstu, tokeny 7d, użycia, ostatnio.
#   „  pdf                userSettings     ~150          -     7×  7 days"
_ROW_RE = re.compile(
    r"^\s{2,}(?P<name>[A-Za-z0-9][\w.:-]*)\s{2,}"
    r"(?P<source>\S+)\s{2,}"
    r"(?P<context>-|<\s*\d+|~?\s*\d+)\s{2,}"
    r"(?P<tokens>-|[\d,]+)\s{2,}"
    r"(?P<uses>\d+)\s*×\s+"
    r"(?P<last>.+?)\s*$"
)
_NEVER_RE = re.compile(r"(\d+)\s+skills?\s+loaded\s+but\s+never\s+invoked", re.I)
_DAYS_RE = re.compile(r"(\d+)\s*days?", re.I)


class SkillDoctorError(RuntimeError):
    """Nie udało się uruchomić albo odczytać raportu (wołający ma fail-open)."""


def _parse_context(text: str) -> int | None:
    """'~150' → 150, '< 20' → 20, '-' → None (nie ma go w liście = nic nie kosztuje)."""
    text = (text or "").strip()
    if text == "-":
        return None
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


def parse_report(text: str) -> dict:
    """Surowe wyjście `/skill-doctor` → dane do tabeli.

    Zwraca `{"skills": [...], "never_used": int|None, "total_context": int}`.
    Rzuca `SkillDoctorError`, gdy nie da się wyłuskać ANI JEDNEGO skilla —
    „udany" odczyt pustej listy wyglądałby jak „nie masz żadnych skilli",
    czyli byłby gorszy niż jawny błąd.
    """
    skills = []
    for line in (text or "").splitlines():
        # Nagłówek tabeli ma te same odstępy co wiersze — odsiewamy go po treści.
        # ⚠️ TO JEST DRUGA LINIA OBRONY, NIE MECHANIZM — zmierzone sabotażem
        # (`sabotaz-skill-doctor.py S10`: 0 padłych przy 76 wykonanych).
        # Wzorzec wiersza i tak odrzuca nagłówek, bo w kolumnie kosztu stoi
        # tam słowo „context", a nie liczba. Zostawiamy to jawnie, bo jest
        # darmowe i czytelne — ale NIE licz na test, którego nie ma: gdyby
        # kiedyś kolumny zmieniły układ, ochroną jest wzorzec, nie ta linia.
        if re.match(r"^\s+skill\s+source\s+context", line):
            continue
        m = _ROW_RE.match(line)
        if not m:
            continue
        ostatnio = m.group("last").strip()
        dni = _DAYS_RE.search(ostatnio)
        skills.append({
            "name": m.group("name"),
            "source": m.group("source"),
            "context": _parse_context(m.group("context")),
            "tokens_7d": None if m.group("tokens") == "-" else int(
                m.group("tokens").replace(",", "")),
            "uses": int(m.group("uses")),
            "last_used": ostatnio,
            "last_used_days": int(dni.group(1)) if dni else None,
        })
    if not skills:
        raise SkillDoctorError("nie znalazłem ani jednego skilla — raport ma inny układ")

    nigdy = _NEVER_RE.search(text or "")
    return {
        "skills": skills,
        "never_used": int(nigdy.group(1)) if nigdy else None,
        "total_context": sum(s["context"] or 0 for s in skills),
    }


def wasted_context(raport: dict) -> int:
    """Ile tokenów PRZY KAŻDEJ TURZE idzie na skille, których nikt nie użył."""
    return sum(s["context"] or 0 for s in (raport or {}).get("skills", [])
               if s.get("uses") == 0)


def sort_for_review(skills: list) -> list:
    """Kolejność do przeglądu: najpierw nieużywane, w nich najdroższe.

    Dokumentacja Claude Code mówi wprost: zaczynaj od tych o najwyższym koszcie
    kontekstu. Nieużywane idą przed używanymi, bo tylko przy nich decyzja jest
    oczywista.
    """
    return sorted(skills or [],
                  key=lambda s: (s.get("uses", 0) != 0,
                                 -(s.get("context") or 0),
                                 s.get("name", "")))


def run_report(claude_command: str = "claude", cwd: str = None,
               timeout: int = 180) -> str:
    """Uruchom `claude -p /skill-doctor` i oddaj surowy tekst raportu.

    ⛔ WEJŚCIE STANDARDOWE ZAMKNIĘTE (`stdin=DEVNULL`). `claude` przyjmuje treść
    także z wejścia, więc otwarta rura znaczy dla niego „dane jeszcze przyjdą"
    i proces WISI W NIESKOŃCZONOŚĆ — objaw wskazuje wtedy na wszystko oprócz
    przyczyny (to samo polecenie w terminalu kończy się od razu).

    ⛔ Zdejmujemy też zmienne, którymi Claude Code oznacza SWOJE podprocesy
    (`CLAUDECODE`, `CLAUDE_CODE_ENTRYPOINT`) — bez tego uruchomiony z wnętrza
    apki zachowuje się inaczej niż uruchomiony przez człowieka.
    """
    polecenie = (claude_command or "claude").strip() or "claude"
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT",
                        "CLAUDE_CODE_CHILD_SESSION")}
    try:
        wynik = subprocess.run(
            [polecenie, "-p", "/skill-doctor"],
            stdin=subprocess.DEVNULL,        # ⛔ patrz wyżej — bez tego wisi
            capture_output=True, text=True,
            timeout=timeout, cwd=cwd or None, env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise SkillDoctorError(f"raport nie wrócił w {timeout} s") from exc
    except Exception as exc:
        raise SkillDoctorError(f"nie udało się uruchomić „{polecenie}”: {exc}") from exc

    tekst = (wynik.stdout or "") + (wynik.stderr or "")
    if not tekst.strip():
        raise SkillDoctorError("raport jest pusty")
    return tekst
