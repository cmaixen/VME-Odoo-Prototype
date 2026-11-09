"""Record the demo video: the ten-minute scenario of docs/demo.md, plus blocks D and E.

Runs in the recorder container (see record.sh), against the video database with the drafts
of prepare.py already in it. Each segment is one browser context with its own WebM; make_video.py
joins them into the MP4. Captions and a visible pointer are drawn in the page by overlay.js.

    python3 tools/demo_video/record.py --out build/demo_video/raw
    python3 tools/demo_video/record.py --out build/demo_video/shots --shots --speed 0.2   # quick check

Nothing in here sends anything: every outward action in the scenario stays a draft.
"""
import argparse
import html
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = os.environ.get("ODOO_URL", "http://odoo:8069").rstrip("/")
DB = os.environ.get("ODOO_DB", "vme_video")
SIZE = {"width": 1920, "height": 1080}
OVERLAY = (HERE / "overlay.js").read_text()

# The fictitious owner of Linde A1 from the demo data (docs/demo.md, step 8).
OWNER_LOGIN = "eigenaar.linde.a1@example.com"
OWNER_PASSWORD = "portaal-demo"


class Recorder:
    """One page with slow, visible actions: the pointer glides to an element before each click."""

    def __init__(self, page, speed, shots_dir=None, voice=None):
        self.page = page
        self.speed = speed
        self.shots_dir = shots_dir
        self.shot_no = 0
        self.label = ""
        # Voice-over (voice.py): caption -> clip. The recording waits for each clip to finish
        # before the next caption, and the timeline tells make_video.py where to put the clips.
        self.voice = voice or {}
        self.timeline = []
        self.t0 = time.time()
        self.voice_until = 0.0
        self.mark = None

    def apply_mark(self):
        """The sync marker of overlay.js; put back after a page load on another origin."""
        if self.mark is not None:
            self.page.evaluate("(n) => window.__vmeMark && window.__vmeMark(n)", self.mark)

    def wait_voice(self, extra=0.0):
        rest = self.voice_until + extra - time.time()
        if rest > 0:
            self.page.wait_for_timeout(int(rest * 1000))

    def speak(self, key):
        """Start the clip of `key` now (in video time), if there is one."""
        clip = self.voice.get(key)
        if clip:
            self.mark = len(self.timeline)
            self.apply_mark()
            now = time.time()
            self.timeline.append({"t": round(now - self.t0, 3), "key": key, "file": clip["file"],
                                  "duration": clip["duration"]})
            self.voice_until = now + clip["duration"] + 0.35

    # -- timing and captions -------------------------------------------------------------
    def hold(self, seconds, shot=None):
        if self.shots_dir and shot:
            self.shot(shot)
        self.page.wait_for_timeout(int(seconds * 1000 * self.speed))

    def shot(self, name):
        self.shot_no += 1
        self.page.screenshot(path=str(self.shots_dir / f"{self.shot_no:03d}_{name}.png"))

    def chapter(self, label):
        """A new step: the band shows only its title, so the last sentence of the previous step
        does not come back from sessionStorage after the next page load."""
        self.wait_voice(0.3)
        self.label = label
        self.page.evaluate("(c) => { try { sessionStorage.setItem('vmeCaption', c); } catch (e) {} "
                           "window.__vmeSetCaption && window.__vmeSetCaption(c); }",
                           f'<span class="step">{html.escape(label)}</span>')

    def say(self, text, seconds=0, shot=None):
        """Caption band: the step in small capitals, then the sentence (the "Zeg:" line or a hint)."""
        content = f'<span class="step">{html.escape(self.label)}</span>{html.escape(text)}' if text else ""
        if text:
            self.wait_voice()  # let the previous sentence finish before the caption changes
        self.page.evaluate("(c) => window.__vmeSetCaption && window.__vmeSetCaption(c)", content)
        self.speak(text)
        if seconds:
            self.hold(seconds, shot or self.label.split(" ")[0])

    def ensure_overlay(self):
        self.page.evaluate(OVERLAY)

    # -- navigation ----------------------------------------------------------------------
    def goto(self, path):
        self.page.goto(BASE + path)
        self.settle()

    def settle(self):
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            pass  # Odoo's bus keeps a long poll open; the page is usable anyway
        self.page.wait_for_timeout(400)
        self.apply_mark()

    def action(self, xmlid, suffix=""):
        self.goto(f"/odoo/action-{xmlid}{suffix}")

    # -- pointer -------------------------------------------------------------------------
    def point(self, locator, pause=0.6):
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        if box:
            self.page.mouse.move(box["x"] + min(box["width"] / 2, 60), box["y"] + box["height"] / 2,
                                 steps=max(8, int(25 * self.speed)))
        self.hold(pause)

    def click(self, locator, pause=0.5, settle=True):
        locator = locator.first
        locator.wait_for(state="visible", timeout=20000)
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        low = box and box["y"] + box["height"] > SIZE["height"] - 190
        if low:  # the caption band would hide the button: fade it while clicking
            self.page.evaluate("() => window.__vmeDimCaption && window.__vmeDimCaption(true)")
        self.point(locator, pause)
        locator.click()
        if settle:
            self.settle()
        if low:
            self.page.evaluate("() => window.__vmeDimCaption && window.__vmeDimCaption(false)")

    def highlight(self, locator, seconds=3.5):
        """Orange frame around what the caption talks about."""
        locator = locator.first
        locator.scroll_into_view_if_needed()
        locator.evaluate(
            """(el, ms) => {
                if (el.tagName === 'TR') {  // outlines on table rows draw only partly: colour the cells
                    const cells = [...el.children];
                    cells.forEach(c => { c.dataset.vmeBg = c.style.background; c.style.background = '#fde7b8'; });
                    setTimeout(() => cells.forEach(c => { c.style.background = c.dataset.vmeBg; }), ms);
                    return;
                }
                el.style.outline = '4px solid #e8a33d';
                el.style.outlineOffset = '4px';
                el.style.borderRadius = '6px';
                setTimeout(() => { el.style.outline = ''; el.style.outlineOffset = ''; }, ms);
            }""",
            int(seconds * 1000 * max(self.speed, 0.3)),
        )
        self.point(locator, 0.2)

    def scroll(self, pixels, steps=6):
        for _ in range(steps):
            self.page.mouse.wheel(0, pixels / steps)
            self.page.wait_for_timeout(60)
        self.hold(0.4)

    def text(self, value, exact=False):
        return self.page.get_by_text(value, exact=exact)


