"""Loads the data pack (read-only) and holds runtime state (requests raised, cases, consent, audit).

The pack is never modified. Everything the prototype creates lives in the
runtime store (app/store.py): PostgreSQL when DATABASE_URL is set, otherwise a local JSON file.
"""
import csv
import datetime as dt
import json
import threading
import uuid
from collections import defaultdict

from . import config



def _read_csv(name):
    path = config.DATA_DIR / name
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Pack:
    """Read-only synthetic data pack."""

    def __init__(self):
        self.employees = {e["employee_id"]: e for e in _read_csv("employees.csv")}
        self.events = defaultdict(list)
        for r in _read_csv("journey_events.csv"):
            self.events[r["employee_id"]].append(r)
        self.requests = defaultdict(list)
        for r in _read_csv("service_requests.csv"):
            self.requests[r["employee_id"]].append(r)
        self.pulse = defaultdict(list)
        for r in _read_csv("pulse_feedback.csv"):
            self.pulse[r["employee_id"]].append(r)
        self.managers = {}
        for e in self.employees.values():
            self.managers.setdefault(e["manager_id"], e["manager_name"])
        self.hrbps = {}
        for e in self.employees.values():
            self.hrbps.setdefault(e["hrbp_id"], e["hrbp_name"])


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
