"""Catalogue suites ENG (rules engine boundaries, prerequisites), SIG (friction signals) and STG (journey stages).

The expected target days, grace periods, applies-when rules and prerequisites below are copied from the challenge's
journey maps (the same tables the test catalogue was built from), so they act as an independent oracle for the
engine's own configuration.

Run: python -m pytest -q tests/test_engine.py -rA
"""
import datetime as dt

import pytest

from app import config
from app.data import pack, state
from app.journey import evaluate, stage_for

pytestmark = pytest.mark.skipif(not config.IS_REFERENCE_PACK, reason="synthetic-pack templates")

# (catalogue code, event code, target day, grace days, applies-when)
STEPS_A = [("A1", "OFFER_ACCEPTED", -45, 0, None), ("A2", "BACKGROUND_CHECK_CLEARED", -30, 5, None),
           ("A3", "VISA_APPLICATION_SUBMITTED", -28, 3, "visa"), ("A4", "MEDICAL_COMPLETED", -18, 3, "visa"),
           ("A5", "VISA_ISSUED", -10, 2, "visa"), ("A6", "JOINING_TICKET_ISSUED", -7, 2, "abroad"),
           ("A7", "ACCOMMODATION_ASSIGNED", -5, 2, "accom"), ("A8", "IT_KIT_ISSUED", 1, 1, None),
           ("A9", "SYSTEM_ACCESS_GRANTED", 2, 1, None), ("A10", "STAFF_ID_ISSUED", 3, 2, None),
           ("A11", "BUDDY_ASSIGNED", 1, 2, None), ("A12", "EMIRATES_ID_APPLIED", 7, 3, "visa"),
           ("A13", "INDUCTION_COMPLETED", 5, 2, None), ("A14", "MANDATORY_TRAINING_BOOKED", 7, 3, None),
           ("A15", "PROBATION_OBJECTIVES_SET", 30, 5, None), ("A16", "CHECKIN_30_DONE", 30, 5, None)]
STEPS_B = [("B1", "MOVE_REQUESTED", 0, 0, None), ("B2", "RECEIVING_MANAGER_ENDORSED", 5, 2, None),
           ("B3", "RELEASING_MANAGER_RELEASED", 7, 3, None), ("B4", "TRANSFER_APPROVED", 12, 3, None),
           ("B5", "TRANSFER_LETTER_ISSUED", 14, 2, None), ("B6", "RELOCATION_ASSESSED", 16, 3, "loc"),
           ("B7", "WORK_PERMIT_ISSUED", 26, 3, "intl"), ("B8", "RELOCATION_ALLOWANCE_PAID", 25, 3, "loc"),
           ("B9", "HOUSING_ARRANGED", 27, 2, "loc"), ("B10", "HANDOVER_COMPLETED", 29, 2, None),
           ("B11", "ACCESS_TRANSFERRED", 30, 1, None), ("B12", "MOVE_EFFECTIVE", 30, 0, None),
           ("B13", "ROLE_TRAINING_BOOKED", 40, 3, None), ("B14", "CHECKIN_30_DONE", 60, 5, None)]
CODE = {c: e for c, e, *_ in STEPS_A + STEPS_B}
ANCHOR = dt.date(2026, 1, 1)
FX = "EMP-9901"