# -- static pages (title card, terminal, PDF pages) ---------------------------------------
CARD_CSS = """
    html, body { margin: 0; height: 100%; }
    body { display: flex; align-items: center; justify-content: center; flex-direction: column;
           background: radial-gradient(circle at 30% 20%, #2f4a63, #141c26 70%); color: #fff;
           font-family: "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; text-align: center; }
    h1 { font-size: 84px; margin: 0 0 18px; letter-spacing: -0.01em; }
    h2 { font-size: 38px; font-weight: 400; margin: 0 0 56px; color: #c9d6e2; }
    p { font-size: 26px; color: #f2c46d; margin: 6px 0; }
    small { position: absolute; bottom: 48px; font-size: 20px; color: #8fa3b5; }
"""


def title_card(rec, title, subtitle, lines, footer, seconds, voice=None):
    rec.wait_voice(0.3)  # the last sentence of the previous step ends before the card appears
    body = "".join(f"<p>{html.escape(line)}</p>" for line in lines)
    rec.page.set_content(
        f"<html><head><style>{CARD_CSS}</style></head><body><h1>{html.escape(title)}</h1>"
        f"<h2>{html.escape(subtitle)}</h2>{body}<small>{html.escape(footer)}</small></body></html>"
    )
    rec.ensure_overlay()
    rec.apply_mark()
    rec.say("")
    rec.page.mouse.move(1900, 1070)
    rec.hold(0.6)
    if voice:
        rec.speak(voice)
    rec.hold(seconds, "titel")
    rec.wait_voice(0.5)


