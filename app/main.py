"""Rafiq — Employee Journey Companion. FastAPI application.

Demo identity: the front end sends X-Rafiq-Role (employee | manager | hrbp | owner) and X-Rafiq-User.
In a pilot this is replaced by SSO (e.g. Microsoft Entra ID) claims; the access rules stay the same.
"""
import datetime as dt
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agents, companion, config, llm
from .data import _lock, consent_active, pack, set_consent, state
from .journey import evaluate, manager_view, operational_signals, seed_early_warnings

@asynccontextmanager
async def lifespan(_app):
    seed_early_warnings()
    yield


app = FastAPI(title="Rafiq — Employee Journey Companion", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def _headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# --------------------------------------------------------------------------
# Access control
# --------------------------------------------------------------------------
class Who(BaseModel):
    role: str
    user: str


def who(x_rafiq_role: str = Header("employee"), x_rafiq_user: str = Header("")) -> Who:
    return Who(role=x_rafiq_role.lower(), user=x_rafiq_user)


def _emp_or_404(emp_id):
    if emp_id not in pack.employees:
        raise HTTPException(404, "Unknown employee")
    return pack.employees[emp_id]


def require_self(emp_id: str, w: Who = Depends(who)):
    """Only the employee themself can use the companion or see their own data."""
    _emp_or_404(emp_id)
    if not (w.role == "employee" and w.user == emp_id):
        state.audit(f"{w.role}:{w.user}", "access_denied", emp_id, "Attempted access to employee-only data")
        raise HTTPException(403, "The companion works for the employee. Only they can see their own conversations and data.")
    return w


# --------------------------------------------------------------------------
# Meta
# --------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True, "as_of": config.AS_OF.isoformat(), "llm": llm.status(),
            "employees": len(pack.employees), "synthetic_data": True}


@app.get("/api/personas")
def personas():
    """Demo persona picker (synthetic people only)."""
    emps = []
    for e in pack.employees.values():
        ev = evaluate(e["employee_id"])
        emps.append({"id": e["employee_id"], "name": f"{e['first_name']} {e['last_name']}",
                     "journey": e["journey_type"], "stage": ev["stage_label"], "day": ev["journey_day"],
                     "role_title": e["role_title"], "location": e["location"], "lang": e["preferred_language"],
                     "overall": ev["overall"], "seeded": e["employee_id"] < "EMP-1100"})
    emps.sort(key=lambda x: (not x["seeded"], x["id"]))
    team_size = defaultdict(int)
    for e in pack.employees.values():
        team_size[e["manager_id"]] += 1
    managers = sorted(({"id": k, "name": v, "team": team_size[k]} for k, v in pack.managers.items()),
                      key=lambda m: -m["team"])
    hrbps = [{"id": k, "name": v} for k, v in sorted(pack.hrbps.items())]
    owners = [{"id": name, "name": name, "role": role} for role, (name, _c) in config.ESCALATION_CONTACTS.items()
              if role != "Recruiter"]
    return {"employees": emps, "managers": managers, "hrbps": hrbps, "owners": owners}


# --------------------------------------------------------------------------
# Employee (self only)
# --------------------------------------------------------------------------
class ChatIn(BaseModel):
    message: str
    lang: str = "en"


class ActionIn(BaseModel):
    action: dict
    include_pulse: bool = False
    note: str = ""


class ConsentIn(BaseModel):
    active: bool


def _public_employee(e):
    keys = ["employee_id", "first_name", "last_name", "preferred_language", "journey_type", "journey_anchor_date",
            "move_effective_date", "move_type", "department", "role_title", "grade", "location", "from_location",
            "from_department", "from_role_title", "manager_name", "releasing_manager_name", "hrbp_name",
            "visa_required", "relocating_from_abroad", "accommodation_eligible", "family_status"]
    return {k: e.get(k, "") for k in keys}


@app.get("/api/employee/{emp_id}/journey")
def journey(emp_id: str, w: Who = Depends(require_self)):
    ev = evaluate(emp_id)
    ev["employee"] = _public_employee(pack.employees[emp_id])
    return ev


@app.get("/api/employee/{emp_id}/brief")
def brief(emp_id: str, lang: str = "en", w: Who = Depends(require_self)):
    return companion.brief(emp_id, lang)


@app.post("/api/employee/{emp_id}/chat")
def chat(emp_id: str, body: ChatIn, w: Who = Depends(require_self)):
    if not body.message.strip():
        raise HTTPException(400, "Empty message")
    return companion.chat(emp_id, body.message, body.lang)