@pytest.fixture
def fixture_emp(monkeypatch):
    """Inject one synthetic employee (onboarding or mobility) with chosen flags, events, requests and pulse."""
    monkeypatch.setattr(state, "completions", lambda: {"steps": {}, "requests": {}})

    def make(journey="ONBOARDING", done=(), visa=True, abroad=True, accom=True, move_type="LOCATION_INTERNATIONAL",
             requests=(), pulse=(), opt_in=True, done_on=None):
        base = dict(pack.employees["EMP-1001" if journey == "ONBOARDING" else "EMP-1003"])
        base.update({"employee_id": FX, "journey_type": journey, "journey_anchor_date": ANCHOR.isoformat(),
                     "visa_required": "true" if visa else "false", "relocating_from_abroad": "true" if abroad else "false",
                     "accommodation_eligible": "true" if accom else "false", "pulse_opt_in": "true" if opt_in else "false",
                     "move_type": move_type if journey == "MOBILITY" else ""})
        monkeypatch.setitem(pack.employees, FX, base)
        targets = {e: t for _, e, t, _, _ in STEPS_A + STEPS_B}
        evs = [{"event_id": f"FX-{i}", "employee_id": FX, "journey_type": journey, "event_code": code,
                "event_label": code, "actor_team": "", "source_system": "fixture", "notes": "",
                "event_timestamp": (ANCHOR + dt.timedelta(days=(done_on or {}).get(code, targets[code]))).isoformat() + "T09:00:00+04:00"}
               for i, code in enumerate(done)]
        monkeypatch.setitem(pack.events, FX, evs)
        monkeypatch.setitem(pack.requests, FX, list(requests))
        monkeypatch.setitem(pack.pulse, FX, list(pulse))
        state.consent_set(FX, "ACTIVE" if opt_in else "WITHDRAWN", "fixture") if False else None
        return FX
    yield make
    state.reset()


def ev_at(day):
    return evaluate(FX, ANCHOR + dt.timedelta(days=day))


def step(ev, code):
    return next((s for s in ev["steps"] if s["code"] == CODE.get(code, code)), None)


def sigs(ev, code=None, typ=None):
    return [s for s in ev["signals"] if (code is None or s.get("step") == CODE.get(code, code)) and (typ is None or s["type"] == typ)]


def _others_done(table, target_code, day):
    """Every other step that is due by `day` is recorded done on time, so only the step under test can be late."""
    return [e for c, e, t, _, _ in table if c != target_code and t <= max(day, t if c < target_code else day)]


# ---------------------------------------------------------------- ENG boundaries (generated exactly like the catalogue)
def _variants():
    out = []
    for table, journey in ((STEPS_A, "ONBOARDING"), (STEPS_B, "MOBILITY")):
        for c, e, t, g, _ in table:
            out.append((f"ENG-{c}-01", journey, c, t, "due"))
            if g == 0:
                out.append((f"ENG-{c}-02", journey, c, t + 1, "stalled"))
            else:
                out.append((f"ENG-{c}-02", journey, c, t + 1, "at_risk"))
                if g >= 2:
                    out.append((f"ENG-{c}-03", journey, c, t + g, "at_risk"))
                out.append((f"ENG-{c}-{4 if g >= 2 else 3:02d}", journey, c, t + g + 1, "stalled"))
    return out


@pytest.mark.parametrize("cid,journey,code,day,expect", _variants(), ids=[v[0] for v in _variants()])
def test_ENG_step_status_at_each_boundary(fixture_emp, cid, journey, code, day, expect):
    table = STEPS_A if journey == "ONBOARDING" else STEPS_B
    # every other step due by `day` is done on time; prerequisites always fall due before their dependants,
    # so the prerequisites of the step under test are complete as the catalogue fixture requires
    others = [e for c, e, t, _, _ in table if c != code and t <= day]
    fixture_emp(journey, done=others)
    ev = ev_at(day)
    s = step(ev, code)
    assert s, f"{cid}: step not in journey"
    assert not s["waiting_on"] or s["status"] in ("STALLED", "AT_RISK", "DUE_TODAY", "UPCOMING"), cid
    if expect == "due":
        assert s["status"] in ("DUE_TODAY", "UPCOMING", "WAITING"), (cid, s["status"])
        assert not sigs(ev, code), cid
    elif expect == "at_risk":
        assert s["status"] == "AT_RISK", (cid, s["status"])
        st = sigs(ev, code, "STEP_AT_RISK")
        assert st and st[0]["level"] == "AMBER" and not sigs(ev, code, "STEP_STALLED"), cid
    else:
        assert s["status"] == "STALLED", (cid, s["status"])
        st = sigs(ev, code, "STEP_STALLED")
        assert st and st[0]["level"] == "RED" and not st[0]["sensitive"], cid   # operational data only
        assert st[0]["escalation"]["name"], cid                                   # named owner for the early warning