def terminal_page(rec, command, output_lines):
    """A terminal window: the command is typed, then the real output of the script appears line by line."""
    rec.page.set_content(f"""<html><head><style>
        body {{ margin: 0; height: 100vh; background: #1d2733; display: flex; align-items: center;
               justify-content: center; font-family: Menlo, "DejaVu Sans Mono", monospace; }}
        .win {{ width: 1500px; height: 640px; background: #0f1419; border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0,0,0,.5); overflow: hidden; margin-bottom: 140px; }}
        .bar {{ height: 40px; background: #2b333c; display: flex; align-items: center; padding: 0 16px;
                color: #9aa7b3; font: 16px sans-serif; }}
        .dot {{ width: 14px; height: 14px; border-radius: 50%; margin-right: 8px; }}
        pre {{ margin: 0; padding: 26px 30px; color: #d8e1e8; font-size: 22px; line-height: 1.5;
               white-space: pre-wrap; }}
        .p {{ color: #7fd88f; }} .o {{ color: #f2c46d; }}
    </style></head><body><div class="win"><div class="bar">
        <span class="dot" style="background:#ff5f56"></span><span class="dot" style="background:#ffbd2e"></span>
        <span class="dot" style="background:#27c93f"></span>&nbsp;&nbsp;syndicus@kantoor: ~/ai</div>
        <pre id="t"><span class="p">~/ai $</span> </pre></div></body></html>""")
    rec.ensure_overlay()
    rec.page.mouse.move(1880, 1060)
    rec.hold(1)
    for char in command:
        rec.page.evaluate("(c) => document.getElementById('t').append(c)", char)
        rec.page.wait_for_timeout(int(45 * rec.speed) + 5)
    rec.hold(0.8)
    rec.page.evaluate("() => document.getElementById('t').append('\\n')")
    for line in output_lines:
        rec.page.evaluate(
            """(l) => { const s = document.createElement('span'); s.className = 'o';
                        s.textContent = l + '\\n'; document.getElementById('t').append(s); }""",
            line,
        )
        rec.hold(0.35)


def pdf_pages_page(rec, title, images):
    """Chromium headless shows no PDF viewer: show the pages of the downloaded PDF as images."""
    imgs = "".join(f'<img src="data:image/png;base64,{data}">' for data in images)
    rec.page.set_content(f"""<html><head><style>
        body {{ margin: 0; background: #525659; font-family: sans-serif; }}
        .bar {{ position: sticky; top: 0; height: 52px; background: #323639; color: #fff; display: flex;
                align-items: center; padding: 0 24px; font-size: 18px; z-index: 2; }}
        .pages {{ display: flex; flex-direction: column; align-items: center; gap: 24px; padding: 24px 0 220px; }}
        img {{ width: 1000px; box-shadow: 0 4px 16px rgba(0,0,0,.5); background: #fff; }}
    </style></head><body><div class="bar">{html.escape(title)}</div><div class="pages">{imgs}</div></body></html>""")
    rec.ensure_overlay()


# -- login ---------------------------------------------------------------------------------
def login_state(browser, login, password, path):
    """Log in outside the recording and keep the session cookie for the recorded context."""
    context = browser.new_context(viewport=SIZE)
    page = context.new_page()
    page.goto(f"{BASE}/web/login?db={DB}")
    page.fill("#login", login)
    page.fill("#password", password)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    if "/web/login" in page.url:
        # The first login after building the database sometimes answers 400: try once more.
        page.goto(f"{BASE}/web/login")
        page.fill("#login", login)
        page.fill("#password", password)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
    context.storage_state(path=str(path))
    context.close()


def load_voice():
    """The clips of voice.py, if they were generated; without them the video is silent."""
    manifest = ROOT / "build/demo_video/voice/manifest.json"
    return json.loads(manifest.read_text()) if manifest.exists() else {}


def new_segment(browser, args, name, state):
    options = {"viewport": SIZE, "storage_state": str(state), "locale": "nl-BE", "timezone_id": "Europe/Brussels",
               "accept_downloads": True}
    if not args.shots:
        options.update(record_video_dir=str(args.out / name), record_video_size=SIZE)
    context = browser.new_context(**options)
    context.add_init_script(OVERLAY)
    page = context.new_page()
    page.set_default_timeout(20000)
    voice = None if args.shots else load_voice()
    return context, Recorder(page, args.speed, args.out if args.shots else None, voice)


def run_ai(*cmd):
    env = dict(os.environ, ODOO_URL=BASE, ODOO_DB=DB)
    result = subprocess.run([sys.executable, *cmd], cwd=ROOT / "ai", env=env, capture_output=True, text=True)
    print(result.stdout, result.stderr, flush=True)
    if result.returncode:
        raise SystemExit(f"{cmd} mislukt")
    return [line for line in result.stdout.splitlines() if line.strip()]


# -- the scenario --------------------------------------------------------------------------
def select_company(rec, name):
    """Switch the active company (top right), as the presenter does before step 3."""
    rec.click(rec.page.locator(".o_switch_company_menu button, .o_switch_company_menu .dropdown-toggle"))
    item = rec.page.locator(".o_switch_company_item, .dropdown-item", has_text=name)
    rec.click(item.locator(".o_switch_company_item_label, span", has_text=name).first if item.count() else item)
    rec.page.wait_for_timeout(1500)
    rec.settle()


