"""Browser suite (Chromium via Playwright) against a local server: I18N, VIEW-08, WFL-CS-10 display, NFR-02..05, NFR-01/07.
Marked slow: it needs Chromium, so it runs before each push, not in the Render build.

Run: python -m pytest -q -m slow tests/test_browser.py -rA
"""
import os
import re
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import concurrent.futures as cf
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")
requests = pytest.importorskip("requests")
pytestmark = pytest.mark.slow
ROOT = Path(__file__).resolve().parent.parent
PW = "test-demo-pass"
ARABIC = re.compile(r"[؀-ۿ]")


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture(scope="module")
def base():
    port = _free_port()
    env = {**os.environ, "RAFIQ_RUNTIME_DIR": tempfile.mkdtemp(prefix="rafiq-ui-"), "LLM_PROVIDER": "offline",
           "RAFIQ_DEMO_PASSWORD": PW, "RAFIQ_ADMIN_PASSWORD": "test-admin-pass", "DATABASE_URL": ""}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if requests.get(url + "/api/health", timeout=1).ok:
                break
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    yield url
    proc.terminate(); proc.wait(5)


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def page_for(browser, base, user=None, lang=None, width=1280):
    ctx = browser.new_context(viewport={"width": width, "height": 900})
    pg = ctx.new_page()
    pg.goto(base + ("/?lang=" + lang if lang else "/"))
    pg.wait_for_selector("#loginForm, #side:not(.hidden)")
    if user:
        pg.fill("#lu", user); pg.fill("#lp", PW); pg.click("#loginForm button[type=submit]")
        pg.wait_for_selector("#side:not(.hidden)")
        pg.wait_for_timeout(400)
    return pg


def nav(pg, label_en=None, page=None):
    pg.click(f'#side button[data-page="{page}"]'); pg.wait_for_timeout(500)


def no_hscroll(pg):
    return pg.evaluate("document.scrollingElement.scrollWidth <= window.innerWidth + 1")


def ask(pg, text):
    n = pg.locator("#msgs .msg.bot").count()
    pg.fill("#input", text); pg.press("#input", "Enter")
    pg.wait_for_function(f"document.querySelectorAll('#msgs .msg.bot').length > {n} && "
                         "document.querySelector('#typing').classList.contains('hidden')", timeout=20000)
    pg.evaluate("typeof finishTyping === 'function' && finishTyping()")
    last, same = None, 0
    while same < 3:                                   # wait until the typed-out reply stops changing
        pg.wait_for_timeout(250)
        cur = pg.locator("#msgs .msg.bot").last.inner_text()
        same = same + 1 if cur == last else 0
        last = cur
    return last


VIEWS = {"aisha.rahman": ["home", "chat", "journey", "requests", "policies", "profile"],
         "mgr.hassan.brown": ["home", "team", "policies"],
         "hr.nadia.farouk": ["home", "cases", "insights", "policies"],
         "owner.priya.raman": ["home", "cases", "insights"]}


# ---------------------------------------------------------------- I18N
def test_I18N_01_rtl_layout_on_every_view_and_VIEW_08_manager_in_arabic(browser, base):
    for user, pages in VIEWS.items():
        pg = page_for(browser, base, user, lang="ar")
        for p in pages:
            nav(pg, page=p)
            assert pg.evaluate("document.documentElement.dir") == "rtl", (user, p)
            assert no_hscroll(pg), (user, p, "horizontal scroll")
            side = pg.inner_text("#side")
            assert ARABIC.search(side) and not re.search(r"\b(Home|Cases|Insights|Policies|My team)\b", side), (user, p)
            if user.startswith("mgr") and p == "team":
                body = pg.inner_text("#view")
                assert ARABIC.search(body) and not re.search(r"pulse|score|mood", body, re.I)
        pg.context.close()


def test_I18N_02_reply_language_follows_the_question(browser, base):
    pg = page_for(browser, base, "shamma.alfalasi", lang="ar")
    nav(pg, page="chat")
    assert ARABIC.search(ask(pg, "ما هو بدل السكن الخاص بي؟"))
    en = ask(pg, "What is my housing allowance?")
    assert "housing allowance" in en.lower() and not ARABIC.search(en.split("\n")[0])
    pg.context.close()


