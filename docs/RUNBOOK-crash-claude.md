# RUNBOOK — diagnoza crashu zakładki `claude` w CVA

Objaw: zakładka „wypada" do gołego promptu basha z hintem `claude --resume <uuid>`
(user widzi to jako „wylogowanie"). To **crash procesu `claude`**, NIE crash CVA
ani — zwykle — problem RAM. Pełny opis metody: `CLAUDE-VOICE-ASSISTANT.md`
(sekcja „DIAGNOZA CRASHU `claude`") + auto-pamięć `cva-crash-diagnostyka.md`.

---

## 📋 Prompt do wklejenia następnemu agentowi

```
Zbadaj crash zakładki w CVA (Claude Voice Assistant). Zakładka "wypadła" do
promptu basha z hintem `claude --resume`.

Zacznij od czarnej skrzynki — to ślad, który teraz zapisujemy automatycznie:
1. Najświeższy plik: ls -t ~/.claude-voice-assistant/crash-logs/ | head -1
   → przeczytaj go; tam jest stack trace / ekran ratunkowy z momentu crashu.

Potem wyklucz przyczyny w tej kolejności (metoda z cva-crash-diagnostyka.md):
2. RAM/OOM:  journalctl --since today | grep -iE "earlyoom|oom-kill|killed process"
   (brak killa + dużo wolnej pamięci = NIE RAM)
3. Token/auth: mtime i expiresAt z ~/.claude/.credentials.json
   (uwaga: "401" w .jsonl to zwykle fałszywka — cyfry w timestampach)
4. Błąd API: szukaj wpisu isApiErrorMessage:true w dzienniku sesji
   ~/.claude/projects/<cwd-z-myślnikami>/<uuid>.jsonl
5. Zostaje crash wewnętrzny claude — skoreluj czas z backupem
   ~/.claude/backups/.claude.json.backup.<ms> (kolizja współbieżnych sesji).

Nie proponuj zmian w kodzie bez analizy i mojej zgody (zasada z CLAUDE.md).
```

---

## 🔁 Odzysk padłej sesji

```bash
claude --resume <uuid>          # uuid z hintu na ekranie ratunkowym
# przykład (crash 2026-06-17):
claude --resume 2b03a6c5-4deb-4381-a743-add1e7dbae2c
```

## Gdzie czego szukać (skrót)

| Co | Gdzie |
|----|-------|
| Zrzut czarnej skrzynki | `~/.claude-voice-assistant/crash-logs/crash-<agent>-<data>.log` |
| Dziennik sesji | `~/.claude/projects/<cwd-z-myślnikami>/<uuid>.jsonl` |
| OOM/earlyoom | `journalctl --since today \| grep -iE "earlyoom\|oom-kill"` |
| Token | `~/.claude/.credentials.json` (mtime + `expiresAt`) |
| Stan globalny / backup | `~/.claude.json`, `~/.claude/backups/.claude.json.backup.<ms>` |