@app.post("/api/employee/{emp_id}/actions")
def run_action(emp_id: str, body: ActionIn, w: Who = Depends(require_self)):
    """Employee-confirmed actions. Nothing here runs without the employee pressing the button."""
    a = body.action
    ev = evaluate(emp_id)
    t = a.get("type")
    if t == "RAISE_REQUEST":
        key = a.get("request_key")
        if key not in config.REQUEST_TYPES:
            raise HTTPException(400, "Unknown request type")
        step = next((s for s in ev["steps"] if s["code"] == a.get("step")), None)
        subject = config.REQUEST_TYPES[key]["label"]
        desc = f"Raised from the companion. Journey: {ev['stage_label']}, day {ev['journey_day']}."
        if step:
            desc += f" Step '{step['label']}' status {step['status']} (target {step['target_date']})."
        if body.note:
            desc += f" Employee note: {body.note}"
        res = agents.raise_request(emp_id, key, subject, desc, a.get("step"), actor=f"employee:{emp_id}")
        return {"ok": True, "kind": "request", **res}
    if t == "ESCALATE":
        include = bool(body.include_pulse and consent_active(emp_id))
        case = agents.escalate(emp_id, ev, a.get("step"), include, body.note, actor=f"employee:{emp_id}")
        return {"ok": True, "kind": "case", "case": case}
    if t == "ASK_HUMAN":
        res = agents.ask_human(emp_id, a.get("question", "")[:500], actor=f"employee:{emp_id}")
        return {"ok": True, "kind": "question", **res}
    raise HTTPException(400, "Unknown action")


@app.get("/api/employee/{emp_id}/notifications")
def notifications(emp_id: str, w: Who = Depends(require_self)):
    return [n for n in state.data["notifications"] if n["employee_id"] == emp_id][-30:][::-1]


@app.get("/api/employee/{emp_id}/mydata")
def mydata(emp_id: str, w: Who = Depends(require_self)):
    """Everything held about the employee (POL-PRV-001 §4.1)."""
    ev = evaluate(emp_id)
    active = consent_active(emp_id)
    pulse = []
    for p in pack.pulse.get(emp_id, []):
        status = p["consent_status"] if active else "WITHDRAWN"
        pulse.append({**p, "effective_consent": status,
                      "used_by_companion": status == "ACTIVE",
                      "deletion_due": None if status == "ACTIVE" else (config.AS_OF + dt.timedelta(days=30)).isoformat()})
    cases = [c for c in state.data["cases"] if c["employee_id"] == emp_id]
    return {
        "profile": _public_employee(pack.employees[emp_id]),
        "consent": {"pulse_active": active,
                    "log": [c for c in state.data["consent_log"] if c["employee_id"] == emp_id]},
        "journey_events": pack.events.get(emp_id, []),
        "requests": ev["requests"],
        "pulse": pulse,
        "signals_about_me": ev["signals"],
        "shared_with_others": [{"case_id": c["case_id"], "type": c["type"], "owner": c["owner"],
                                "hrbp": c["hrbp"]["name"], "shared_items": c["shared_items"],
                                "created_at": c["created_at"], "status": c["status"]} for c in cases],
        "manager_can_see": "Journey step progress only (no conversations, pulse or sentiment). See POL-PRV-001 §5.1.",
        "conversation_messages": len(state.data["conversations"].get(emp_id, [])),
        "retention": "Conversation history is deleted after 90 days, or now if you choose (POL-PRV-001 §8.1).",
        "access_log": [a for a in state.data["audit"] if a["employee_id"] == emp_id][-20:][::-1],
    }


@app.post("/api/employee/{emp_id}/consent")
def consent(emp_id: str, body: ConsentIn, w: Who = Depends(require_self)):
    set_consent(emp_id, body.active, f"employee:{emp_id}")
    return {"ok": True, "pulse_active": consent_active(emp_id)}


@app.delete("/api/employee/{emp_id}/conversations")
def forget(emp_id: str, w: Who = Depends(require_self)):
    with _lock:
        state.data["conversations"].pop(emp_id, None)
        state.save()
    state.audit(f"employee:{emp_id}", "conversation_deleted", emp_id, "Employee deleted conversation history")
    return {"ok": True}


# --------------------------------------------------------------------------
# Manager: step progress for their own team only
# --------------------------------------------------------------------------
@app.get("/api/manager/{mgr_id}/team")
def team(mgr_id: str, w: Who = Depends(who)):
    if not (w.role == "manager" and w.user == mgr_id):
        raise HTTPException(403, "Managers can only see their own team")
    members = [e for e in pack.employees.values() if e["manager_id"] == mgr_id]
    state.audit(f"manager:{mgr_id}", "team_view", "*", f"Viewed step progress for {len(members)} people")
    return {"manager": pack.managers.get(mgr_id), "visibility": "Journey step progress only (POL-PRV-001 §5.1)",
            "team": [manager_view(e["employee_id"]) for e in members]}


# --------------------------------------------------------------------------
# HRBP and escalation owners: cases
# --------------------------------------------------------------------------
class CaseIn(BaseModel):
    status: str | None = None
    note: str | None = None


def _case_scope(w: Who):
    if w.role == "hrbp":
        return [c for c in state.data["cases"] if c["hrbp"]["id"] == w.user]
    if w.role == "owner":
        return [c for c in state.data["cases"] if c["owner"]["name"] == w.user]
    raise HTTPException(403, "Only HR Business Partners and named owners can see cases")