def test_I18N_03_citations_render_correctly_in_rtl(browser, base):
    pg = page_for(browser, base, "shamma.alfalasi", lang="ar")
    nav(pg, page="chat")
    ask(pg, "ما هو بدل السكن الخاص بي؟")
    cites = pg.locator("#msgs .msg.bot").last.locator(".cite").all_inner_texts()
    assert cites and all(re.fullmatch(r"POL-[A-Z]+-\d{3} §[\d.]+", c.strip()) for c in cites), cites
    pg.locator("#msgs .msg.bot").last.locator(".cite").first.click()
    pg.wait_for_selector("dialog[open]")
    assert "POL-" in pg.inner_text("dialog[open]")
    pg.context.close()


def test_I18N_07_handoff_and_consent_dialogs_in_arabic(browser, base):
    pg = page_for(browser, base, "aisha.rahman", lang="ar")
    nav(pg, page="chat")
    ask(pg, "لم أستلم الحاسوب المحمول بعد")
    pg.locator("#msgs .msg.bot").last.locator("button.act, .acts button").filter(has_text="Priya Raman").first.click()
    pg.wait_for_selector("dialog[open]")
    # the exact English text the owner receives is shown as-is, marked lang="en"; everything else must be Arabic
    txt = pg.evaluate("""() => { const d = document.querySelector('dialog[open]').cloneNode(true);
        d.querySelectorAll('[lang=en]').forEach(e => e.remove()); return d.innerText; }""")
    assert pg.locator("dialog[open] [lang=en]").count() == 1
    allowed = r"Priya Raman|Nadia Farouk|Aisha Rahman|Kevin Lim|Dubai|Group HQ|Garhoud|POL-[A-Z]+-\d+|§|SR-\d+|CASE-\w+|HIGH|IT"
    leftovers = re.findall(r"[A-Za-z]{3,}", re.sub(allowed, "", txt))
    pg.keyboard.press("Escape")
    pg.click('#side button[data-page="!mydata"]'); pg.wait_for_selector("dialog[open]")
    md = pg.inner_text("dialog[open]")
    pg.context.close()
    assert not leftovers, f"English fragments in the Arabic handoff dialog: {sorted(set(leftovers))[:15]}"
    assert ARABIC.search(md)


def test_I18N_08_language_choice_persists(browser, base):
    pg = page_for(browser, base, "aisha.rahman")
    pg.click("#langBtn"); pg.wait_for_timeout(400)
    pg.reload(); pg.wait_for_selector("#side:not(.hidden), #loginForm")
    assert pg.evaluate("document.documentElement.dir") == "rtl"
    pg.click("#langBtn"); pg.wait_for_timeout(300)            # back to English for the next tests
    pg.context.close()


def test_I18N_09_deep_link_lang_ar(browser, base):
    pg = page_for(browser, base, None, lang="ar")
    assert pg.evaluate("document.documentElement.dir") == "rtl" and ARABIC.search(pg.inner_text("#view"))
    pg.context.close()


# ---------------------------------------------------------------- WFL-CS-10 display
def test_WFL_CS_10_overdue_update_is_highlighted_in_the_inbox(browser, base):
    s = requests.Session()
    s.post(base + "/api/login", json={"username": "aisha.rahman", "password": PW}, headers={"X-Rafiq-Request": "1"})
    c = s.post(base + "/api/employee/EMP-1001/actions", json={"action": {"type": "ESCALATE", "step": "IT_KIT_ISSUED"}},
               headers={"X-Rafiq-Request": "1"}).json()["case"]
    pg = page_for(browser, base, "owner.priya.raman")
    pg.evaluate("S.health.as_of = '2099-01-01'")             # simulate the next-update date passing
    nav(pg, page="cases")
    assert "Update overdue" in pg.inner_text("#view")
    pg.context.close()


# ---------------------------------------------------------------- NFR
def test_NFR_02_phone_width_no_horizontal_scroll_and_dialogs_fit(browser, base):
    bad = []
    for user, pages in VIEWS.items():
        for lang in (None, "ar"):
            pg = page_for(browser, base, user, lang=lang, width=375)
            for p in pages:
                pg.evaluate(f"go('{p}')"); pg.wait_for_timeout(500)
                if not no_hscroll(pg):
                    bad.append((user, lang, p))
            if user == "aisha.rahman":
                pg.evaluate("openMyData()"); pg.wait_for_selector("dialog[open]")
                w = pg.evaluate("document.querySelector('dialog[open]').getBoundingClientRect().width")
            pg.context.close()
    assert not bad, f"horizontal scroll at 375px on: {bad}"
    assert w <= 375


