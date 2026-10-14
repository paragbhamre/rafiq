"""Rafiq — Employee Journey Companion. FastAPI application.

Identity: every person signs in with their own account (app/auth.py). The server issues a signed,
HttpOnly session cookie and derives role and identity from it alone. In a pilot, sign-in is replaced
by SSO (e.g. Microsoft Entra ID / OIDC) claims; the access rules below stay the same.
"""
import datetime as dt
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agents, auth, companion, config, llm
from .data import consent_active, pack, set_consent, state
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
# Access control (identity from the signed session only)
# --------------------------------------------------------------------------
def _actor(u):
    return f"{u['role']}:{u['id']}"


def _emp_or_404(emp_id):
    if emp_id not in pack.employees:
        raise HTTPException(404, "Unknown employee")
    return pack.employees[emp_id]


def require_self(emp_id: str, u: dict = Depends(auth.current_user)):
    """Only the employee themself can use the companion or see their own data."""
    _emp_or_404(emp_id)
    if not (u["role"] == "employee" and u["id"] == emp_id):
        state.audit(_actor(u), "access_denied", emp_id, "Attempted access to employee-only data")
        raise HTTPException(403, "The companion works for the employee. Only they can see their own conversations and data.")
    return u


def require_role(*roles):
    def dep(u: dict = Depends(auth.current_user)):
        if u["role"] not in roles:
            raise HTTPException(403, "Your account can't open this page.")
        return u
    return dep


# --------------------------------------------------------------------------
# Meta and sign-in
# --------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True, "as_of": config.AS_OF.isoformat(), "ai_writer": llm.status()["configured"], "storage": state.health(), "pack": "synthetic" if config.IS_REFERENCE_PACK else config.DATA_DIR.name,
            "employees": len(pack.employees), "synthetic_data": True}


class LoginIn(BaseModel):
    username: str
    password: str


@app.get("/api/demo-accounts")
def demo_accounts():
    """Featured synthetic accounts for the sign-in page. Usernames only, never passwords."""
    return auth.demo_accounts()


UI_REFS = ["POL-PRV-001 §1.2", "POL-PRV-001 §4.1", "POL-PRV-001 §5.1", "POL-PRV-001 §5.2", "POL-PRV-001 §5.3",
           "POL-PRV-001 §6.2", "POL-PRV-001 §8.1"]


def ui_cites():
    """Privacy references the interface shows, resolved to the loaded pack (None = not found, hide it)."""
    from .policies import library
    return {r: library.resolve(r) for r in UI_REFS}


def cref(ref, fallback="the privacy policy"):
    from .policies import library
    return library.resolve(ref) or fallback


@app.post("/api/login")
def login(body: LoginIn, request: Request, response: Response):
    if request.headers.get("x-rafiq-request") != "1":
        raise HTTPException(403, "Missing request header.")
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    key = auth.throttle(ip, body.username)
    acct = auth.directory.find(body.username)
    if not acct or not auth.check_password(acct, body.password):
        auth.record_fail(key)
        raise HTTPException(401, "That username and password don't match.")
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    response.set_cookie(auth.COOKIE, auth.issue(acct), httponly=True, secure=secure, samesite="lax",
                        max_age=int(auth.SESSION_HOURS * 3600), path="/")
    state.audit(_actor(acct), "signed_in", acct["id"] if acct["role"] == "employee" else "*", "Signed in")
    out = {"user": auth.public(acct), "home": auth.home_for(acct), "cite_map": ui_cites()}
    if acct["role"] == "employee":
        out["suggestions"] = auth.suggestions_for(acct["id"])
    return out


@app.post("/api/logout")
def logout(response: Response, u: dict = Depends(auth.current_user)):
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(u: dict = Depends(auth.current_user)):
    out = {"user": auth.public(u), "home": auth.home_for(u), "cite_map": ui_cites()}
    if u["role"] == "manager":
        out["team_size"] = sum(1 for e in pack.employees.values() if e["manager_id"] == u["id"])
    if u["role"] == "employee":
        out["suggestions"] = auth.suggestions_for(u["id"])
    return out


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


