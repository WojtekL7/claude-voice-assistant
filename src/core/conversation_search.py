"""Wyszukiwanie w rozmowie agenta (🔍) — sama logika, bez okien.

Trzymamy to osobno od GUI, żeby dało się przetestować bez budowania widżetów
(ta sama zasada, co przy `turn_snapshot` i limitach RAM).

Źródłem jest DZIENNIK SESJI, nie bufor ekranu — bo tylko dziennik ma całą
rozmowę od początku i czysty tekst. Bufor terminala ma cap 5000 znaków,
znaki sterujące i ramki narzędzi (patrz historia BUG #3 „czyta śmieci z ekranu").
"""
import re
import unicodedata
from typing import List, Optional

# Ile znaków kontekstu pokazujemy z każdej strony trafienia na liście wyników.
CONTEXT_CHARS = 60

# Polskie „ł" NIE rozkłada się przez NFKD (zostaje jako osobna litera, a przy
# `encode('ascii','ignore')` po prostu ZNIKA — „działa" → „dziaa"). Dlatego
# najpierw ręczna podmiana, dopiero potem normalizacja. Ta sama pułapka co przy
# nazwach plików wysyłanych w nagłówkach HTTP (patrz CLAUDE-COMMON, PUŁAPKI PYTHON).
_MANUAL_FOLD = str.maketrans({
    'ł': 'l', 'Ł': 'L',
    'đ': 'd', 'Đ': 'D',
    'ø': 'o', 'Ø': 'O',
    'ß': 's',
})


def fold(text: str) -> str:
    """Postać do PORÓWNYWANIA: bez wielkości liter i bez ogonków.

    Dzięki temu „zolw" znajduje „żółw", a „SPRAWDZ" znajduje „sprawdź" —
    istotne, bo user często pisze bez polskich znaków, gdy się spieszy.
    ⚠️ Funkcja MUSI zachowywać DŁUGOŚĆ tekstu znak w znak, inaczej pozycje
    trafień wskazywałyby inne miejsce w oryginale niż naprawdę.
    """
    if not text:
        return ""
    swapped = text.translate(_MANUAL_FOLD)
    out = []
    for ch in swapped:
        base = unicodedata.normalize('NFKD', ch)
        stripped = ''.join(c for c in base if not unicodedata.combining(c))
        # Znak bez odpowiednika ASCII (np. emoji) zostaje sobą — byle JEDEN znak.
        out.append(stripped[:1] if stripped else ch)
    return ''.join(out).lower()


def utf16_offset(text: str, index: int) -> int:
    """Pozycja pythonowa (punkty kodowe) → pozycja Qt (jednostki UTF-16).

    ⚠️ POWÓD ISTNIENIA TEJ FUNKCJI (zmierzone 2026-08-03, zgłoszone przez usera):
    Python liczy znaki jako PUNKTY KODOWE, a `QString`/`QTextCursor` w JEDNOSTKACH
    UTF-16 — każdy znak spoza BMP (emoji 🤖 🔍 ✅, część CJK) zajmuje w Qt DWA
    miejsca. Podanie indeksu pythonowego wprost do `setPosition` przesuwało więc
    podświetlenie w LEWO o tyle znaków, ile emoji stało wcześniej w tekście
    (w realnej wypowiedzi: 5 emoji → zaznaczone „wie " zamiast „lupa").

    Objaw MYLI: wygląda jak zły algorytm szukania, choć szukanie jest poprawne —
    psuje się dopiero PRZEKAZANIE pozycji do widżetu. Dlatego przeliczenie robimy
    WYŁĄCZNIE na styku z Qt; wewnątrz Pythona indeksy zostają pythonowe.
    """
    if index <= 0:
        return 0
    return len(text[:index].encode('utf-16-le')) // 2


class Hit:
    """Jedno trafienie: skąd pochodzi, w którym miejscu i z jakim kontekstem."""

    __slots__ = ('entry_index', 'role', 'time', 'text', 'start', 'end')

    def __init__(self, entry_index: int, role: str, time: str, text: str,
                 start: int, end: int):
        self.entry_index = entry_index
        self.role = role
        self.time = time
        self.text = text
        self.start = start
        self.end = end

    def snippet(self, context: int = CONTEXT_CHARS) -> str:
        """Fragment zdania wokół trafienia, w JEDNEJ linii (do listy wyników)."""
        left = max(0, self.start - context)
        right = min(len(self.text), self.end + context)
        piece = self.text[left:right].replace('\n', ' ')
        piece = re.sub(r'\s+', ' ', piece).strip()
        return ('…' if left > 0 else '') + piece + ('…' if right < len(self.text) else '')

    def matched_text(self) -> str:
        return self.text[self.start:self.end]


def find_hits(entries: List[dict], query: str, roles: Optional[set] = None,
              limit: int = 500) -> List[Hit]:
    """Znajdź WSZYSTKIE wystąpienia frazy w rozmowie (od najstarszego).

    `entries` = wynik `TranscriptReader.conversation_entries()`.
    `roles` = ograniczenie do ról (None = cała rozmowa: user + assistant).
    Puste/białe zapytanie → pusta lista (nie zwracamy „wszystkiego").
    """
    query = (query or "").strip()
    if not query:
        return []
    needle = fold(query)
    if not needle:
        return []
    hits: List[Hit] = []
    for idx, entry in enumerate(entries):
        role = entry.get('role', '')
        if roles is not None and role not in roles:
            continue
        text = entry.get('text') or ''
        haystack = fold(text)
        # Zabezpieczenie: gdyby złożenie zmieniło długość, pozycje byłyby
        # przesunięte — wtedy lepiej pominąć wpis niż pokazać zły fragment.
        if len(haystack) != len(text):
            continue
        start = haystack.find(needle)
        while start != -1:
            hits.append(Hit(idx, role, entry.get('time', ''), text,
                            start, start + len(needle)))
            if len(hits) >= limit:
                return hits
            start = haystack.find(needle, start + 1)
    return hits


def summarize(hits: List[Hit]) -> dict:
    """Ile trafień i w ilu wypowiedziach (do podpisu nad listą)."""
    return {
        'hits': len(hits),
        'entries': len({h.entry_index for h in hits}),
    }