# ---------------------------------------------------------------- ENG applies-when exclusions
@pytest.mark.parametrize("code", ["A3", "A4", "A5", "A12"])
def test_ENG_visa_steps_absent_for_non_visa_hires(fixture_emp, code):
    fixture_emp(visa=False, done=[CODE["A1"], CODE["A2"]])
    ev = ev_at(40)
    assert step(ev, code) is None and not sigs(ev, code)


def test_ENG_A6_X1_ticket_absent_for_local_hire(fixture_emp):
    fixture_emp(abroad=False, done=[CODE["A1"], CODE["A2"]])
    ev = ev_at(-1)
    assert step(ev, "A6") is None and not sigs(ev, "A6")


def test_ENG_A7_X1_accommodation_absent_when_not_eligible(fixture_emp):
    fixture_emp(accom=False, done=[CODE["A1"], CODE["A2"]])
    ev = ev_at(0)
    assert step(ev, "A7") is None and not sigs(ev, "A7")


@pytest.mark.parametrize("code", ["B6", "B8", "B9"])
def test_ENG_relocation_steps_absent_for_role_and_team_changes(fixture_emp, code):
    for mt in ("ROLE_CHANGE", "TEAM_CHANGE"):
        fixture_emp("MOBILITY", move_type=mt, done=[CODE["B1"]])
        assert step(ev_at(35), code) is None, (code, mt)


def test_ENG_B7_X1_permit_absent_for_domestic_and_B12_needs_B5_only(fixture_emp):
    fixture_emp("MOBILITY", move_type="LOCATION_DOMESTIC", done=[CODE["B1"]])
    ev = ev_at(35)
    assert step(ev, "B7") is None
    assert step(ev, "B12")["prerequisites"] == [CODE["B5"]]


def test_ENG_B12_X1_international_move_waits_on_the_permit(fixture_emp):
    done = [CODE[c] for c in ("B1", "B2", "B3", "B4", "B5", "B6", "B8", "B9", "B10")]
    fixture_emp("MOBILITY", move_type="LOCATION_INTERNATIONAL", done=done)
    ev = ev_at(30)
    b12 = step(ev, "B12")
    assert CODE["B7"] in b12["prerequisites"] and CODE["B7"] in b12["waiting_on"]
    assert any(s["blocked_step"] == CODE["B12"] for s in sigs(ev, "B7", "BLOCKING"))