@app.get("/api/employee/{emp_id}/profile")
def profile(emp_id: str, u: dict = Depends(require_self)):
    """The employee's own record, as held in the HR system (the pack). Only they can open it."""
    e = pack.employees[emp_id]
    out = _public_employee(e)
    out["manager_id"] = e.get("manager_id", "")
    out["username"] = u.get("username", "")
    return out


@app.get("/api/employee/{emp_id}/journey")
def journey(emp_id: str, u: dict = Depends(require_self)):
    ev = evaluate(emp_id)
    ev["employee"] = _public_employee(pack.employees[emp_id])
    return ev


@app.get("/api/employee/{emp_id}/brief")
def brief(emp_id: str, lang: str = "en", u: dict = Depends(require_self)):
    return companion.brief(emp_id, lang)


@app.post("/api/employee/{emp_id}/chat")
def chat(emp_id: str, body: ChatIn, u: dict = Depends(require_self)):
    if not body.message.strip():
        raise HTTPException(400, "Empty message")
    return companion.chat(emp_id, body.message, body.lang)


@app.post("/api/employee/{emp_id}/actions")
def run_action(emp_id: str, body: ActionIn, u: dict = Depends(require_self)):
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
def notifications(emp_id: str, u: dict = Depends(require_self)):
    return state.notifications(emp_id, 30)


@app.get("/api/employee/{emp_id}/mydata")
def mydata(emp_id: str, u: dict = Depends(require_self)):
    """Everything held about the employee (POL-PRV-001 §4.1)."""
    ev = evaluate(emp_id)
    active = consent_active(emp_id)
    pulse = []
    for p in pack.pulse.get(emp_id, []):
        status = p["consent_status"] if active else "WITHDRAWN"
        pulse.append({**p, "effective_consent": status,
                      "used_by_companion": status == "ACTIVE",
                      "deletion_due": None if status == "ACTIVE" else (config.AS_OF + dt.timedelta(days=30)).isoformat()})
    cases = state.cases(employee_id=emp_id)
    return {
        "profile": _public_employee(pack.employees[emp_id]),
        "consent": {"pulse_active": active,
                    "log": state.consent_log(emp_id)},
        "journey_events": pack.events.get(emp_id, []),
        "requests": ev["requests"],
        "pulse": pulse,
        "signals_about_me": ev["signals"],
        "shared_with_others": [{"case_id": c["case_id"], "type": c["type"], "owner": c["owner"],
                                "hrbp": c["hrbp"]["name"], "shared_items": c["shared_items"],
                                "created_at": c["created_at"], "status": c["status"]} for c in cases],
        "manager_can_see": f"Journey step progress only (no conversations, pulse or sentiment). See {cref('POL-PRV-001 §5.1')}.",
        "conversation_messages": state.conv_count(emp_id),
        "retention": f"Conversation history is deleted after 90 days, or now if you choose ({cref('POL-PRV-001 §8.1')}).",
        "access_log": state.audit_for(emp_id, 20),
    }


@app.post("/api/employee/{emp_id}/consent")
def consent(emp_id: str, body: ConsentIn, u: dict = Depends(require_self)):
    set_consent(emp_id, body.active, f"employee:{emp_id}")
    return {"ok": True, "pulse_active": consent_active(emp_id)}


@app.delete("/api/employee/{emp_id}/conversations")
def forget(emp_id: str, u: dict = Depends(require_self)):
    state.conv_delete(emp_id)
    state.audit(f"employee:{emp_id}", "conversation_deleted", emp_id, "Employee deleted conversation history")
    return {"ok": True}


