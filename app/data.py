"""Loads the data pack (read-only) and holds runtime state (requests raised, cases, consent, audit).

The pack is never modified. Everything the prototype creates lives in the
runtime store (app/store.py): PostgreSQL when DATABASE_URL is set, otherwise a local JSON file.
"""
import csv
import datetime as dt
import json
import re
import threading
import uuid
from collections import defaultdict

from pathlib import Path

from . import config, schema
from .packio import load_table, read_mapping  # noqa: F401  (re-exported)



class PackError(RuntimeError):
    pass


class Pack:
    """Read-only data pack, normalised to Rafiq's schema."""

    def __init__(self, pack_dir=None, strict=True):
        self.dir = Path(pack_dir or config.DATA_DIR)
        self.mapping = read_mapping(self.dir)
        self.issues = []
        tables = {}
        for logical in schema.FILES:
            rows, issues = load_table(logical, self.dir, self.mapping)
            tables[logical] = rows
            self.issues += issues
        blockers = [i["msg"] for i in self.issues if i["level"] == "BLOCKER"]
        if blockers and strict:
            raise PackError("Data pack can't be loaded:\n  - " + "\n  - ".join(blockers) +
                            "\nRun: python tools/ingest.py " + str(self.dir))
        self.employees = {e["employee_id"]: e for e in tables["employees"]}
        self.events = defaultdict(list)
        for r in tables["events"]:
            self.events[r["employee_id"]].append(r)
        self.requests = defaultdict(list)
        for r in tables["requests"]:
            self.requests[r["employee_id"]].append(r)
        self.pulse = defaultdict(list)
        for r in tables["pulse"]:
            self.pulse[r["employee_id"]].append(r)
        self.managers = {}
        for e in self.employees.values():
            self.managers.setdefault(e["manager_id"], e["manager_name"])
        self.hrbps = {}
        for e in self.employees.values():
            self.hrbps.setdefault(e["hrbp_id"], e["hrbp_name"])
        self._tables = tables
        self.shift_days = 0          # days the pack's dates have been moved forward
        self._shift_lock = threading.Lock()
        self.shift_to(config.pack_shift_days())

    # ----------------------------------------------------------------------
    # Date shift: keeps every seeded journey on the same day relative to today (see config.py).
    # Rows are changed in place, so modules that imported `pack` see the new dates.
    # ----------------------------------------------------------------------
    def shift_to(self, total_days):
        with self._shift_lock:
            delta = total_days - self.shift_days
            if not delta:
                return
            for logical, rows in self._tables.items():
                cols = schema.DATES.get(logical, [])
                texts = _TEXT_COLS.get(logical, [])
                for r in rows:
                    for c in cols:
                        if r.get(c):
                            r[c] = _shift_iso(r[c], delta)
                    for c in texts:
                        if r.get(c):
                            r[c] = _shift_text(r[c], delta)
            self.shift_days = total_days

    def ensure_current(self):
        """Re-apply the shift if the day has changed since the pack was loaded (cheap when it hasn't)."""
        if self.shift_days != config.pack_shift_days():
            self.shift_to(config.pack_shift_days())


# Free-text columns that mention dates such as "09 Oct" or "26 Sept"
_TEXT_COLS = {"events": ["notes"], "requests": ["subject", "description"], "pulse": ["comment"]}
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_TEXT_DATE = re.compile(r"\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\b")


def _shift_iso(value, days):
    """Shift an ISO date or timestamp, keeping any time and offset."""
    d = dt.date.fromisoformat(value[:10]) + dt.timedelta(days=days)
    return d.isoformat() + value[10:]


def _shift_text(text, days):
    year = config.PACK_REFERENCE_DATE.year

    def repl(m):
        day, mon = m.group(1), m.group(2)
        try:
            d = dt.date(year, _MONTHS.index(mon[:3]) + 1, int(day)) + dt.timedelta(days=days)
        except ValueError:
            return m.group(0)
        out_mon = "Sept" if (mon == "Sept" and d.month == 9) else _MONTHS[d.month - 1]
        return f"{d.day:02d} {out_mon}" if len(day) == 2 else f"{d.day} {out_mon}"
    return _TEXT_DATE.sub(repl, text)


pack = Pack()
from .store import _lock, make_store  # noqa: E402

state = make_store()


# --------------------------------------------------------------------------
# Consent (runtime overrides the pack's initial opt-in)
# --------------------------------------------------------------------------
def consent_active(employee_id):
    c = state.consent_get(employee_id)
    if c is not None:
        return c == "ACTIVE"
    return pack.employees[employee_id]["pulse_opt_in"] == "true"


def set_consent(employee_id, active, actor):
    state.consent_set(employee_id, "ACTIVE" if active else "WITHDRAWN", actor)
    state.audit(actor, "consent_" + ("granted" if active else "withdrawn"), employee_id,
                "Pulse feedback consent " + ("granted" if active else "withdrawn"))


def usable_pulse(employee_id):
    """Pulse rows the companion may use: consent active now AND row-level consent ACTIVE."""
    if not consent_active(employee_id):
        return []
    return [p for p in pack.pulse.get(employee_id, []) if p["consent_status"] == "ACTIVE"]


def all_requests(employee_id):
    """Pack requests plus anything raised through the prototype."""
    created = state.requests_for(employee_id)
    return pack.requests.get(employee_id, []) + created
