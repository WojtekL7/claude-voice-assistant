"""
Vibe Coding Assistant - Transcript Reader (Etap 2, Droga A)

Czyta czyste wypowiedzi Claude'a z pliku-dziennika sesji Claude Code
(`~/.claude/projects/<katalog>/<sesja>.jsonl`) — zamiast parsować śmieciowy,
"skaczący" strumień terminala.

Bierzemy WYŁĄCZNIE:
- wpisy typu "assistant",
- nie będące pod-agentem (isSidechain == False/brak),
- z bloków treści tylko typ "text" (pomijamy "thinking" i "tool_use").

Dzięki temu narzędzia, myślenie i pod-agenci odpadają automatycznie, a tekst
jest czysty (poprawny markdown, polskie znaki OK) — gotowy do filtra prozy.

Klasa jest "głupia" i nieblokująca: trzyma offset bajtowy w aktywnym pliku
sesji i przy poll() dokłada tylko NOWE, kompletne linie. Logikę "kiedy czytać"
(aktywna zakładka, zaległości) zostawiamy warstwie GUI (Etap 3).
"""
import os
import re
import json
import glob
import time
from pathlib import Path
from typing import List, Optional


# Stan TURY odczytany ze struktury dziennika (patrz TranscriptReader.turn_snapshot).
# Nazwy trzymamy tu, bo używa ich też GUI (decyzja „czytać teraz czy poczekać").
TURN_IDLE = "idle"                  # agent skończył — ostatnia wypowiedź jest ostatnią
TURN_OWES_TEXT = "owes_text"        # agent jest winien odpowiedź (myśli / ma wynik narzędzia)
TURN_TOOL_PENDING = "tool_pending"  # pracuje narzędzie / czeka na zgodę — tekst nieprędko
TURN_UNKNOWN = "unknown"            # nie da się orzec (brak sesji, plik nieczytelny)


def _encode_project_dir(working_directory: str) -> str:
    """Zamień ścieżkę katalogu roboczego na nazwę folderu w ~/.claude/projects.

    Claude Code koduje ścieżkę zamieniając znaki niealfanumeryczne na '-'.
    Np. /home/u/Projekty/claude-voice-assistant
        -> -home-u-Projekty-claude-voice-assistant
    """
    abspath = os.path.abspath(os.path.expanduser(working_directory))
    return re.sub(r'[^A-Za-z0-9]', '-', abspath)


