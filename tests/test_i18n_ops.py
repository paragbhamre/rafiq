"""Catalogue suites I18N (API-level parts) and OPS (platform checks that can run without the hosted service).

Run: python -m pytest -q tests/test_i18n_ops.py -rA
"""
import re
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, companion, config
from app.data import pack, state
from app.journey import seed_early_warnings
from app.main import app

pytestmark = pytest.mark.skipif(not config.IS_REFERENCE_PACK, reason="synthetic-pack people")
ROOT = Path(__file__).resolve().parent.parent
ARABIC = re.compile(r"[؀-ۿ]")


def H(user):
    return {"Cookie": f"{auth.COOKIE}={auth.issue(auth.directory.find(user))}", "X-Rafiq-Request": "1"}


def cites(r):
    return {c["cite"] if isinstance(c, dict) else c for c in r["citations"]}


@pytest.fixture(autouse=True)
def clean():
    state.reset(); seed_early_warnings()
    yield
    state.reset(); seed_early_warnings()


# ---------------------------------------------------------------- I18N
@pytest.mark.parametrize("q,want", [
    ("ما هو بدل السكن الخاص بي؟", "POL-ALW-001"),
    ("متى سأحصل على الحاسوب المحمول؟", "POL-IT-001"),
    ("هل سيرى مديري ما أقوله لك؟", "POL-PRV-001"),
])
def test_I18N_04_arabic_questions_find_the_right_policy(q, want):
    emp = {"POL-ALW-001": "EMP-1007", "POL-IT-001": "EMP-1001", "POL-PRV-001": "EMP-1011"}[want]
    r = companion.chat(emp, q)
    assert r["lang"] == "ar" and ARABIC.search(r["reply"])
    assert any(c.startswith(want) for c in cites(r)), (q, cites(r))


def test_I18N_05_mixed_language_input_is_understood():
    r = companion.chat("EMP-1007", "ما هو housing allowance الخاص بي؟")
    assert any(c.startswith("POL-ALW-001") for c in cites(r)) and "9,000" in r["reply"]
    r = companion.chat("EMP-1001", "My laptop لم يصل بعد")
    assert any(c.startswith("POL-IT-001") for c in cites(r))


def test_I18N_06_amounts_and_dates_identical_in_arabic_and_english():
    en = companion.chat("EMP-1007", "What is my housing allowance?")
    ar = companion.chat("EMP-1007", "ما هو بدل السكن الخاص بي؟")
    nums = lambda t: set(re.findall(r"\d[\d,]*", t))
    assert "9,000" in en["reply"] and "9,000" in ar["reply"]
    assert {n for n in nums(en["reply"]) if "," in n} == {n for n in nums(ar["reply"]) if "," in n}
    assert cites(en) == cites(ar)


# ---------------------------------------------------------------- OPS
def test_OPS_02_health_check():
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200 and r.json().get("ok", True) and r.json()["storage"]["ok"]


def test_OPS_05_reset_returns_to_baseline_and_logins_still_work():
    c = TestClient(app)
    baseline = sorted((x["employee_id"], x["type"], x["owner"]["name"]) for x in state.cases())
    c.post("/api/employee/EMP-1001/actions", json={"action": {"type": "ESCALATE", "step": "IT_KIT_ISSUED"}}, headers=H("EMP-1001"))
    c.post("/api/employee/EMP-1001/chat", json={"message": "hi"}, headers=H("EMP-1001"))
    c.post("/api/employee/EMP-1006/consent", json={"active": True}, headers=H("EMP-1006"))
    assert c.post("/api/admin/reset", headers=H("admin")).status_code == 200
    assert sorted((x["employee_id"], x["type"], x["owner"]["name"]) for x in state.cases()) == baseline
    assert state.conv_count("EMP-1001") == 0 and not state.requests_for("EMP-1001")
    assert c.get("/api/employee/EMP-1006/mydata", headers=H("EMP-1006")).json()["consent"]["state"] == "WITHDRAWN"
    r = c.post("/api/login", json={"username": "aisha.rahman", "password": "test-demo-pass"}, headers={"X-Rafiq-Request": "1"})
    assert r.status_code == 200


def test_OPS_06_two_testers_at_once_no_cross_talk():
    a, b = TestClient(app), TestClient(app)
    for cl, u in ((a, "aisha.rahman"), (b, "emeka.okafor")):
        assert cl.post("/api/login", json={"username": u, "password": "test-demo-pass"},
                       headers={"X-Rafiq-Request": "1"}).status_code == 200
    hdr = {"X-Rafiq-Request": "1"}
    for _ in range(3):
        ra = a.post("/api/employee/EMP-1001/chat", json={"message": "Where is my laptop?"}, headers=hdr).json()
        rb = b.post("/api/employee/EMP-1008/chat", json={"message": "Where am I staying?"}, headers=hdr).json()
        assert "Laptop" in ra["reply"] and "ccommodation" in rb["reply"]
    assert a.get("/api/me").json()["user"]["id"] == "EMP-1001" and b.get("/api/me").json()["user"]["id"] == "EMP-1008"
    assert a.get("/api/employee/EMP-1008/threads", headers=hdr).status_code == 403
    ta = a.get("/api/employee/EMP-1001/threads", headers=hdr).json()
    tb = b.get("/api/employee/EMP-1008/threads", headers=hdr).json()
    assert ta and tb and not ({t["id"] for t in ta} & {t["id"] for t in tb})


def test_OPS_10_no_secrets_in_the_repository():
    key = re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
                     r"postgres(?:ql)?://[^\s:@/]+:[^\s@/<>{}$]+@")
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split() \
        if (ROOT / ".git").exists() else [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file()]
    hits = []
    for f in files:
        p = ROOT / f
        if p.suffix in (".png", ".jpg", ".ico", ".pyc", ".xlsx") or not p.is_file():
            continue
        if key.search(p.read_text(encoding="utf-8", errors="ignore")):
            hits.append(f)
    assert not hits, hits
    render = (ROOT / "render.yaml").read_text(encoding="utf-8") if (ROOT / "render.yaml").exists() else ""
    for k in ("ANTHROPIC_API_KEY", "RAFIQ_DEMO_PASSWORD", "RAFIQ_ADMIN_PASSWORD"):
        if k in render:
            block = render.split(k, 1)[1][:120]
            assert "sync: false" in block or "generateValue" in block or "fromDatabase" in block, k


def test_OPS_12_every_seeded_login_works_after_a_fresh_start():
    c = TestClient(app)
    users = list(auth.directory.users.values()) if isinstance(auth.directory.users, dict) else auth.directory.users()
    assert len([u for u in users if u["role"] == "employee"]) == len(pack.employees)
    for u in ("aisha.rahman", "mgr.hassan.brown", "hr.nadia.farouk", "owner.priya.raman", "owner.reem.alhashimi",
              "owner.omar.haddad", "lucas.moreau"):
        r = c.post("/api/login", json={"username": u, "password": "test-demo-pass"}, headers={"X-Rafiq-Request": "1"})
        assert r.status_code == 200, u
