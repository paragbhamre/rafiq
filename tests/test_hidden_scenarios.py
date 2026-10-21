"""Hidden-scenario rehearsal employees (EMP-1301 to EMP-1320, data/scenarios.md H01-H20).

Part 1 checks the seeded situation in the journey engine: the intended step is stalled (or the
employee is on track) whatever today's date is.
Part 2 runs the employee's prompt through the companion. Cases Rafiq doesn't handle yet are marked
xfail with the gap, so the build stays green and the gap stays visible; remove the mark once fixed.
"""
import os
import tempfile

os.environ.setdefault("RAFIQ_RUNTIME_DIR", tempfile.mkdtemp(prefix="rafiq-test-"))
os.environ["LLM_PROVIDER"] = "offline"

import pytest  # noqa: E402

from app import companion, config  # noqa: E402
from app.journey import evaluate  # noqa: E402

pytestmark = pytest.mark.skipif(not config.IS_REFERENCE_PACK, reason="synthetic-pack scenarios")

# employee, stalled step(s) that are the point of the scenario, other overdue steps allowed as a consequence
SEEDED = {
    "EMP-1301": (["BACKGROUND_CHECK_CLEARED"], {"VISA_APPLICATION_SUBMITTED"}),
    "EMP-1302": (["VISA_APPLICATION_SUBMITTED"], set()),
    "EMP-1303": (["STAFF_ID_ISSUED"], set()),
    "EMP-1304": (["EMIRATES_ID_APPLIED"], set()),
    "EMP-1305": (["MANDATORY_TRAINING_BOOKED"], set()),
    "EMP-1306": (["PROBATION_OBJECTIVES_SET"], set()),
    "EMP-1307": (["CHECKIN_30_DONE"], set()),
    "EMP-1308": (["JOINING_TICKET_ISSUED"], set()),
    "EMP-1309": (["RELEASING_MANAGER_RELEASED"], set()),
    "EMP-1310": (["TRANSFER_LETTER_ISSUED"], set()),
    "EMP-1311": (["RELOCATION_ASSESSED"], set()),
    "EMP-1312": (["HOUSING_ARRANGED"], set()),
    "EMP-1313": (["HANDOVER_COMPLETED"], set()),
    "EMP-1314": (["ROLE_TRAINING_BOOKED"], set()),
    "EMP-1315": (["CHECKIN_30_DONE"], set()),
    "EMP-1316": ([], set()),
    "EMP-1317": ([], set()),
    "EMP-1318": ([], set()),
    "EMP-1319": ([], set()),
    "EMP-1320": ([], set()),
}


@pytest.mark.parametrize("emp", sorted(SEEDED))
def test_seeded_situation(emp):
    stalled, allowed = SEEDED[emp]
    ev = evaluate(emp)
    status = {s["code"]: s["status"] for s in ev["steps"]}
    for code in stalled:
        assert status[code] == "STALLED", (emp, code, status[code])
    others = {c for c, st in status.items() if st in ("STALLED", "AT_RISK")} - set(stalled)
    assert others <= allowed, (emp, others)
    if not stalled:
        assert ev["overall"] in ("GREEN", "AMBER")


def test_not_applicable_steps_are_absent():
    codes = lambda e: {s["code"] for s in evaluate(e)["steps"]}  # noqa: E731
    assert "WORK_PERMIT_ISSUED" not in codes("EMP-1317")                 # domestic move
    assert not {"RELOCATION_ASSESSED", "RELOCATION_ALLOWANCE_PAID"} & codes("EMP-1316")  # team change
    assert "ACCOMMODATION_ASSIGNED" not in codes("EMP-1319")             # not eligible
    assert not {"JOINING_TICKET_ISSUED", "VISA_ISSUED"} & codes("EMP-1320")  # local hire, UAE national


def test_request_ageing_only_is_amber():
    ev = evaluate("EMP-1318")
    assert ev["overall"] == "AMBER"
    assert [s["type"] for s in ev["signals"]] == ["REQUEST_AGEING"]


# ---------------------------------------------------------------- companion replies
def _esc(r):
    return {(a.get("owner") or {}).get("name") for a in r["actions"] if a["type"] == "ESCALATE"}


def _cites(r):
    return {c["cite"] for c in r["citations"]}


GAP = "companion gap found in the 21 Oct rehearsal; see tracker HID cases"