@app.get("/api/cases")
def cases(w: Who = Depends(who)):
    items = _case_scope(w)
    order = {"OPEN": 0, "ACKNOWLEDGED": 1, "RESOLVED": 2}
    return sorted(items, key=lambda c: (order.get(c["status"], 3), c["type"] != "EMPLOYEE_HANDOFF", c["created_at"]), reverse=False)


@app.post("/api/cases/{case_id}")
def update_case(case_id: str, body: CaseIn, w: Who = Depends(who)):
    if case_id not in {c["case_id"] for c in _case_scope(w)}:
        raise HTTPException(404, "Case not found in your scope")
    if body.status and body.status not in ("OPEN", "ACKNOWLEDGED", "RESOLVED"):
        raise HTTPException(400, "Bad status")
    return agents.update_case(case_id, body.status, body.note, actor=f"{w.role}:{w.user}")


# --------------------------------------------------------------------------
# Insights: where journeys stall (aggregated, small groups suppressed)
# --------------------------------------------------------------------------
def _site_group(loc):
    return loc if loc.startswith("Dubai") else "Outstations (all)"


@app.get("/api/insights/stalls")
def stalls(group: str = "location", w: Who = Depends(who)):
    if w.role not in ("hrbp", "owner"):
        raise HTTPException(403, "Insights are for HR and service owners")
    key = (lambda e: _site_group(e["location"])) if group == "location" else (lambda e: e["department"])
    cells = defaultdict(lambda: {"applicable": 0, "open_issue": 0, "late_done": 0, "late_days": 0})
    totals = defaultdict(lambda: {"applicable": 0, "open_issue": 0, "late_done": 0, "late_days": 0, "label": "", "journey": ""})
    for e in pack.employees.values():
        ev = evaluate(e["employee_id"])
        g = key(e)
        for s in ev["steps"]:
            if s["code"] in ("OFFER_ACCEPTED", "MOVE_REQUESTED"):
                continue
            if dt.date.fromisoformat(s["target_date"]) > config.AS_OF and s["status"] not in ("DONE", "DONE_LATE"):
                continue  # not due yet
            for bucket in (cells[(s["code"], ev["journey_type"], g)], totals[(s["code"], ev["journey_type"])]):
                bucket["applicable"] += 1
                if s["status"] in ("STALLED", "AT_RISK"):
                    bucket["open_issue"] += 1
                    bucket["late_days"] += s["days_late"]
                elif s["status"] == "DONE_LATE":
                    bucket["late_done"] += 1
                    bucket["late_days"] += s["days_late"]
            totals[(s["code"], ev["journey_type"])]["label"] = s["label"]
            totals[(s["code"], ev["journey_type"])]["journey"] = ev["journey_type"]
    groups = sorted({k[2] for k in cells})
    rows = []
    for (code, jt), t in totals.items():
        if t["applicable"] < config.MIN_GROUP_SIZE:
            continue
        rate = (t["open_issue"] + t["late_done"]) / t["applicable"]
        row = {"step": code, "label": t["label"], "journey": jt, "applicable": t["applicable"],
               "open_issue": t["open_issue"], "late_done": t["late_done"], "rate": round(rate, 3),
               "avg_days_late": round(t["late_days"] / max(1, t["open_issue"] + t["late_done"]), 1), "cells": {}}
        for g in groups:
            c = cells.get((code, jt, g))
            if not c or c["applicable"] < config.MIN_GROUP_SIZE:
                row["cells"][g] = {"suppressed": True, "n": "<10" if c else 0}
            else:
                row["cells"][g] = {"suppressed": False, "n": c["applicable"],
                                   "rate": round((c["open_issue"] + c["late_done"]) / c["applicable"], 3)}
        rows.append(row)
    rows.sort(key=lambda r: -r["rate"])
    return {"group_by": group, "groups": groups, "rows": rows, "min_group_size": config.MIN_GROUP_SIZE,
            "note": "Aggregated and anonymised; cells with fewer than 10 employees are hidden (POL-PRV-001 §5.3). "
                    "Rate = steps currently late or completed late, divided by steps due."}


# --------------------------------------------------------------------------
# Policy library (not personal data)
# --------------------------------------------------------------------------
@app.get("/api/policies")
def policies():
    from .policies import library
    return list(library.policies.values())


@app.get("/api/policies/{policy_id}")
def policy(policy_id: str):
    from .policies import library
    meta = library.policies.get(policy_id)
    if not meta:
        raise HTTPException(404, "Unknown policy")
    return {**meta, "sections": [{"cite": s["cite"], "heading": s["heading"], "text": s["text"]}
                                 for s in library.sections if s["policy_id"] == policy_id]}


# --------------------------------------------------------------------------
# Admin (demo only)
# --------------------------------------------------------------------------
@app.post("/api/admin/reset")
def reset():
    state.reset()
    seed_early_warnings()
    return {"ok": True}


app.mount("/static", StaticFiles(directory=str(config.ROOT / "static")), name="static")


@app.get("/")
def index():
    return FileResponse(str(config.ROOT / "static" / "index.html"))