def step1_worklist(rec):
    rec.chapter("Stap 1 van 8 · Uw dag in één lijst")
    rec.action("vme_belgie.vme_work_item_server_action")
    rec.page.mouse.move(1500, 100)
    rec.say("Mijn werk vandaag: wat te laat is, vandaag of deze week vervalt, over alle gebouwen heen.", 4)
    rec.highlight(rec.page.locator("tr.o_group_header", has_text="Vandaag"))
    rec.highlight(rec.page.locator("tr.o_data_row", has_text="Lek of waterschade (A4)"), 4)
    rec.say("Vannacht mailde de eigenaar van A4 over een lek. De AI-assistent zette een antwoord klaar.", 4)
    rec.scroll(700)
    row = rec.page.locator("tr.o_data_row", has_text="Keuring plannen: Lift blok A")
    rec.highlight(row, 4)
    rec.say("Deze week: de keuring van de lift in blok A plannen. Onthoud die voor stap 3.", 4)
    concept = rec.page.locator("tr.o_data_row .badge", has_text="Concept")
    rec.highlight(concept.nth(0), 4)
    rec.say("Uw dag begint met één lijst over al uw gebouwen, en alles wat naar buiten moet, "
            "staat klaar als concept.", 6)
    rec.scroll(-700)


def step2_leak(rec):
    rec.chapter("Stap 2 van 8 · Een eigenaar mailt een lek")
    row = rec.page.locator("tr.o_data_row", has_text="Lek of waterschade (A4)")
    rec.click(row.get_by_text("Openen"))
    rec.hold(1)
    proposal = rec.page.locator(".o-mail-Activity", has_text="Lek of waterschade (A4)")
    rec.say("De mail staat bij de juiste VME: Residentie Linde, kavel A4, onderwerp lek, dringend.", 1)
    rec.highlight(proposal.locator("li", has_text="Kavel"), 4)
    rec.hold(3, "lek_koppeling")
    rec.highlight(proposal.get_by_text("Voorgesteld antwoord, nog niet verstuurd"), 4)
    rec.say("Het voorstel van de AI-assistent: nog niet verstuurd. Uw medewerker kijkt het na.", 4)
    panel = rec.page.locator(".o-mail-Chatter, .o-mail-ChatterContainer").first
    draft = proposal.get_by_text("Conceptantwoord").first
    draft.scroll_into_view_if_needed()
    rec.point(draft)
    rec.highlight(proposal.get_by_text("Schadedossier 1 aangemaakt", exact=False), 4)
    rec.say("Er staat al een schadedossier klaar, en het antwoord vertelt wat de eigenaar intussen kan doen.", 5)
    original = proposal.get_by_text("Oorspronkelijke mail", exact=False).first
    original.scroll_into_view_if_needed()
    rec.point(original, 1)
    rec.say("De AI leest de mail, vindt het gebouw en de kavel en schrijft een antwoord; "
            "uw medewerker beslist en verstuurt.", 6, "lek_zeg")
    del panel


def step3_invoice(rec):
    rec.chapter("Stap 3 van 8 · Een leverancier mailt een factuur")
    output = run_ai("facturen_mailgate.py", "--inbox", "demo_inbox")
    terminal_page(rec, "python facturen_mailgate.py --inbox demo_inbox", output)
    rec.say("De Keuringsdienst mailt de factuur van de liftinspectie naar het factuuradres van Residentie Linde.", 5,
            "factuur_terminal")
    rec.action("account.action_move_in_invoice_type")
    rec.say("Leveranciersfacturen staan per gebouw: rechtsboven kiezen we Residentie Linde.", 1)
    select_company(rec, "Residentie Linde")
    rec.action("account.action_move_in_invoice_type")
    rec.say("Facturatie > Leveranciers: de factuur staat er als concept.", 1)
    rec.click(rec.page.locator("tr.o_data_row", has_text="KD-2026-1105"))
    rec.hold(1)
    rec.say("Leverancier, bedrag en btw komen uit de Peppol-e-factuur in bijlage; "
            "de verdeelregel koos de liftsleutel.", 1)
    key = rec.page.locator(".o_field_widget[name='invoice_line_ids'] td", has_text="Liftsleutel")
    if key.count():
        rec.highlight(key, 4)
    rec.hold(4, "factuur_concept")
    rec.say("Eén klik op Bevestigen: geboekt en verdeeld.", 1)
    rec.click(rec.page.locator(".o_form_statusbar button[name='action_post']"))
    rec.hold(1.5)
    smart = rec.page.locator(".o_control_panel button, .oe_button_box button", has_text="Verdeling")
    rec.highlight(smart, 3)
    rec.click(smart)
    rec.hold(1)
    rec.say("Verdeeld over 12 eigenaars: alleen de appartementen, want garages gebruiken de lift niet.", 5,
            "factuur_verdeeld")
    rec.click(rec.page.locator(".o_breadcrumb a, .breadcrumb-item a").last)
    rec.hold(1)
    rec.page.mouse.move(600, 600)
    message = rec.page.locator(".o-mail-Message", has_text="Keuring van")
    if message.count():
        message.first.scroll_into_view_if_needed()
        rec.highlight(message, 5)
    rec.say("In de historiek: automatisch verdeeld, en de keuring van de lift geregistreerd, "
            "met de volgende keuring al in de agenda.", 5, "factuur_historiek")
    rec.action("vme_belgie.vme_work_item_server_action")
    rec.scroll(700)
    rec.say("Eén mail van een leverancier: geboekt, verdeeld over de juiste eigenaars, en uw keuringsagenda "
            "is bijgewerkt. U klikte één keer.", 6, "factuur_zeg")
    rec.scroll(-700)