# --------------------------------------------------------------------------
# Manager: step progress for their own team only
# --------------------------------------------------------------------------
@app.get("/api/manager/{mgr_id}/team")
def team(mgr_id: str, u: dict = Depends(auth.current_user)):
    if not (u["role"] == "manager" and u["id"] == mgr_id):
        raise HTTPException(403, "Managers can only see their own team")
    members = [e for e in pack.employees.values() if e["manager_id"] == mgr_id]
    state.audit(f"manager:{mgr_id}", "team_view", "*", f"Viewed step progress for {len(members)} people")
    return {"manager": pack.managers.get(mgr_id), "visibility": f"Journey step progress only ({cref('POL-PRV-001 §5.1')})",
            "team": [manager_view(e["employee_id"]) for e in members]}


# --------------------------------------------------------------------------
# HRBP and escalation owners: cases
# --------------------------------------------------------------------------
class CaseIn(BaseModel):
    status: str | None = None
    note: str | None = None


def _case_scope(u):
    if u["role"] == "hrbp":
        return state.cases(hrbp_id=u["id"])
    if u["role"] == "owner":
        return state.cases(owner_name=u["id"])
    raise HTTPException(403, "Only HR Business Partners and named owners can see cases")


@app.get("/api/cases")
def cases(u: dict = Depends(auth.current_user)):
    items = _case_scope(u)
    order = {"OPEN": 0, "ACKNOWLEDGED": 1, "RESOLVED": 2}
    return sorted(items, key=lambda c: (order.get(c["status"], 3), c["type"] != "EMPLOYEE_HANDOFF", c["created_at"]), reverse=False)


@app.post("/api/cases/{case_id}")
def update_case(case_id: str, body: CaseIn, u: dict = Depends(auth.current_user)):
    if case_id not in {c["case_id"] for c in _case_scope(u)}:
        raise HTTPException(404, "Case not found in your scope")
    if body.status and body.status not in ("OPEN", "ACKNOWLEDGED", "RESOLVED"):
        raise HTTPException(400, "Bad status")
    return agents.update_case(case_id, body.status, body.note, actor=_actor(u))


# --------------------------------------------------------------------------
# Insights: where journeys stall (aggregated, small groups suppressed)
# --------------------------------------------------------------------------
def _site_group(loc):
    return loc if loc.startswith("Dubai") else "Outstations (all)"


@app.get("/api/insights/stalls")
def stalls(group: str = "location", u: dict = Depends(auth.current_user)):
    if u["role"] not in ("hrbp", "owner", "admin"):
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
            "note": "Aggregated and anonymised; cells with fewer than 10 employees are hidden (" + cref("POL-PRV-001 §5.3") + "). "
                    "Rate = steps currently late or completed late, divided by steps due."}


# --------------------------------------------------------------------------
# Policy library (not personal data)
# --------------------------------------------------------------------------
@app.get("/api/policies")
def policies(u: dict = Depends(auth.current_user)):
    from .policies import library
    return list(library.policies.values())


@app.get("/api/policies/{policy_id}")
def policy(policy_id: str, u: dict = Depends(auth.current_user)):
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
def reset(u: dict = Depends(require_role("admin"))):
    state.reset()
    seed_early_warnings()
    state.audit(_actor(u), "demo_reset", "*", "Demo state reset")
    return {"ok": True}


@app.get("/api/admin/credentials", response_class=PlainTextResponse)
def credentials(u: dict = Depends(require_role("admin"))):
    """Credentials sheet for judges (per-user password mode). Admin only; never stored in the repo."""
    state.audit(_actor(u), "credentials_exported", "*", "Exported demo credentials")
    return PlainTextResponse(auth.credentials_csv(), headers={"Content-Disposition": "attachment; filename=rafiq-demo-accounts.csv"})


app.mount("/static", StaticFiles(directory=str(config.ROOT / "static")), name="static")


@app.get("/")
def index():
    return FileResponse(str(config.ROOT / "static" / "index.html"))