def test_NFR_03_keyboard_only_sign_in_and_visible_focus(browser, base):
    pg = page_for(browser, base)
    pg.focus("#lu"); pg.keyboard.type("aisha.rahman"); pg.keyboard.press("Tab"); pg.keyboard.type(PW); pg.keyboard.press("Enter")
    pg.wait_for_selector("#side:not(.hidden)")
    pg.evaluate("document.activeElement.blur()")
    seen, outlines, nofocus = set(), [], []
    for _ in range(80):
        pg.keyboard.press("Tab")
        info = pg.evaluate("""() => { const e = document.activeElement; const cs = getComputedStyle(e);
            return [e.tagName, e.dataset.page || e.id || e.textContent.trim().slice(0, 20),
                    cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0 || cs.boxShadow !== 'none'] }""")
        seen.add(info[1]); outlines.append(info[2])
        if not info[2] and info[0] != "BODY":          # BODY = the tab order wrapping round
            nofocus.append(info[:2])
    pg.context.close()
    assert {"home", "chat", "journey", "input"} <= seen or {"home", "chat", "journey"} <= seen, sorted(seen)[:20]
    assert not nofocus, f"focus without a visible focus style: {nofocus[:5]}"


def test_NFR_04_controls_have_accessible_names(browser, base):
    pg = page_for(browser, base, "aisha.rahman")
    missing = []
    for p in VIEWS["aisha.rahman"]:
        pg.evaluate(f"go('{p}')"); pg.wait_for_timeout(500)
        missing += pg.evaluate("""() => [...document.querySelectorAll('button, input, textarea, select, a[href]')]
            .filter(e => e.offsetParent !== null)
            .filter(e => !(e.getAttribute('aria-label') || e.textContent.trim() || e.title ||
                           (e.id && document.querySelector(`label[for="${e.id}"]`)) || e.placeholder))
            .map(e => e.outerHTML.slice(0, 80))""")
    pg.context.close()
    assert not missing, missing[:5]


def test_NFR_05_status_is_not_conveyed_by_colour_alone(browser, base):
    pg = page_for(browser, base, "aisha.rahman")
    txt = pg.inner_text("#view")
    marks = pg.evaluate("[...document.querySelectorAll('.mk')].every(m => m.getAttribute('aria-label'))")
    pg.context.close()
    assert re.search(r"Stalled \+\d+d", txt) and "Waiting on" in txt and marks


def test_NFR_01_and_07_latency_and_concurrent_load(base):
    def one(i):
        s = requests.Session()
        u = ["aisha.rahman", "mei.chen", "emeka.okafor", "sophie.dubois", "tariq.hussain"][i % 5]
        s.post(base + "/api/login", json={"username": u, "password": PW}, headers={"X-Rafiq-Request": "1"})
        me = s.get(base + "/api/me").json()["user"]["id"]
        t0 = time.time()
        r = s.post(base + f"/api/employee/{me}/chat", json={"message": "What's next for me?"}, headers={"X-Rafiq-Request": "1"})
        return r.status_code, time.time() - t0
    seq = [one(i)[1] for i in range(10)]
    with cf.ThreadPoolExecutor(20) as ex:
        res = list(ex.map(one, range(40)))
    assert all(code == 200 for code, _ in res)
    p95_seq = sorted(seq)[int(0.95 * len(seq)) - 1]
    p95_load = sorted(t for _, t in res)[int(0.95 * len(res)) - 1]
    print(f"p95 single {p95_seq:.2f}s, p95 under 20 concurrent users {p95_load:.2f}s")
    assert p95_seq < 3 and p95_load < 8


def test_DEF057_case_stays_selected_after_acknowledge(browser, base):
    pg = page_for(browser, base, "owner.priya.raman")
    nav(pg, page="cases")
    item = pg.locator(".case-item").nth(1)
    cid = item.get_attribute("data-id")
    item.click(); pg.wait_for_timeout(300)
    pg.click('[data-status="ACKNOWLEDGED"]'); pg.wait_for_timeout(600)
    assert cid in pg.inner_text("#caseDetail")                       # still the same case, now under Acknowledged
    assert pg.locator('.filters button[data-f="ACKNOWLEDGED"]').get_attribute("aria-pressed") == "true"
    pg.context.close()
