#!/usr/bin/env python3
"""Wstrzyknij wspólne górne menu do stron dyktowania i agentów + dodaj na stronie
dyktowania sekcję „Jak uruchomić dyktowanie". Idempotentne (pomija, gdy menu już jest).

Uruchom z katalogu packaging/web:  python3 inject-menu.py
"""
from pathlib import Path

HERE = Path(__file__).parent

MENU_CSS = """
    /* Górne menu nawigacyjne — wspólne dla wszystkich instrukcji */
    .topnav{position:sticky;top:0;z-index:90;background:rgba(20,8,40,.92);backdrop-filter:blur(8px);border-bottom:1px solid rgba(255,255,255,.12)}
    .topnav-inner{max-width:860px;margin:0 auto;display:flex;flex-wrap:wrap;gap:4px;padding:9px 132px 9px 14px}
    .topnav a{color:#e9d5ff;text-decoration:none;font-weight:700;font-size:.92rem;padding:8px 14px;border-radius:999px;white-space:nowrap;cursor:pointer}
    .topnav a:hover{background:rgba(255,255,255,.10);color:#fff}
    .topnav a.active{background:#a855f7;color:#fff}
"""

LABELS = {
    "pl": {"macos": "🍎 macOS", "linux": "🐧 Linux", "windows": "🪟 Windows",
           "dyktowanie": "🎙️ Dyktowanie", "agenci": "🤖 Agenci"},
    "en": {"macos": "🍎 macOS", "linux": "🐧 Linux", "windows": "🪟 Windows",
           "dyktowanie": "🎙️ Dictation", "agenci": "🤖 Agents"},
}


def build_menu(lang, active):
    suf = "-en" if lang == "en" else ""
    lab = LABELS[lang]
    items = []
    for os in ("macos", "linux", "windows"):
        items.append('      <a href="instrukcja-instalacja%s.html#%s">%s</a>' % (suf, os, lab[os]))
    for name in ("dyktowanie", "agenci"):
        cls = ' class="active"' if active == name else ""
        items.append('      <a href="instrukcja-%s%s.html"%s>%s</a>' % (name, suf, cls, lab[name]))
    return '  <nav class="topnav">\n    <div class="topnav-inner">\n%s\n    </div>\n  </nav>\n' % "\n".join(items)


# Nowa sekcja „Jak uruchomić dyktowanie" (wstawiana przed FAQ na stronie dyktowania).
DICT_SECTION = {
    "pl": """    <section class="panel">
      <h2><span class="num">5</span> Jak uruchomić dyktowanie w programie</h2>
      <p>Gdy klucz jest już wklejony, dyktowanie włączasz w dowolnej zakładce agenta —
        nie trzeba nic restartować:</p>
      <ol>
        <li>Wejdź w zakładkę agenta. W <b>dolnym pasku przycisków</b> (pod terminalem,
          obok pola, w które wpisujesz polecenia) znajdź okrągłą ikonę <b>🎙️ mikrofonu</b>
          (po najechaniu pokazuje podpowiedź „Dyktuj").</li>
        <li><b>Kliknij mikrofon raz</b>, żeby zacząć — przycisk <b>zostaje podświetlony</b>,
          co znaczy, że program słucha.</li>
        <li>Powiedz, co chcesz przekazać. Mów wyraźnie, w miarę cicho w tle;
          polski i angielski rozpoznają się automatycznie.</li>
        <li><b>Kliknij mikrofon ponownie</b>, żeby zakończyć. Po chwili Twoje słowa pojawią
          się jako <b>tekst w polu wpisywania</b> — możesz je poprawić i wysłać klawiszem
          <kbd>Enter</kbd>.</li>
      </ol>
      <div class="see"><b>Nie masz jeszcze klucza?</b> Jeśli klikniesz mikrofon, a klucz Groq
        nie jest wpisany, program najpierw poprosi o jego dodanie (patrz kroki 1–3 wyżej).</div>
      <div class="warn">⚠️ Dyktowanie uruchamia się <b>wyłącznie przyciskiem mikrofonu</b> —
        nie ma skrótu klawiszowego. Pierwsza zamiana głosu na tekst może chwilę potrwać,
        kolejne są szybsze.</div>
    </section>

""",
    "en": """    <section class="panel">
      <h2><span class="num">5</span> How to start dictation in the program</h2>
      <p>Once the key is pasted, you turn dictation on in any agent tab —
        no restart needed:</p>
      <ol>
        <li>Open an agent tab. In the <b>bottom button bar</b> (under the terminal, next to
          the field where you type commands) find the round <b>🎙️ microphone</b> icon
          (hovering shows the tooltip "Dictate").</li>
        <li><b>Click the microphone once</b> to start — the button <b>stays highlighted</b>,
          meaning the program is listening.</li>
        <li>Say what you want to pass on. Speak clearly, with little background noise;
          English and Polish are detected automatically.</li>
        <li><b>Click the microphone again</b> to finish. After a moment your words appear as
          <b>text in the input field</b> — you can edit them and send with <kbd>Enter</kbd>.</li>
      </ol>
      <div class="see"><b>No key yet?</b> If you click the microphone and the Groq key isn't
        entered, the program will first ask you to add it (see steps 1–3 above).</div>
      <div class="warn">⚠️ Dictation starts <b>only via the microphone button</b> — there is no
        keyboard shortcut. The first voice-to-text may take a moment; the next ones are faster.</div>
    </section>

""",
}

# Marker FAQ — przed nim wstawiamy nową sekcję.
FAQ_MARKER = {
    "pl": '    <section class="panel">\n      <h2>Najczęstsze pytania</h2>',
    "en": '    <section class="panel">\n      <h2>Frequently asked questions</h2>',
}


def inject(name, active):
    for lang in ("pl", "en"):
        suf = "-en" if lang == "en" else ""
        path = HERE / ("instrukcja-%s%s.html" % (name, suf))
        html = path.read_text(encoding="utf-8")
        if 'class="topnav"' in html:
            print("pomijam (menu już jest):", path.name)
            continue
        # 1) CSS menu przed </style>
        html = html.replace("  </style>", MENU_CSS + "  </style>", 1)
        # 2) pasek menu po przełączniku języka (przed <div class="wrap">)
        html = html.replace('  </details>\n  <div class="wrap">',
                            '  </details>\n' + build_menu(lang, active) + '  <div class="wrap">', 1)
        # 3) (tylko dyktowanie) nowa sekcja przed FAQ
        if name == "dyktowanie":
            html = html.replace(FAQ_MARKER[lang], DICT_SECTION[lang] + FAQ_MARKER[lang], 1)
        path.write_text(html, encoding="utf-8")
        print("zaktualizowano:", path.name)


def main():
    inject("dyktowanie", active="dyktowanie")
    inject("agenci", active="agenci")


if __name__ == "__main__":
    main()