class TranscriptReader:
    """Czyta nowe wypowiedzi tekstowe Claude'a z dziennika sesji."""

    # Rozpoznanie komunikatu o WYGASŁYM LOGOWANIU wśród błędów API.
    # ⚠️ Wzorzec stosujemy WYŁĄCZNIE do wpisów z pieczątką `isApiErrorMessage`
    # (patrz _is_api_error). Samo szukanie tych słów w treści byłoby BŁĘDEM:
    # fraza „Please run /login" pojawia się w NORMALNEJ rozmowie (pliki pamięci,
    # opis tej właśnie usterki), więc dopasowanie po tekście uznawałoby rozmowę
    # o problemie za sam problem.
    _AUTH_ERROR_RE = re.compile(
        r"login expired|please run\s*/login|invalid authentication|"
        r"authentication_error|unauthorized|\b401\b",
        re.I,
    )
    # Ile komunikatów błędu trzymamy, zanim GUI je odbierze (anty-rozrost).
    _API_ERRORS_CAP = 20

    def __init__(self, working_directory: str):
        self._projects_base = Path.home() / ".claude" / "projects"
        self.working_directory = ""
        self._project_dir: Optional[Path] = None
        self._session_file: Optional[str] = None
        self._offset = 0
        # Stan dla waiting_for_user(): ostatni zaobserwowany rozmiar pliku sesji
        # (-1 = jeszcze nie obserwowano) oraz licznik kolejnych sprawdzeń, w
        # których plik był STATYCZNY (do odrzucenia krótkich pauz w streamingu).
        self._wait_last_size = -1
        self._wait_stable = 0
        # Gdy znamy DOKŁADNY identyfikator sesji (apka uruchamia
        # `claude --session-id <uuid>`), czytnik patrzy tylko na ten jeden
        # plik <uuid>.jsonl — bez zgadywania z katalogu. None = tryb zgadywania
        # (np. sesja wznowiona ręcznie po crashu, spoza kontroli apki).
        self._pinned_session_id: Optional[str] = None
        # Komunikaty BŁĘDÓW Claude Code wyłuskane w poll() (wygasłe logowanie,
        # przeciążenie API). To NIE są wypowiedzi agenta — nie idą do lektora;
        # odbiera je GUI przez take_api_errors().
        self._api_errors: List[dict] = []
        self.set_working_directory(working_directory)

    # ---------- konfiguracja ----------

    def set_working_directory(self, working_directory: str):
        """Ustaw katalog roboczy zakładki i znajdź jego folder w transkrypcie."""
        self.working_directory = os.path.abspath(os.path.expanduser(working_directory))
        self._project_dir = self._find_project_dir()
        self._session_file = None
        self._offset = 0
        # Moment startu czytnika (zegar ścienny). Służy do "przygarnięcia"
        # sesji, która ISTNIAŁA już przy starcie, ale jest dalej zapisywana
        # PO nim (= wznowiona sesja tej zakładki po restarcie/reopenie) — patrz
        # _newest_session_file. mtime pliku i time.time() są w tym samym zegarze.
        self._reader_start = time.time()
        # Sesją ZAKŁADKI jest plik, który powstanie PO jej starcie (czytnik
        # tworzymy w chwili uruchamiania claude). Pliki istniejące wcześniej —
        # w tym RÓWNOLEGŁE sesje Claude Code w tym samym katalogu (np. osobne
        # okno terminala) — domyślnie pomijamy. WYJĄTEK (samonaprawa): jeśli
        # zakładka NIE utworzyła własnego nowego pliku (np. po self-update apka
        # wstała, a Claude WZNOWIŁ istniejący plik), przygarniamy plik istniejący
        # wcześniej, ALE zapisywany po starcie czytnika — to żywa sesja tej
        # zakładki. Stare, NIETKNIĘTE pliki dalej pomijamy (żeby nie czytać
        # cudzych/starych wypowiedzi). Bez wznowienia "najnowszy po mtime"
        # przeskakiwałby na obcą, aktywnie pisaną sesję.
        self._preexisting = self._existing_session_files()

    def _existing_session_files(self) -> set:
        if not self._project_dir or not self._project_dir.is_dir():
            return set()
        try:
            return set(glob.glob(str(self._project_dir / "*.jsonl")))
        except Exception:
            return set()

    def _find_project_dir(self) -> Optional[Path]:
        """Znajdź folder transkryptu odpowiadający katalogowi roboczemu."""
        if not self._projects_base.is_dir():
            return None
        # 1) Wprost po zakodowanej nazwie.
        cand = self._projects_base / _encode_project_dir(self.working_directory)
        if cand.is_dir():
            return cand
        # 2) Fallback: przeszukaj foldery i dopasuj po polu 'cwd' w pierwszym wpisie.
        for d in self._projects_base.iterdir():
            if not d.is_dir():
                continue
            try:
                jsonls = list(d.glob("*.jsonl"))
                if not jsonls:
                    continue
                newest = max(jsonls, key=lambda p: p.stat().st_mtime)
                with open(newest, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        obj = json.loads(line)
                        if obj.get("cwd") and os.path.abspath(obj["cwd"]) == self.working_directory:
                            return d
                        break  # sprawdzamy tylko pierwszy sensowny wpis
            except Exception:
                continue
        return None

    # ---------- wybór pliku sesji ----------

    def _newest_session_file(self) -> Optional[str]:
        if not self._project_dir or not self._project_dir.is_dir():
            # katalog mógł powstać dopiero teraz — spróbuj ponownie
            self._project_dir = self._find_project_dir()
            if not self._project_dir:
                return None
        files = glob.glob(str(self._project_dir / "*.jsonl"))
        pre = getattr(self, "_preexisting", set())
        # Poziom 1 (preferowany): pliki powstałe PO starcie zakładki — własna
        # nowa sesja / kolejny plik po /clear. Tu zachowana stara ochrona:
        # gdy zakładka ma swój świeży plik, cudze/stare sesje są ignorowane.
        fresh = [f for f in files if f not in pre]
        if fresh:
            return max(fresh, key=self._safe_mtime)
        # Poziom 2 (samonaprawa): brak własnego nowego pliku → przygarnij sesję,
        # która ISTNIAŁA wcześniej, ale jest zapisywana PO starcie czytnika
        # (mtime > _reader_start) — to wznowiona żywa sesja tej zakładki.
        # Stare, nietknięte pliki (mtime <= start) zostają pominięte.
        start = getattr(self, "_reader_start", 0)
        resumed = [f for f in files if self._safe_mtime(f) > start]
        if resumed:
            return max(resumed, key=self._safe_mtime)
        return None

    @staticmethod
    def _safe_mtime(path: str) -> float:
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0.0

    @staticmethod
    def _safe_size(path: str) -> int:
        try:
            return os.path.getsize(path)
        except OSError:
            return 0

    def pin_session(self, session_id: str):
        """Przypnij DOKŁADNY plik sesji — znamy go z `claude --session-id <uuid>`.

        Koniec zgadywania: czytnik patrzy wyłącznie na <project_dir>/<uuid>.jsonl.
        Plik może jeszcze nie istnieć (claude utworzy go przy starcie) — wtedy
        has_session()/waiting_for_user() zwracają „brak/nie czeka", a zaczną
        działać w chwili, gdy plik się pojawi. Reset stanu offsetu i liczników
        ciszy, by przy RESTARCIE zakładki zacząć od nowej sesji od zera.
        """
        self._pinned_session_id = (session_id or "").strip() or None
        self._session_file = None
        self._offset = 0
        self._wait_last_size = -1
        self._wait_stable = 0
        self._api_errors = []

    def _ensure_session(self):
        """Upewnij się, że śledzimy właściwy plik sesji.

        Tryb PRZYPIĘTY (znamy --session-id): pilnujemy dokładnie <uuid>.jsonl.
        Tryb ZGADYWANIA (pin=None): bierzemy najnowszy plik wg dotychczasowej
        heurystyki (wznowienia ręczne spoza apki).
        """
        pinned = getattr(self, "_pinned_session_id", None)
        if pinned:
            if not self._project_dir or not self._project_dir.is_dir():
                # katalog projektu powstaje dopiero gdy claude wystartuje
                self._project_dir = self._find_project_dir()
            if not self._project_dir:
                return
            cand = str(self._project_dir / f"{pinned}.jsonl")
            if os.path.exists(cand):
                if cand != self._session_file:
                    self._session_file = cand
                    self._offset = 0
            # plik jeszcze nie powstał → czekamy (session_file zostaje None)
            return
        newest = self._newest_session_file()
        if newest != self._session_file:
            self._session_file = newest
            if newest and newest in getattr(self, "_preexisting", set()):
                # Przygarnięto wznowioną sesję istniejącą wcześniej — ma już
                # historię. Przeskocz na KONIEC, żeby nie odgrywać na głos całej
                # dotychczasowej rozmowy (czytamy tylko to, co przyjdzie dalej).
                self._offset = self._safe_size(newest)
            else:
                # Świeży plik (nowa sesja / po /clear) — czytaj od początku.
                self._offset = 0

    def seek_to_end(self):
        """Przeskocz na koniec bieżącej sesji (pomiń zaległości)."""
        self._ensure_session()
        if self._session_file and os.path.exists(self._session_file):
            self._offset = os.path.getsize(self._session_file)
        else:
            self._offset = 0

    def has_session(self) -> bool:
        self._ensure_session()
        return self._session_file is not None

    # ---------- odczyt ----------

    def poll(self) -> List[str]:
        """Zwróć listę NOWYCH wypowiedzi tekstowych Claude'a od ostatniego poll().

        Każdy element listy = jeden blok tekstowy asystenta (surowy markdown).
        Niekompletna ostatnia linia (jeszcze dopisywana) jest pomijana do
        kolejnego wywołania.
        """
        self._ensure_session()
        if not self._session_file or not os.path.exists(self._session_file):
            return []

        try:
            size = os.path.getsize(self._session_file)
            if size < self._offset:
                # Plik się skurczył — Claude Code SKOMPAKTOWAŁ dziennik (auto-
                # compact przy długiej sesji) albo /clear przepisał <uuid>.jsonl
                # na krótszy. NIE wracamy na początek (self._offset = 0): poll()
                # oddałby wtedy CAŁY plik i lektor recytowałby całą rozmowę od
                # nowa przy każdym compact. Skaczemy na KONIEC (filozofia
                # primingu): czytamy tylko to, co przyjdzie DALEJ. Flaga „?"
                # (waiting_for_user) ma osobny licznik _wait_last_size i sam się
                # koryguje, więc na nią to nie wpływa.
                self._offset = size
                return []
            if size == self._offset:
                return []
            with open(self._session_file, "rb") as f:
                f.seek(self._offset)
                raw = f.read()
        except Exception:
            return []

        # Przetwarzamy tylko kompletne linie (do ostatniego '\n').
        # Ostatnia linia bez '\n' = zapis W TOKU → czeka na kolejne wywołanie.
        # (Sprawdzone 2026-07-21: Claude Code kończy wpis znakiem nowej linii —
        # 8/8 ustabilizowanych dzienników — więc ogon czeka ułamek sekundy, a nie
        # w nieskończoność. Objaw „czyta przedostatnią" ma inną przyczynę:
        # kolejkę lektora, patrz MainWindow._poll_transcripts.)
        last_nl = raw.rfind(b"\n")
        if last_nl == -1:
            return []  # nic kompletnego jeszcze nie ma
        consumed = last_nl + 1
        complete = raw[:consumed]
        self._offset += consumed

        results: List[str] = []
        for bline in complete.split(b"\n"):
            if not bline.strip():
                continue
            try:
                obj = json.loads(bline.decode("utf-8", "ignore"))
            except Exception:
                continue
            self._consume_entry(obj, results)
        return results

    def _consume_entry(self, obj: dict, results: List[str]):
        """Przetwórz JEDEN wpis dziennika.

        Błąd Claude Code → kolejka dla GUI (nie dla lektora).
        Zwykła wypowiedź tekstowa → do listy wyników.
        """
        if not isinstance(obj, dict):
            return
        if self._is_api_error(obj):
            self._record_api_error(obj)
            return
        text = self._extract_text(obj)
        if text:
            results.append(text)

    # ---------- błędy Claude Code (wygasłe logowanie, przeciążenie) ----------

    @staticmethod
    def _is_api_error(obj: dict) -> bool:
        """Czy wpis to KOMUNIKAT BŁĘDU Claude Code, a nie wypowiedź agenta?

        Rozpoznajemy po PIECZĄTCE `isApiErrorMessage` (Claude Code stawia ją
        sam; takie wpisy mają też `message.model == "<synthetic>"`), NIGDY po
        treści — patrz komentarz przy _AUTH_ERROR_RE.
        """
        return obj.get("type") == "assistant" and bool(obj.get("isApiErrorMessage"))

    def _record_api_error(self, obj: dict):
        """Odłóż komunikat błędu dla GUI (z oceną, czy dotyczy logowania)."""
        parts = []
        for block in (obj.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                parts.append(block["text"])
        text = " ".join(parts).strip()
        if not text:
            return
        self._api_errors.append({
            "text": text,
            "timestamp": obj.get("timestamp"),
            "is_auth": bool(self._AUTH_ERROR_RE.search(text)),
            "session_file": self._session_file,
        })
        if len(self._api_errors) > self._API_ERRORS_CAP:
            self._api_errors = self._api_errors[-self._API_ERRORS_CAP:]

    def take_api_errors(self) -> List[dict]:
        """Odbierz (i wyczyść) komunikaty błędów zebrane przez poll()."""
        errors, self._api_errors = self._api_errors, []
        return errors

    def journal_lags_screen(self) -> bool:
        """Czy dziennik NIE ma jeszcze ostatniej wypowiedzi (jest o nią w tyle)?

        Claude Code odracza zapis wypowiedzi kończącej turę pytaniem
        `AskUserQuestion` — dopisuje ją dopiero po odpowiedzi użytkownika.
        W tym oknie ostatnim wpisem z rolą zostaje `user` (polecenie albo
        `tool_result`), bo tekst asystenta jeszcze nie wylądował w pliku.

        Po ZWYKŁYM końcu tury jest odwrotnie: ostatnim wpisem z rolą jest
        `assistant` (jego wypowiedź jest już w pliku, w komplecie i czysta).
        Zweryfikowane na żywym dzienniku 2026-07-10.

        Zwraca True tylko gdy trzeba sięgnąć po brudny bufor EKRANU.
        """
        self._ensure_session()
        if not self._session_file or not os.path.exists(self._session_file):
            return True
        # skip_agent_turns: wynik narzędzia / przerwanie NIE liczą się jako
        # „użytkownik czeka" — inaczej w sesjach z dużą liczbą komend (CRM,
        # deploy) dziennik był fałszywie uznawany za spóźniony i „czytaj
        # ostatnią" sięgało po brudny bufor ekranu zamiast czystego dziennika.
        return self._last_entry_role(skip_agent_turns=True) == "user"

    def last_response(self) -> Optional[str]:
        """Zwróć OSTATNIĄ wypowiedź tekstową Claude'a z bieżącej sesji.

        Używane przez przycisk 🔊 (ręczne "czytaj"), gdy nie ma zaznaczenia
        ani zaległości. Czyta cały plik sesji — w sam raz na akcję na żądanie.
        """
        return self.turn_snapshot()[0]

    def turn_snapshot(self):
        """Zwróć `(ostatnia_wypowiedź, stan_tury)` — JEDEN przebieg po pliku.

        Stan tury odpowiada na pytanie, którego NIE da się zadać terminalowi:
        „czy agent jest nam jeszcze winien odpowiedź?". Terminal mówi tylko,
        czy coś się rusza — a między odpowiedzią użytkownika a pierwszym
        znakiem odpowiedzi agent potrafi MYŚLEĆ dziesiątki sekund (zmierzone
        na żywym dzienniku CRM 2026-07-25: 30 s ciszy w pliku), pokazując przy
        tym jedynie drobną animację. Dokładnie w tę dziurę wpadały rundy 1 i 2
        naprawy 🔊 (progi liczone ze strumienia znaków) i czytały POPRZEDNIĄ
        wypowiedź.

        Czytamy więc STRUKTURĘ tury — co stoi ZA ostatnią wypowiedzią:
          * nic (poza wpisami księgowymi)   → TURN_IDLE         (można czytać)
          * odpowiedź usera / wynik narzędzia / „myślenie"
                                            → TURN_OWES_TEXT    (czekaj na tekst)
          * uruchomione narzędzie bez wyniku → TURN_TOOL_PENDING (nic nie nadchodzi zaraz)
          * plik nieczytelny / brak sesji    → TURN_UNKNOWN      (decyduje stary czujnik)
        """
        self._ensure_session()
        if not self._session_file or not os.path.exists(self._session_file):
            return None, TURN_UNKNOWN
        last = None
        after = 0                # wpisy ROZMOWY stojące za ostatnią wypowiedzią
        pending_tools = set()    # narzędzia uruchomione i jeszcze bez wyniku
        try:
            with open(self._session_file, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    t = self._extract_text(obj)
                    if t:
                        # Nowa wypowiedź = tura „zeruje się": wszystko wcześniejsze
                        # (także narzędzia bez wyniku) dotyczy już przeszłości.
                        last = t
                        after = 0
                        pending_tools.clear()
                        continue
                    if not self._is_conversation_entry(obj):
                        continue
                    after += 1
                    self._track_tools(obj, pending_tools)
        except Exception:
            return last, TURN_UNKNOWN
        if after == 0:
            return last, TURN_IDLE
        if pending_tools:
            return last, TURN_TOOL_PENDING
        return last, TURN_OWES_TEXT

    def session_size(self) -> int:
        """Rozmiar pliku sesji (-1 = nie znamy). Rosnący plik = agent pracuje."""
        self._ensure_session()
        if not self._session_file:
            return -1
        return self._safe_size(self._session_file)

    @staticmethod
    def _is_conversation_entry(obj: dict) -> bool:
        """Czy wpis należy do ROZMOWY głównego agenta (a nie do księgowości)?

        Claude Code dopisuje po zakończonej turze wpisy techniczne
        (`system/turn_duration`, `last-prompt`, `ai-title`, `mode`,
        `permission-mode`, `attachment`). Gdyby liczyły się jako „coś się
        dzieje", KAŻDY bezczynny agent wyglądałby na winnego odpowiedź i 🔊
        czekałby zawsze. Pod-agenci (`isSidechain`) prowadzą własną turę —
        dla nas są niewidoczni.
        """
        if obj.get("isSidechain") or obj.get("isMeta"):
            return False
        return obj.get("type") in ("assistant", "user")

    @staticmethod
    def _track_tools(obj: dict, pending: set):
        """Dopisz uruchomione narzędzia i skreśl te, które już oddały wynik."""
        content = (obj.get("message") or {}).get("content")
        if not isinstance(content, list):
            return
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tool_id = block.get("id")
                if tool_id:
                    pending.add(tool_id)
            elif block.get("type") == "tool_result":
                pending.discard(block.get("tool_use_id"))

    def waiting_for_user(self) -> bool:
        """Czy agent ZATRZYMAŁ się i czeka na odpowiedź użytkownika?

        Definicja oparta o PRAWDĘ z dziennika sesji (odporna na zniekształcenia
        strumienia terminala i format popupów):

          agent czeka  ⇔  plik sesji STOI (nic nie dopisuje) przez ~kilka sekund,
                          a rozmowa już się zaczęła (jest wpis user/assistant).

        Dlaczego cisza w pliku, a NIE „ostatni wpis = assistant": Claude Code
        zapisuje wpis `tool_use` dla AskUserQuestion DOPIERO po odpowiedzi —
        więc przy pytaniu z opcjami ostatnim wpisem zostaje `user` (polecenie,
        które wywołało pytanie), a plik stoi. Tak samo „cisza" łapie prośbę o
        zgodę na Write/Edit/Bash, pytanie tekstem i „skończyłem — co dalej?".

        Rosnący plik = agent pracuje/pisze (myślenie, tool_use, streaming) →
        NIE czeka. Gdy odpowiesz, plik rośnie (nowy wpis) → False (flaga gaśnie).
        Wymagamy 2 kolejnych statycznych sprawdzeń (~1,6 s), by odrzucić krótkie
        pauzy między porcjami strumienia.
        """
        self._ensure_session()
        if not self._session_file or not os.path.exists(self._session_file):
            self._wait_last_size = -1
            self._wait_stable = 0
            return False
        try:
            size = os.path.getsize(self._session_file)
        except Exception:
            return False
        grew = (size != self._wait_last_size)
        self._wait_last_size = size
        if grew:
            self._wait_stable = 0
            return False  # plik się zmienił od ostatniego sprawdzenia = agent pracuje
        self._wait_stable += 1
        if self._wait_stable < 2:
            return False
        # Plik stoi od ~1,6 s. Upewnij się tylko, że rozmowa w ogóle ruszyła
        # (jest wpis user/assistant) — żeby nie zapalać flagi na pustej sesji
        # z samymi wpisami technicznymi (snapshot/mode itp.).
        return self._last_entry_role() is not None

    @staticmethod
    def _is_agent_turn_userentry(obj: dict) -> bool:
        """Czy ten wpis o roli 'user' to w istocie KONTYNUACJA tury agenta, a
        nie wypowiedź użytkownika?

        W dzienniku Claude Code rolę 'user' mają NIE tylko wiadomości od
        człowieka, ale też:
          • `tool_result` — wynik narzędzia, które URUCHOMIŁ AGENT (Bash/Read/
            Edit/…); to jego własna robota w środku tury,
          • marker „[Request interrupted by user for tool use]" — sygnał
            przerwania narzędzia, nie tekst do przeczytania.
        Takie wpisy NIE oznaczają, że użytkownik czeka z nieodczytaną
        odpowiedzią — ostatnia KOMPLETNA wypowiedź agenta jest już w dzienniku.
        (Rozpoznane z realnej sesji CRM: to one fałszywie kierowały „czytaj
        ostatnią" na brudny bufor ekranu — 38% momentów.)
        """
        msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
        content = msg.get("content")
        if not isinstance(content, list) or not content:
            return False
        if all(isinstance(b, dict) and b.get("type") == "tool_result"
               for b in content):
            return True
        for b in content:
            if (isinstance(b, dict) and b.get("type") == "text"
                    and "Request interrupted" in (b.get("text") or "")):
                return True
        return False

    def _last_entry_role(self, skip_agent_turns: bool = False) -> Optional[str]:
        """Rola ostatniego SENSOWNEGO wpisu ('assistant'/'user'/None).

        Pomija wpisy bez roli (np. file-history-snapshot) oraz pod-agentów
        (isSidechain). Czyta tylko ogon pliku — tanie przy dużych sesjach.

        `skip_agent_turns=True` dodatkowo pomija wpisy 'user' będące
        kontynuacją tury agenta (wynik narzędzia / przerwanie — patrz
        `_is_agent_turn_userentry`). Używa tego `journal_lags_screen()`, by NIE
        mylić własnej pracy agenta z „użytkownik czeka". Domyślnie False, żeby
        `waiting_for_user()` (flaga „agent czeka") zachował dotychczasowe
        zachowanie.
        """
        if not self._session_file:
            return None
        try:
            with open(self._session_file, "rb") as f:
                f.seek(0, os.SEEK_END)
                end = f.tell()
                start = max(0, end - 65536)   # ostatnie ~64 KB wystarczą na kilka wpisów
                f.seek(start)
                tail = f.read()
        except Exception:
            return None
        lines = tail.split(b"\n")
        if start > 0 and lines:
            lines = lines[1:]   # pierwsza linia mogła być ucięta w połowie
        for bline in reversed(lines):
            bline = bline.strip()
            if not bline:
                continue
            try:
                obj = json.loads(bline.decode("utf-8", "ignore"))
            except Exception:
                continue
            if obj.get("isSidechain"):
                continue
            msg = obj.get("message")
            role = msg.get("role") if isinstance(msg, dict) else None
            if role == "user" and skip_agent_turns and self._is_agent_turn_userentry(obj):
                continue   # wynik narzędzia / przerwanie — nie granica użytkownika
            if role in ("assistant", "user"):
                return role
            # wpis bez roli (snapshot itp.) — szukaj dalej wstecz
        return None

    @staticmethod
    def _extract_text(obj: dict) -> Optional[str]:
        """Wyciągnij prozę z wpisu, jeśli to wypowiedź tekstowa głównego agenta."""
        if obj.get("type") != "assistant":
            return None
        if obj.get("isSidechain"):
            return None
        if obj.get("isApiErrorMessage"):
            # Komunikat techniczny Claude Code („Login expired · Please run
            # /login", „API Error: 529 Overloaded") — nie czytamy go na głos
            # ANI w auto-czytaniu (poll), ANI przyciskiem 🔊 (last_response).
            return None
        msg = obj.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, list):
            return None
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if t:
                    parts.append(t)
        if not parts:
            return None
        return "\n\n".join(parts)