CASES = [
    ("H01", "EMP-1301", "I accepted my offer weeks ago and haven't heard anything since.",
     lambda r: "background" in r["reply"].lower() and "not sure" not in r["reply"].lower(), None),
    ("H02", "EMP-1302", "Has my visa application gone in?",
     lambda r: "Khalid Al Mansoori" in _esc(r) and "POL-PRO-001 §3.1" in _cites(r), None),
    ("H03", "EMP-1303", "I still need someone to sign me into the building every day.",
     lambda r: "Rashid Al Ketbi" in _esc(r) and "POL-SEC-001 §1.2" in _cites(r), None),
    ("H04", "EMP-1304", "متى ستكون الهوية الإماراتية جاهزة؟",
     lambda r: "Khalid Al Mansoori" in _esc(r) and "POL-PRO-001 §5.2" in _cites(r), None),
    ("H05", "EMP-1305", "Do I need to book any training?",
     lambda r: "Daniel Okafor" in _esc(r) and "POL-LRN-001 §2.2" in _cites(r), None),
    ("H06", "EMP-1306", "My manager still hasn't set my probation objectives. Is that a problem for me?",
     lambda r: "Claire Dupont" in _esc(r) and "POL-ONB-002 §2.2" in _cites(r), None),
    ("H07", "EMP-1307", "Wasn't someone from HR meant to check in with me?",
     lambda r: "Vikram Desai" in _esc(r), None),
    ("H08", "EMP-1308", "My visa came through but I have no flight ticket.",
     lambda r: "Abdulla Al Kaabi" in _esc(r) and "POL-TRV-001 §1.3" in _cites(r), None),
    ("H09", "EMP-1309", "My current manager won't confirm my release date.",
     lambda r: "James Whitaker" in _esc(r) and "POL-MOB-001 §4.1" in _cites(r), None),
    ("H10", "EMP-1310", "What are my new terms? I haven't had my transfer letter.",
     lambda r: "Claire Dupont" in _esc(r) and "POL-MOB-001 §3.4" in _cites(r), None),
    ("H11", "EMP-1311", "Nobody has told me what relocation support I get.",
     lambda r: "Sarah Whitfield" in _esc(r) and "isn't part of your journey" not in r["reply"], None),
    ("H12", "EMP-1312", "I moved today and have nowhere to live.",
     lambda r: "Omar Haddad" in _esc(r), None),
    ("H13", "EMP-1313", "I'm already in my new role but still doing my old job.",
     lambda r: "Abdulla Al Kaabi" in _esc(r), None),
    ("H14", "EMP-1314", "Is there training for my new role?",
     lambda r: "Daniel Okafor" in _esc(r) and "POL-LRN-001 §3.1" in _cites(r), None),
    ("H15", "EMP-1315", "Has anyone scheduled my check-in for the new role?",
     lambda r: "Nadia Farouk" in _esc(r), None),
    ("H16", "EMP-1316", "Do I get a relocation allowance for my team move?",
     lambda r: "POL-ALW-001 §4.4" in _cites(r) and not _esc(r), None),
    ("H17", "EMP-1317", "متى سيصدر تصريح العمل للموقع الجديد؟",
     lambda r: not _esc(r) and "ليست جزءاً" in r["reply"], None),
    ("H18", "EMP-1318", "Any update on my facilities request?",
     lambda r: "SR-" in r["reply"], None),
    ("H19", "EMP-1319", "When will I get my staff accommodation address?",
     lambda r: "POL-ACC-001 §1.3" in _cites(r) and not _esc(r), None),
    ("H20", "EMP-1320", "When will my joining flight ticket be issued?",
     lambda r: "isn't part of your journey" in r["reply"] and not _esc(r), None),
]


@pytest.mark.parametrize("hid,emp,prompt,check,gap", CASES, ids=[c[0] for c in CASES])
def test_companion_handles_hidden_scenario(hid, emp, prompt, check, gap):
    r = companion.chat(emp, prompt)
    ok = check(r)
    if gap:
        assert not ok, f"{hid} now passes: remove its gap note in CASES"
        pytest.xfail(gap)
    assert ok, (hid, r["reply"][:400], _esc(r), _cites(r))


# ---------------------------------------------------------------- fallbacks found in the 21 Oct rehearsal
def test_unknown_allowance_is_not_sure_not_another_allowance():
    # A04: never answer an unknown allowance with the amounts of a different one
    for emp in ("EMP-1001", "EMP-1009"):
        r = companion.chat(emp, "What's the company's education allowance per child?")
        assert "not sure" in r["reply"].lower() and "AED" not in r["reply"], emp
        assert any(a["type"] == "ASK_HUMAN" for a in r["actions"])


def test_vague_first_person_question_answers_from_the_stalled_step():
    r = companion.chat("EMP-1001", "Nothing is working for me this week.")
    assert "not sure" not in r["reply"].lower()
    assert "Priya Raman" in _esc(r)


def test_not_covered_question_still_says_not_sure():
    r = companion.chat("EMP-1012", "Can I bring my cat on the joining flight, and will the company pay for it?")
    assert "not sure" in r["reply"].lower() and not _esc(r)
    r = companion.chat("EMP-1009", "I'm wondering about the gym membership I was promised.")
    assert "not sure" in r["reply"].lower()


def test_request_status_question_lists_the_request():
    r = companion.chat("EMP-1002", "Any update on my request?")
    assert "SR-00002" in r["reply"] and "Khalid Al Mansoori" in _esc(r)
