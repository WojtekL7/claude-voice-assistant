#!/usr/bin/env python3
"""Generator scalonej strony instalacji (macOS + Linux + Windows) z górnym menu.

Wyciąga sekcje (między </header> a <footer>) z istniejących stron per-system
i składa je w jedną stronę z zakładkami OS w górnym menu. Buduje wersję PL i EN.
Stare strony per-system zamienia w przekierowania na scaloną (kotwica #os).

Uruchom z katalogu packaging/web:  python3 build-instalacja.py
"""
import re
from pathlib import Path

HERE = Path(__file__).parent

# Wspólne górne menu (CSS współdzielony z dyktowaniem/agentami).
MENU_CSS = """
    /* Górne menu nawigacyjne — wspólne dla wszystkich instrukcji */
    .topnav{position:sticky;top:0;z-index:90;background:rgba(20,8,40,.92);backdrop-filter:blur(8px);border-bottom:1px solid rgba(255,255,255,.12)}
    .topnav-inner{max-width:860px;margin:0 auto;display:flex;flex-wrap:wrap;gap:4px;padding:9px 132px 9px 14px}
    .topnav a{color:#e9d5ff;text-decoration:none;font-weight:700;font-size:.92rem;padding:8px 14px;border-radius:999px;white-space:nowrap;cursor:pointer}
    .topnav a:hover{background:rgba(255,255,255,.10);color:#fff}
    .topnav a.active{background:#a855f7;color:#fff}
"""

# Etykiety pozycji menu per język.
LABELS = {
    "pl": {"macos": "🍎 macOS", "linux": "🐧 Linux", "windows": "🪟 Windows",
           "dyktowanie": "🎙️ Dyktowanie", "agenci": "🤖 Agenci"},
    "en": {"macos": "🍎 macOS", "linux": "🐧 Linux", "windows": "🪟 Windows",
           "dyktowanie": "🎙️ Dictation", "agenci": "🤖 Agents"},
}

OSES = ["macos", "linux", "windows"]


def suffix(lang):
    return "-en" if lang == "en" else ""


def build_menu(lang, active, on_install_page):
    """HTML górnego menu. Na stronie instalacji OS-y to kotwice (#os) tej samej
    strony; na innych stronach — pełne linki do scalonej strony."""
    suf = suffix(lang)
    lab = LABELS[lang]
    items = []
    for os in OSES:
        href = "#%s" % os if on_install_page else "instrukcja-instalacja%s.html#%s" % (suf, os)
        cls = ' class="active"' if active == os else ""
        idattr = ' id="tab-%s"' % os if on_install_page else ""
        items.append('      <a href="%s"%s%s>%s</a>' % (href, idattr, cls, lab[os]))
    # Dyktowanie + Agenci — zawsze pełne linki.
    for name in ("dyktowanie", "agenci"):
        href = "instrukcja-%s%s.html" % (name, suf)
        cls = ' class="active"' if active == name else ""
        items.append('      <a href="%s"%s>%s</a>' % (href, cls, lab[name]))
    return '  <nav class="topnav">\n    <div class="topnav-inner">\n%s\n    </div>\n  </nav>\n' % "\n".join(items)


def extract_sections(html):
    """Treść między </header> a <footer> (same sekcje, bez nagłówka i stopki)."""
    start = html.index("</header>") + len("</header>")
    end = html.index("<footer>", start)
    return html[start:end].strip()


def localize_ids(sec, os):
    """Uczyń identyfikatory unikalnymi w obrębie panelu OS (prefiks `{os}__`).

    Trzy strony OS używają tych samych id (cz1..cz5 sekcji + npmcmd/nodecmd…
    przy przyciskach Kopiuj). Po scaleniu kolidowałyby (getElementById bierze
    pierwszy → Linux/Windows kopiowałyby komendę macOS, kotwice TOC myliłyby się).
    Prefiksujemy: definicje id, kotwice #fragment i argument copyCmd('id')."""
    sec = re.sub(r'id="([^"]+)"', lambda m: 'id="%s__%s"' % (os, m.group(1)), sec)
    sec = re.sub(r'href="#([^"]+)"', lambda m: 'href="#%s__%s"' % (os, m.group(1)), sec)
    sec = re.sub(r"copyCmd\('([^']+)'", lambda m: "copyCmd('%s__%s'" % (os, m.group(1)), sec)
    return sec


def extract_style(html):
    """Blok wewnątrz <style>…</style> (bez samych tagów)."""
    m = re.search(r"<style>(.*?)</style>", html, re.S)
    return m.group(1)


def lang_switch(lang, this_file):
    """Przełącznik języka — link do drugiej wersji tego samego pliku."""
    other = "en" if lang == "pl" else "pl"
    other_file = this_file.replace("-en", "") if lang == "en" else this_file.replace(".html", "-en.html")
    cur_label = "English" if lang == "en" else "Polski"
    summary = "🌐 English ▾" if lang == "en" else "🌐 Polski ▾"
    a_en = '<a href="%s"%s>English</a>' % (
        (this_file if lang == "en" else other_file), ' class="active"' if lang == "en" else "")
    a_pl = '<a href="%s"%s>Polski</a>' % (
        (this_file if lang == "pl" else other_file), ' class="active"' if lang == "pl" else "")
    if lang == "en":
        menu = "%s\n      %s" % (a_en, a_pl)
    else:
        menu = "%s\n      %s" % (a_en, a_pl)
    return ('  <details class="lang-switch">\n    <summary>%s</summary>\n'
            '    <div class="lang-menu">\n      %s\n    </div>\n  </details>\n'
            % (summary, menu))