def step4_quotes(rec):
    rec.chapter("Stap 4 van 8 · Drie offertes, door de AI naast elkaar gelegd")
    rec.action("vme_belgie.vme_works_comparison_action")
    rec.click(rec.page.locator("tr.o_data_row", has_text="Gevelrenovatie"))
    rec.hold(1)
    rec.say("De AI las de drie offertes voor de gevel. De aandachtspunten staan in het geel.", 1)
    warn = rec.page.locator(".alert-warning").first
    if warn.count():
        rec.highlight(warn, 5)
    rec.hold(5, "offertes_aandacht")
    table = rec.page.locator("table", has_text="(p.").last
    if table.count():
        table.scroll_into_view_if_needed()
        rec.point(table, 1)
        rec.say("Bij elk getal de bron: het paginanummer in de offerte.", 5, "offertes_tabel")
    rec.say("Een avond offertes naast elkaar leggen wordt tien minuten nakijken, met de bron bij elk getal. "
            "De AV kiest; wij zetten de feiten klaar.", 7, "offertes_zeg")


def pick_tags(rec, field, names):
    """Fill a many2many-tags field by typing and choosing from the dropdown, like a user."""
    for name in names:
        box = rec.page.locator(f".modal .o_field_widget[name='{field}'] input")
        rec.click(box, settle=False)
        box.press_sequentially(name, delay=int(60 * rec.speed) + 5)
        rec.page.wait_for_timeout(700)
        rec.click(rec.page.locator(".o-autocomplete--dropdown-item", has_text=name), pause=0.3, settle=False)
        rec.page.wait_for_timeout(500)


def set_field(rec, field, value, scope=".modal"):
    box = rec.page.locator(f"{scope} .o_field_widget[name='{field}'] input").first
    rec.click(box, settle=False)
    box.select_text()
    box.press_sequentially(str(value), delay=int(80 * rec.speed) + 5)
    # Blur instead of Tab: Tab would open the date picker of the next field.
    box.evaluate("e => { e.dispatchEvent(new Event('change', {bubbles: true})); e.blur(); }")
    rec.page.wait_for_timeout(800)


def step5_provisions(rec):
    rec.chapter("Stap 5 van 8 · Provisies 2027 voor alle gebouwen")
    rec.action("vme_belgie.vme_provision_call_action")
    rec.say("Provisieoproepen: één wizard voor alle gebouwen tegelijk.", 1.5)
    rec.click(rec.page.get_by_role("button", name="Nieuwe provisieoproep"))
    rec.page.locator(".modal").wait_for()
    pick_tags(rec, "association_ids", ["Residentie Linde", "Hof ter Beuken", "Kaaihuis"])
    set_field(rec, "year", 2027)
    set_field(rec, "number", 1)
    rec.say("Budgetjaar 2027, oproep 1. Het voorbeeld toont per VME het werk- en het reservekapitaal.", 4,
            "provisies_voorbeeld")
    warning = rec.page.locator(".modal .o_field_widget[name='preview_html'] .alert, "
                               ".modal .o_field_widget[name='preview_html'] .text-warning, "
                               ".modal .o_field_widget[name='preview_html'] .text-danger")
    if warning.count():
        rec.highlight(warning, 5)
    rec.say("Bij Hof ter Beuken waarschuwt het systeem: het reservekapitaal zit onder de wettelijke 5% "
            "van de lasten van vorig jaar.", 5, "provisies_5pct")
    rec.click(rec.page.locator(".modal-footer button", has_text="Maak provisieoproepen"))
    rec.page.wait_for_timeout(2000)
    rec.settle()
    rec.say("Per eigenaar een oproep voor werkkapitaal en een voor reservekapitaal, elk met de eigen "
            "bankrekening en een gestructureerde mededeling.", 5, "provisies_resultaat")
    rec.say("Uw kwartaaloproep voor tweehonderd gebouwen is één wizard, en de 5%-regel bewaakt zichzelf.", 6,
            "provisies_zeg")