# ---------------------------------------------------------------- ENG prerequisites
def test_ENG_PRQ_01_access_waits_on_the_laptop(fixture_emp):
    fixture_emp(done=[CODE[c] for c in ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A10", "A11")])
    ev = ev_at(5)
    a9 = step(ev, "A9")
    assert CODE["A8"] in a9["waiting_on"] and a9["blocked_by"]["code"] == CODE["A8"]
    assert step(ev, "A8")["escalation"]["role"] == "IT Service Delivery Manager"


def test_ENG_PRQ_02_induction_waits_on_access(fixture_emp):
    fixture_emp(done=[CODE[c] for c in ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A10", "A11")])
    assert CODE["A9"] in step(ev_at(6), "A13")["waiting_on"]


def test_ENG_PRQ_03_ticket_prerequisite_depends_on_visa(fixture_emp):
    fixture_emp(visa=True, done=[CODE[c] for c in ("A1", "A2", "A3", "A4")])
    assert CODE["A5"] in step(ev_at(-8), "A6")["waiting_on"]
    fixture_emp(visa=False, done=[CODE[c] for c in ("A1", "A2")])
    a6 = step(ev_at(-8), "A6")
    assert a6["prerequisites"] == [CODE["A2"]] and not a6["waiting_on"]


def test_ENG_PRQ_04_transfer_approval_needs_both_managers(fixture_emp):
    fixture_emp("MOBILITY", done=[CODE["B1"], CODE["B2"]])
    b4 = step(ev_at(12), "B4")
    assert set(b4["prerequisites"]) == {CODE["B2"], CODE["B3"]} and b4["waiting_on"] == [CODE["B3"]]


def test_ENG_PRQ_05_completed_late_step_shows_done_without_a_signal(fixture_emp):
    done = [CODE[c] for c in ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11")]
    fixture_emp(done=done, done_on={CODE["A8"]: 4})
    ev = ev_at(6)
    assert step(ev, "A8")["status"] in ("DONE", "DONE_LATE") and not sigs(ev, "A8")


def test_ENG_PRQ_06_step_without_prerequisites_is_judged_on_its_own(fixture_emp):
    done = [CODE[c] for c in ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10")]
    fixture_emp(done=done)
    a11 = step(ev_at(4), "A11")
    assert a11["prerequisites"] == [] and a11["status"] == "STALLED"


# ---------------------------------------------------------------- SIG blocking
def test_SIG_BLK_01_at_risk_visa_blocks_the_ticket_due_in_two_days(fixture_emp):
    fixture_emp(done=[CODE[c] for c in ("A1", "A2", "A3", "A4")])
    ev = ev_at(-9)                                     # A5 target -10 (1 day late, at risk); A6 due day -7
    assert step(ev, "A5")["status"] == "AT_RISK"
    b = [s for s in sigs(ev, "A5", "BLOCKING") if s["blocked_step"] == CODE["A6"]]
    assert b and b[0]["level"] == "RED" and b[0]["escalation"]["role"] == "PRO Team Lead"


@pytest.mark.parametrize("cid,day,flag", [("SIG-BLK-02", 22, True), ("SIG-BLK-03", 21, False)])
def test_SIG_BLK_window_is_seven_days_inclusive(fixture_emp, cid, day, flag):
    # B3 (target 7, grace 3) is stalled from day 11; B10 (needs B3) is due on day 29
    fixture_emp("MOBILITY", done=[CODE[c] for c in ("B1", "B2")])
    ev = ev_at(day)
    assert step(ev, "B3")["status"] == "STALLED"
    blocking = [s for s in sigs(ev, "B3", "BLOCKING") if s["blocked_step"] == CODE["B10"]]
    assert bool(blocking) is flag, cid


# ---------------------------------------------------------------- SIG request ageing and pending info
def _req(days_open, sla=2, status="OPEN", updated_days_ago=None, day=10):
    as_of = ANCHOR + dt.timedelta(days=day)
    created = as_of - dt.timedelta(days=days_open)
    upd = as_of - dt.timedelta(days=updated_days_ago if updated_days_ago is not None else days_open)
    return {"request_id": "SR-FX1", "employee_id": FX, "category": "IT", "request_type": "x", "linked_event_code": "",
            "subject": "Fixture", "description": "", "status": status, "priority": "MEDIUM", "owner_team": "IT Service Desk",
            "owner_name": "Kevin Lim", "created_at": created.isoformat() + "T09:00:00+04:00",
            "last_updated_at": upd.isoformat() + "T09:00:00+04:00", "resolved_at": "", "sla_days": str(sla), "days_open": str(days_open)}


ALL_A_DONE = [e for _, e, *_ in STEPS_A]


@pytest.mark.parametrize("cid,days,status,level", [("SIG-AGE-01", 2, "OPEN", None), ("SIG-AGE-02", 3, "OPEN", "AMBER"),
                                                   ("SIG-AGE-03", 4, "OPEN", "AMBER"), ("SIG-AGE-04", 5, "OPEN", "RED"),
                                                   ("SIG-AGE-05", 10, "RESOLVED", None), ("SIG-AGE-05b", 10, "CLOSED", None)])
def test_SIG_AGE_request_ageing_thresholds(fixture_emp, cid, days, status, level):
    fixture_emp(done=ALL_A_DONE, requests=[_req(days, 2, status)])
    got = [s for s in ev_at(10)["signals"] if s["type"] == "REQUEST_AGEING"]
    assert (got[0]["level"] if got else None) == level, cid


@pytest.mark.parametrize("cid,waited,flag", [("SIG-PND-01", 3, False), ("SIG-PND-02", 4, True)])
def test_SIG_PND_pending_info_bounce(fixture_emp, cid, waited, flag):
    fixture_emp(done=ALL_A_DONE, requests=[_req(1, 10, "PENDING_INFO", updated_days_ago=waited)])
    got = [s for s in ev_at(10)["signals"] if s["type"] == "REQUEST_BOUNCED"]
    assert bool(got) is flag and (not got or got[0]["level"] == "AMBER"), cid


# ---------------------------------------------------------------- SIG pulse and compound
def _pulse(score, days_ago, consent="ACTIVE", day=10):
    at = ANCHOR + dt.timedelta(days=day - days_ago)
    return {"response_id": f"PLS-FX{score}{days_ago}", "employee_id": FX, "submitted_at": at.isoformat() + "T12:00:00+04:00",
            "journey_type": "ONBOARDING", "journey_stage": "", "question_id": "Q2", "question_text": "", "score": str(score),
            "comment": "fixture", "language": "en", "consent_status": consent}


@pytest.mark.parametrize("cid,score,ago,consent,opt_in,flag", [
    ("SIG-PUL-01", 2, 5, "ACTIVE", True, True), ("SIG-PUL-02", 3, 5, "ACTIVE", True, False),
    ("SIG-PUL-03", 1, 15, "ACTIVE", True, False), ("SIG-PUL-04", 1, 2, "WITHDRAWN", False, False)])
def test_SIG_PUL_low_pulse_rules(fixture_emp, cid, score, ago, consent, opt_in, flag):
    fixture_emp(done=ALL_A_DONE, pulse=[_pulse(score, ago, consent)], opt_in=opt_in)
    ev = ev_at(10)
    got = [s for s in ev["signals"] if s["type"] == "PULSE_LOW"]
    assert bool(got) is flag, cid
    if got:
        assert got[0]["level"] == "AMBER" and got[0]["sensitive"] and not [s for s in ev["signals"] if s["type"] == "COMPOUND"]
    if not opt_in:
        assert ev["pulse_used"] == 0


def _a14_late(day_late_status):
    """All done except A14 (target 7, grace 3): day 8 = at risk, day 11 = stalled."""
    return [e for _, e, *_ in STEPS_A if e != CODE["A14"]], {"at_risk": 8, "stalled": 11}[day_late_status]


def test_SIG_CMP_01_two_ambers_make_compound(fixture_emp):
    done, day = _a14_late("at_risk")
    fixture_emp(done=done, requests=[_req(3, 2, "OPEN", day=day)])
    ev = ev_at(day)
    assert [s["level"] for s in ev["signals"] if s["type"] in ("STEP_AT_RISK", "REQUEST_AGEING")] == ["AMBER", "AMBER"]
    c = [s for s in ev["signals"] if s["type"] == "COMPOUND"]
    assert c and c[0]["level"] == "RED" and not c[0]["sensitive"]


def test_SIG_CMP_02_red_plus_low_pulse_makes_compound(fixture_emp):
    done, day = _a14_late("stalled")
    fixture_emp(done=done, pulse=[_pulse(2, 3, day=day)])
    c = [s for s in ev_at(day)["signals"] if s["type"] == "COMPOUND"]
    assert c and c[0]["level"] == "RED" and c[0]["sensitive"]       # employee-facing only, never to an owner unasked


def test_SIG_CMP_03_red_plus_withdrawn_pulse_is_not_compound(fixture_emp):
    done, day = _a14_late("stalled")
    fixture_emp(done=done, pulse=[_pulse(1, 3, "WITHDRAWN", day=day)], opt_in=False)
    ev = ev_at(day)
    assert not [s for s in ev["signals"] if s["type"] in ("COMPOUND", "PULSE_LOW")]
    assert not any(s.get("sensitive") for s in ev["signals"])


def test_SIG_CMP_04_single_amber_is_not_compound(fixture_emp):
    done, day = _a14_late("at_risk")
    fixture_emp(done=done)
    ev = ev_at(day)
    assert [s["type"] for s in ev["signals"]] == ["STEP_AT_RISK"] and ev["overall"] == "AMBER"


def test_SIG_CMP_05_amber_step_plus_low_pulse_makes_compound(fixture_emp):
    done, day = _a14_late("at_risk")
    fixture_emp(done=done, pulse=[_pulse(2, 3, day=day)])
    assert [s for s in ev_at(day)["signals"] if s["type"] == "COMPOUND"]


# ---------------------------------------------------------------- STG
@pytest.mark.parametrize("cid,journey,day,stage", [
    ("STG-A-01", "ONBOARDING", -1, "PRE_ARRIVAL"), ("STG-A-02", "ONBOARDING", 0, "FIRST_WEEK"),
    ("STG-A-03", "ONBOARDING", 6, "FIRST_WEEK"), ("STG-A-04", "ONBOARDING", 7, "FIRST_MONTH"),
    ("STG-A-05", "ONBOARDING", 30, "FIRST_MONTH"), ("STG-A-06", "ONBOARDING", 31, "SETTLING_IN"),
    ("STG-A-07", "ONBOARDING", 90, "SETTLING_IN"),
    ("STG-B-01", "MOBILITY", 4, "MOVE_REQUESTED"), ("STG-B-02", "MOBILITY", 5, "APPROVALS"),
    ("STG-B-03", "MOBILITY", 14, "APPROVALS"), ("STG-B-04", "MOBILITY", 15, "PRE_MOVE"),
    ("STG-B-05", "MOBILITY", 29, "PRE_MOVE"), ("STG-B-06", "MOBILITY", 30, "IN_NEW_ROLE"),
    ("STG-B-07", "MOBILITY", 60, "IN_NEW_ROLE")])
def test_STG_stage_boundaries(fixture_emp, cid, journey, day, stage):
    assert stage_for(journey, day)[0] == stage, cid
    fixture_emp(journey, done=[CODE["A1"]] if journey == "ONBOARDING" else [CODE["B1"]])
    assert ev_at(day)["stage"] == stage, cid


def test_STG_X_01_outside_the_window_is_graceful(fixture_emp):
    fixture_emp(done=ALL_A_DONE)
    ev = ev_at(91)
    assert ev["stage"] and ev["overall"] == "GREEN" and not ev["signals"]
    fixture_emp("MOBILITY", move_type="ROLE_CHANGE", done=[e for c, e, *_ in STEPS_B if c not in ("B6", "B7", "B8", "B9")])
    ev = ev_at(61)
    assert ev["stage"] and ev["overall"] == "GREEN" and not ev["signals"]


def test_STG_X_05_day_rolls_over_at_dubai_midnight():
    utc = dt.timezone.utc
    before = config.today(dt.datetime(2026, 10, 21, 19, 59, tzinfo=utc))   # 23:59 Dubai
    after = config.today(dt.datetime(2026, 10, 21, 20, 1, tzinfo=utc))     # 00:01 Dubai, still 21 Oct in UTC
    assert before == dt.date(2026, 10, 21) and after == dt.date(2026, 10, 22)