def build_install_page(lang):
    suf = suffix(lang)
    # Style bierzemy z Linuksa (nadzbiór), dokładamy CSS menu.
    linux_html = (HERE / ("instrukcja-linux%s.html" % suf)).read_text(encoding="utf-8")
    style = extract_style(linux_html) + MENU_CSS
    panels = []
    for os in OSES:
        page = (HERE / ("instrukcja-%s%s.html" % (os, suf))).read_text(encoding="utf-8")
        sections = localize_ids(extract_sections(page), os)
        display = "block" if os == "macos" else "none"
        panels.append('    <div class="os-panel" id="panel-%s" style="display:%s">\n%s\n    </div>'
                      % (os, display, sections))
    panels_html = "\n".join(panels)

    if lang == "en":
        title = "Full install guide — macOS, Linux, Windows | Claude Voice Assistant"
        desc = "Step-by-step install guide for Claude Voice Assistant on macOS, Linux and Windows, plus dictation — explained for everyone."
        h1 = "Full install guide"
        tagline = "Pick your system in the top menu. Everything explained step by step, so anyone can do it — no technical knowledge needed."
        back = "← Back to the download page"
    else:
        title = "Pełna instrukcja instalacji — macOS, Linux, Windows | Claude Voice Assistant"
        desc = "Instrukcja instalacji Claude Voice Assistant krok po kroku na macOS, Linuksie i Windows, plus dyktowanie — wytłumaczone dla każdego."
        h1 = "Pełna instrukcja instalacji"
        tagline = "Wybierz swój system w górnym menu. Wszystko krok po kroku, tak żeby zrozumiał każdy — bez wiedzy technicznej."
        back = "← Wróć do strony pobierania"

    this_file = "instrukcja-instalacja%s.html" % suf
    menu = build_menu(lang, active="macos", on_install_page=True)
    langsw = lang_switch(lang, this_file)
    html_lang = "en" if lang == "en" else "pl"

    js = """
  <script>
    // Górne menu macOS/Linux/Windows = zakładki na tej samej stronie (kotwica #os).
    var PANELS = ['macos','linux','windows'];
    function showOS(os){
      if (PANELS.indexOf(os) === -1) os = 'macos';
      PANELS.forEach(function(p){
        document.getElementById('panel-'+p).style.display = (p===os)?'block':'none';
        var t = document.getElementById('tab-'+p);
        if (t) t.classList.toggle('active', p===os);
      });
    }
    // Reagujemy TYLKO na hashe systemów (#macos/#linux/#windows). Kotwice
    // wewnątrz strony (TOC: #macos__cz1) przepuszczamy do przewijania przeglądarki.
    function hashOS(){ var h = (location.hash || '').replace('#',''); return PANELS.indexOf(h) !== -1 ? h : null; }
    window.addEventListener('hashchange', function(){ var o = hashOS(); if (o) { showOS(o); window.scrollTo(0,0); } });
    showOS(hashOS() || 'macos');

    // Kopiowanie komend (przeniesione 1:1 ze stron OS; działa też na http przez execCommand).
    function copyCmd(id, btn) {
      var text = document.getElementById(id).textContent;
      function done(){ var t = btn.textContent; btn.textContent = "✓"; setTimeout(function(){ btn.textContent = t; }, 1500); }
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done);
      } else {
        var ta = document.createElement("textarea");
        ta.value = text; document.body.appendChild(ta); ta.select();
        document.execCommand("copy"); document.body.removeChild(ta); done();
      }
    }
  </script>"""

    return """<!DOCTYPE html>
<html lang="{html_lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <style>{style}</style>
</head>
<body>
{langsw}{menu}  <div class="wrap">
    <header>
      <div class="logo">📦</div>
      <h1>{h1}</h1>
      <p class="tagline">{tagline}</p>
      <a class="back" href="https://pobierz.srv1251441.hstgr.cloud/">{back}</a>
    </header>

{panels}

    <footer>
      <p><a href="https://pobierz.srv1251441.hstgr.cloud/">{back}</a></p>
      <p>Claude Voice Assistant • kontakt@fulfillment-polska.pl</p>
    </footer>
  </div>
{js}
</body>
</html>
""".format(html_lang=html_lang, title=title, desc=desc, style=style, langsw=langsw,
           menu=menu, h1=h1, tagline=tagline, back=back, panels=panels_html, js=js)


def build_redirect(os, lang):
    suf = suffix(lang)
    target = "instrukcja-instalacja%s.html#%s" % (suf, os)
    html_lang = "en" if lang == "en" else "pl"
    msg = ("This guide has been merged. Taking you to the " if lang == "en"
           else "Ta instrukcja została scalona. Przenoszę Cię na ")
    linktext = "new page" if lang == "en" else "nową stronę"
    return """<!DOCTYPE html>
<html lang="{hl}">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url={target}">
  <link rel="canonical" href="{target}">
  <title>→ instrukcja instalacji</title>
</head>
<body>
  <p>{msg}<a href="{target}">{linktext}</a>…</p>
  <script>location.replace("{target}");</script>
</body>
</html>
""".format(hl=html_lang, target=target, msg=msg, linktext=linktext)


def main():
    for lang in ("pl", "en"):
        suf = suffix(lang)
        out = HERE / ("instrukcja-instalacja%s.html" % suf)
        out.write_text(build_install_page(lang), encoding="utf-8")
        print("zapisano", out.name)
        for os in OSES:
            r = HERE / ("instrukcja-%s%s.html" % (os, suf))
            r.write_text(build_redirect(os, lang), encoding="utf-8")
            print("  przekierowanie", r.name, "->", "instrukcja-instalacja%s.html#%s" % (suf, os))


if __name__ == "__main__":
    main()