def step6_assemblies(rec):
    rec.chapter("Stap 6 van 8 · De AV's van 2027 plannen")
    rec.action("vme_belgie.vme_assembly_planner_wizard_action")
    rec.page.locator(".modal").wait_for()
    set_field(rec, "year", 2027)
    rec.say("De AV-planner deelt het hele AV-seizoen in, zonder dubbel geboekte zaal of medewerker.", 3,
            "av_planner")
    rec.click(rec.page.locator(".modal-footer button", has_text="Indeling voorstellen"))
    rec.page.wait_for_timeout(1500)
    rec.settle()
    rec.say("Elke AV binnen haar wettelijke periode van vijftien dagen. Alles staat op Voorgesteld: "
            "bevestigen doet uw medewerker.", 6, "av_resultaat")
    rec.say("Uw AV-seizoen in één voorstel, binnen elke wettelijke termijn, en wie niet kan komen, stemt online.",
            6, "av_zeg")


def step7_statement(rec):
    rec.chapter("Stap 7 van 8 · De jaarafrekening 2026")
    rec.action("vme_belgie.vme_association_action")
    rec.click(rec.page.locator(".o_data_row, .o_kanban_record", has_text="Residentie Linde"))
    rec.click(rec.page.get_by_role("button", name="Jaarafrekening", exact=True))
    modal = rec.page.locator(".modal")
    modal.wait_for()
    rec.page.wait_for_timeout(1500)
    preview = modal.locator(".o_field_widget[name='preview_html']")
    check = preview.locator(".alert").first
    if check.count():
        rec.highlight(check, 5)
    rec.say("De controle: de som van alle aandelen is gelijk aan de geboekte kosten, "
            "inclusief de liftfactuur van daarnet.", 5, "afrekening_controle")
    a1 = preview.locator("tr", has_text="Eigenaar Linde A1").first
    if a1.count():
        rec.highlight(a1, 5)
    rec.say("Eigenaar Linde A1 krijgt geld terug, A3 heeft nog provisies open staan.", 4, "afrekening_a1")
    a5 = preview.locator("tr", has_text="Linde A5")
    if a5.count():
        for i in range(a5.count()):
            rec.highlight(a5.nth(i), 6)
        rec.say("A5 werd op 1 juli verkocht: verkoper en koper krijgen elk hun eigen afrekening, "
                "pro rata hun dagen.", 5, "afrekening_a5")
    with rec.page.expect_download(timeout=120000) as info:
        rec.click(modal.locator(".modal-footer button", has_text="Afdrukken (PDF)"), settle=False)
    pdf = info.value.path()
    show_pdf(rec, pdf, "Jaarafrekening 2026 - Residentie Linde.pdf")
    rec.say("De PDF per eigenaar: kosten per sleutel, provisies, saldo, het reservekapitaal apart "
            "en het detail per factuur.", 5, "afrekening_pdf")
    rec.scroll(900, steps=12)
    rec.hold(3)
    rec.say("De afrekening die u nu een week kost, staat klaar zodra de laatste factuur geboekt is, tot op de cent "
            "en ook bij een verkoop midden in het jaar.", 7, "afrekening_zeg")


def show_pdf(rec, path, title, pages=2):
    import base64

    import fitz  # PyMuPDF

    doc = fitz.open(path)
    images = [base64.b64encode(doc[i].get_pixmap(dpi=110).tobytes("png")).decode() for i in range(min(pages, len(doc)))]
    pdf_pages_page(rec, title, images)
    rec.page.mouse.move(1500, 500)
    rec.hold(1)


