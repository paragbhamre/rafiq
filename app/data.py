"""Loads the data pack (read-only) and holds runtime state (requests raised, cases, consent, audit).

The pack is never modified. Everything the prototype creates lives in RUNTIME_DIR/state.json
and can be reset with POST /api/admin/reset.
"""
import csv
import datetime as dt
import json
import threading
import uuid
from collections import defaultdict

from . import config

_lock = threading.RLock()


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


class State:
    """Mutable runtime state with JSON persistence."""

    def __init__(self):
        self.path = config.RUNTIME_DIR / "state.json"
        self.reset(load=True)

    def reset(self, load=False):
        with _lock:
            self.data = {"requests": [], "cases": [], "consent": {}, "consent_log": [],
                         "audit": [], "notifications": [], "conversations": {}, "seeded_warnings": False}
            if load and self.path.exists():
                try:
                    self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
                except (json.JSONDecodeError, OSError):
                    pass
            self.save()

    def save(self):
        with _lock:
            config.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def now_iso():
        t = dt.datetime.combine(config.AS_OF, dt.datetime.now().time()).replace(microsecond=0)
        return t.isoformat() + "+04:00"

    @staticmethod
    def new_id(prefix):
        return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"

    def audit(self, actor, action, employee_id, detail):
        with _lock:
            self.data["audit"].append({"at": self.now_iso(), "actor": actor, "action": action,
                                       "employee_id": employee_id, "detail": detail})
            self.save()

    def notify(self, employee_id, text, text_ar=None, kind="info", ref=None):
        with _lock:
            self.data["notifications"].append({"id": self.new_id("NTF"), "at": self.now_iso(),
                                               "employee_id": employee_id, "text": text,
                                               "text_ar": text_ar or text, "kind": kind, "ref": ref})
            self.save()


pack = Pack()
state = State()


# --------------------------------------------------------------------------
# Consent (runtime overrides the pack's initial opt-in)
# --------------------------------------------------------------------------
def consent_active(employee_id):
    c = state.data["consent"].get(employee_id)
    if c is not None:
        return c == "ACTIVE"
    return pack.employees[employee_id]["pulse_opt_in"] == "true"


def set_consent(employee_id, active, actor):
    with _lock:
        state.data["consent"][employee_id] = "ACTIVE" if active else "WITHDRAWN"
        state.data["consent_log"].append({"at": state.now_iso(), "employee_id": employee_id,
                                          "status": "ACTIVE" if active else "WITHDRAWN", "by": actor})
        state.save()
    state.audit(actor, "consent_" + ("granted" if active else "withdrawn"), employee_id,
                "Pulse feedback consent " + ("granted" if active else "withdrawn"))


def usable_pulse(employee_id):
    """Pulse rows the companion may use: consent active now AND row-level consent ACTIVE."""
    if not consent_active(employee_id):
        return []
    return [p for p in pack.pulse.get(employee_id, []) if p["consent_status"] == "ACTIVE"]


def all_requests(employee_id):
    """Pack requests plus anything raised through the prototype."""
    created = [r for r in state.data["requests"] if r["employee_id"] == employee_id]
    return pack.requests.get(employee_id, []) + created
