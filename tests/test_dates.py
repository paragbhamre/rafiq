"""Rafiq runs on today's date; the pack's dates are moved so seeded journeys look the same on any day.

Catalogue cases: STG-X-02 (today's date), STG-X-04 (scenarios hold on any date), STG-X-05 (Dubai midnight).
"""
import datetime as dt

import pytest

from app import config
from app.data import _shift_text, pack
from app.journey import evaluate


def _snapshot():
    """Day, stage and every step's status for every employee (what the scenarios depend on)."""
    out = {}
    for emp_id in pack.employees:
        ev = evaluate(emp_id)
        out[emp_id] = (ev["journey_day"], ev["stage"], tuple((s["code"], s["status"]) for s in ev["steps"]))
    return out


@pytest.fixture
def on_date(monkeypatch):
    """Pretend today is a given date, then put the pack back."""
    def go(d):
        monkeypatch.setattr(config, "FREEZE_DATE", d)
        pack.ensure_current()
    yield go
    monkeypatch.undo()
    pack.ensure_current()


def test_today_is_the_real_date_not_a_fixed_one():
    # STG-X-02
    assert config.FREEZE_DATE is None, "the test run must not freeze the date"
    assert config.AS_OF == dt.datetime.now(config.TZ).date()


def test_pack_is_shifted_to_today():
    # Aisha (S01) is on Day 5 whatever today is
    aisha = pack.employees["EMP-1001"]
    assert dt.date.fromisoformat(aisha["journey_anchor_date"]) == config.AS_OF - dt.timedelta(days=5)
    assert evaluate("EMP-1001")["journey_day"] == 5


@pytest.mark.parametrize("offset", [-30, 1, 7, 30, 120])
def test_scenarios_hold_on_any_date(on_date, offset):
    # STG-X-04: every employee's day, stage and step statuses are identical on any run date
    on_date(config.PACK_REFERENCE_DATE)
    reference = _snapshot()
    on_date(config.PACK_REFERENCE_DATE + dt.timedelta(days=offset))
    assert pack.shift_days == offset
    assert _snapshot() == reference


def test_shift_round_trips(on_date):
    on_date(config.PACK_REFERENCE_DATE)
    before = pack.employees["EMP-1002"]["journey_anchor_date"], pack.requests["EMP-1002"][0]["created_at"]
    on_date(config.PACK_REFERENCE_DATE + dt.timedelta(days=45))
    on_date(config.PACK_REFERENCE_DATE)
    assert (pack.employees["EMP-1002"]["journey_anchor_date"], pack.requests["EMP-1002"][0]["created_at"]) == before


def test_day_changes_at_dubai_midnight(monkeypatch):
    # STG-X-05: 20:30 UTC on 21 Oct is 00:30 on 22 Oct in Dubai
    monkeypatch.setattr(config, "FREEZE_DATE", None)
    monkeypatch.setattr(config, "TZ", __import__("zoneinfo").ZoneInfo("Asia/Dubai"))
    utc = dt.timezone.utc
    assert config.today(dt.datetime(2026, 10, 21, 19, 59, tzinfo=utc)) == dt.date(2026, 10, 21)
    assert config.today(dt.datetime(2026, 10, 21, 20, 1, tzinfo=utc)) == dt.date(2026, 10, 22)


def test_dates_in_free_text_move_too():
    assert _shift_text("New joiner started 09 Oct. Permit issued 26 Sept.", 7) == "New joiner started 16 Oct. Permit issued 03 Oct."
    assert _shift_text("Booked 1 Oct", 31) == "Booked 1 Nov"
    assert _shift_text("three days ago, grade G6", 7) == "three days ago, grade G6"