def step8_portal(rec):
    rec.chapter("Stap 8 van 8 · De eigenaar ziet zijn afrekening")
    rec.goto("/my")
    rec.say("Het portaal van Eigenaar Linde A1, op zijn eigen computer.", 3, "portaal_home")
    rec.click(rec.page.locator("a", has_text="Mijn mede-eigendom").first)
    rec.click(rec.page.locator("a", has_text="Residentie Linde").first)
    rec.say("Zijn kavels A1 en G1, de volgende AV met de agenda, de stand van werk- en reservekapitaal "
            "en de provisies, ook de nieuwe oproep van 2027.", 6, "portaal_vme")
    rec.scroll(700, steps=10)
    rec.hold(3)
    rec.scroll(700, steps=10)
    rec.hold(3)
    link = rec.page.locator("a", has_text="Jaarafrekening 2026")
    rec.click(link)
    rec.say("Jaarafrekening 2026, voorlopig: het saldo in zijn voordeel.", 4, "portaal_afrekening")
    rec.scroll(1200, steps=14)
    invoice = rec.page.locator("tr", has_text="KD-2026-1105")
    if invoice.count():
        rec.highlight(invoice, 5)
    rec.say("En onderaan zijn aandeel in de liftfactuur van Keuringsdienst Voorbeeld vzw: "
            "de mail van de leverancier van daarnet.", 5, "portaal_lift")
    rec.say("Van de mail van de leverancier tot de afrekening bij de eigenaar: niemand heeft iets overgetikt, "
            "en niets is vertrokken zonder een klik van uw medewerker.", 7, "portaal_zeg")


def block_d_closing(rec):
    rec.chapter("Extra · Het boekjaar afsluiten")
    rec.action("vme_belgie.vme_association_action")
    rec.click(rec.page.locator(".o_data_row, .o_kanban_record", has_text="Residentie Linde"))
    rec.click(rec.page.get_by_role("button", name="Boekjaar afsluiten", exact=True))
    rec.hold(1)
    set_field(rec, "year", 2026, scope=".o_form_view")
    rec.click(rec.page.locator(".o_form_button_save"))
    rec.hold(1)
    rec.say("Boekjaar 2026 van Residentie Linde: de controles tonen wat nog ontbreekt, "
            "hier een leveranciersfactuur in concept.", 5, "afsluiting_controles")
    draft = rec.page.locator(".o_form_view a", has_text="Concept factuur")
    if draft.count():
        closing_url = rec.page.url
        # The link opens a new tab; keep it in this tab so it stays in the recording.
        draft.first.evaluate("a => a.removeAttribute('target')")
        rec.click(draft)
        rec.hold(1)
        rec.say("Eén klik op de link: de factuur nakijken en bevestigen.", 2)
        rec.click(rec.page.locator(".o_form_statusbar button[name='action_post']"))
        rec.hold(2)
        rec.page.goto(closing_url)
        rec.settle()
        rec.hold(1)
        rec.say("Alleen \"het boekjaar loopt nog\" blijft over.", 4, "afsluiting_klaar")
    rec.click(rec.page.locator("button", has_text="Afrekening voorbereiden"))
    rec.hold(1.5)
    rec.say("Afrekening voorbereiden: per eigenaar een concept-factuur of -creditnota. Er vertrekt niets.", 5,
            "afsluiting_concepten")
    tab = rec.page.locator(".nav-link", has_text="Resultaat en overdracht")
    if tab.count():
        rec.click(tab)
    rec.say("De afrekening wordt geboekt met één klik van uw medewerker, en het jaar gaat dicht zonder dat er "
            "iets vertrekt.", 6, "afsluiting_zeg")


def block_e_outlook(rec):
    rec.chapter("Extra · Een mail van een eigenaar in Outlook")
    rec.goto("/vme_mail_plugin/static/outlook/taskpane.html?demo=1")
    # In Outlook the panel is a narrow column next to the mail: show it that way, enlarged for the video.
    rec.page.add_style_tag(content="""
        html { background: #dfe5ec; }
        body { width: 930px; min-height: 100vh; margin: 0 auto !important; background: #fff;
               box-shadow: 0 0 24px rgba(0, 0, 0, .18); }
        body > *:not(#vme-caption):not(#vme-cursor):not(#vme-click):not(#vme-mark) { zoom: 1.45; }
    """)
    rec.page.wait_for_timeout(2000)
    rec.say("Het paneel naast de mail in Outlook, hier als voorbeeld in de browser.", 2)
    choose_mail(rec, "01")
    rec.say("De lekmail van A4: Residentie Linde, kavels A4 en G4, en het voorstel van de AI-assistent, "
            "nog niet verstuurd.", 6, "outlook_01")
    reply = rec.page.locator("button", has_text="Antwoord invoegen")
    if reply.count():
        rec.click(reply)
        rec.say("Antwoord invoegen zet het voorstel in het antwoordvenster. Verzonden is er niets.", 5,
                "outlook_antwoord")
        close = rec.page.locator("button", has_text="niet verzenden")
        if close.count():
            rec.click(close)
    choose_mail(rec, "02")
    rec.say("Een vraag van B7: onder Wat staat er open, de achterstallige provisies met bedrag en vervaldag.", 6,
            "outlook_02")
    rec.say("Uw medewerkers blijven in Outlook en zien bij elke mail het gebouw, de kavel en wat er openstaat, "
            "met een antwoord klaar om na te kijken. Verzenden blijft hun klik.", 7, "outlook_zeg")


def choose_mail(rec, prefix):
    select = rec.page.locator("#demo-mail")
    rec.point(select)
    value = select.locator("option").filter(has_text=prefix).first.get_attribute("value")
    select.select_option(value)
    rec.page.wait_for_timeout(2500)


def connect_outlook(browser, state):
    """Off camera: connect the Outlook panel once (Verbinden met Odoo, Toestaan) and keep the key."""
    context = browser.new_context(viewport=SIZE, storage_state=str(state))
    page = context.new_page()
    page.goto(f"{BASE}/vme_mail_plugin/static/outlook/taskpane.html?demo=1")
    page.wait_for_timeout(2000)
    connect = page.get_by_role("button", name="Verbinden met Odoo")
    if connect.count():
        with context.expect_page() as popup_info:
            connect.click()
        popup = popup_info.value
        popup.wait_for_load_state()
        popup.get_by_role("button", name="Toestaan").click()
        page.wait_for_timeout(3000)
    context.storage_state(path=str(state))
    context.close()


STAFF_STEPS = [step1_worklist, step2_leak, step3_invoice, step4_quotes, step5_provisions, step6_assemblies,
               step7_statement]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=ROOT / "build/demo_video/raw")
    parser.add_argument("--shots", action="store_true", help="geen video, wel een screenshot per resultaat")
    parser.add_argument("--speed", type=float, default=1.0, help="schaal voor de pauzes (0.2 = vijf keer sneller)")
    parser.add_argument("--only", help="komma-gescheiden namen van stappen om te draaien (voor het debuggen)")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    only = set(args.only.split(",")) if args.only else None

    with sync_playwright() as p:
        browser = p.chromium.launch()
        staff_state = args.out / "staff.json"
        owner_state = args.out / "owner.json"
        login_state(browser, "admin", "admin", staff_state)
        login_state(browser, OWNER_LOGIN, OWNER_PASSWORD, owner_state)
        connect_outlook(browser, staff_state)

        segments = [
            ("1_staff", staff_state, [intro, *STAFF_STEPS]),
            ("2_owner", owner_state, [step8_portal]),
            ("3_extra", staff_state, [extras_card, block_d_closing, block_e_outlook, outro]),
        ]
        for name, state, steps in segments:
            steps = [s for s in steps if not only or s.__name__ in only]
            if not steps:
                continue
            context, rec = new_segment(browser, args, name, state)
            started = time.time()
            try:
                for step in steps:
                    print(f"[{name}] {step.__name__}", flush=True)
                    step(rec)
                rec.wait_voice(0.8)
                if not args.shots:
                    (args.out / name / "timeline.json").write_text(json.dumps(rec.timeline, indent=1))
            except Exception:
                rec.page.screenshot(path=str(args.out / f"ERROR_{name}.png"))
                raise
            finally:
                context.close()
            print(f"[{name}] {time.time() - started:.0f} s", flush=True)
        browser.close()


def intro(rec):
    title_card(rec, "Quotis", "Een syndicusplatform op Odoo: van mail tot jaarafrekening",
               ["Drie fictieve gebouwen · begin november 2026",
                "De software zet alles klaar, een mens beslist."],
               "Prototype. Alle gebouwen, eigenaars, bedragen en rekeningnummers zijn verzonnen.", 6, "#intro")


def extras_card(rec):
    title_card(rec, "Twee extra's", "Het boekjaar afsluiten · Een mail van een eigenaar in Outlook",
               [], "Prototype met fictieve data.", 3, "#extras")


def outro(rec):
    title_card(rec, "Quotis", "De software zet alles klaar, een mens beslist.",
               ["Niets vertrekt zonder een klik van uw medewerker."],
               "Prototype op Odoo 19 Community. Alle data is verzonnen; de Belgische regels zijn nog niet "
               "juridisch nagekeken.", 5, "#outro")


if __name__ == "__main__":
    main()
