"""Accounts and sessions.

Every person in the pack gets their own account:
  employees    aisha.rahman          (or their ID, e.g. EMP-1001)
  managers     mgr.hassan.brown      (or MGR-204)
  HR partners  hr.nadia.farouk       (or HRBP-01)
  owners       owner.priya.raman     (named escalation owners)
  admin        admin                 (demo reset only; enabled only when RAFIQ_ADMIN_PASSWORD is set)

Passwords (RAFIQ_PASSWORD_MODE):
  shared   - one demo password for all non-admin accounts (RAFIQ_DEMO_PASSWORD). Default.
  per_user - a distinct password per account, derived from RAFIQ_SESSION_SECRET; the admin can
             download the credentials sheet. Nothing is stored in the repository.

Identity comes ONLY from a signed, HttpOnly session cookie set by the server. Client-sent headers
or parameters never decide who someone is. In a pilot this module is replaced by SSO (e.g. Microsoft
Entra ID / OIDC) and the same role checks apply.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from . import config
from .data import pack

COOKIE = "rafiq_session"
SESSION_HOURS = float(os.getenv("RAFIQ_SESSION_HOURS", "8"))
SECRET = (os.getenv("RAFIQ_SESSION_SECRET") or secrets.token_hex(32)).encode()
PASSWORD_MODE = os.getenv("RAFIQ_PASSWORD_MODE", "shared").lower()
DEMO_PASSWORD = os.getenv("RAFIQ_DEMO_PASSWORD", "")
ADMIN_PASSWORD = os.getenv("RAFIQ_ADMIN_PASSWORD", "")
# Local runs only: a hosted deployment (Render sets RENDER=true) must set RAFIQ_DEMO_PASSWORD, or sign-in stays closed.
DEFAULT_DEV_PASSWORD = "" if os.getenv("RENDER") else "rafiq-demo"

MAX_FAILS, FAIL_WINDOW_S = 8, 15 * 60
_fails = defaultdict(deque)

# Seeded scenario employees shown on the sign-in page (synthetic people)
FEATURED = {
    "EMP-1001": "Day 5, no laptop", "EMP-1002": "Visa stalled, flies next week",
    "EMP-1003": "London move, allowance pending", "EMP-1004": "Role change, endorsement late",
    "EMP-1005": "Feels lost, no buddy", "EMP-1006": "Consent withdrawn",
    "EMP-1007": "Arabic, housing allowance", "EMP-1008": "Lands in 2 days, no housing",
    "EMP-1009": "Smooth journey", "EMP-1010": "Moved to DWC, no access",
    "EMP-1011": "Privacy question", "EMP-1012": "Out-of-policy question",
    "EMP-1013": "Singapore tomorrow, no permit", "EMP-1014": "UAE national, Arabic",
}


def _slug(*parts):
    return ".".join(re.sub(r"[^a-z0-9]", "", p.lower()) for p in parts if p)


class Directory:
    def __init__(self):
        self.users = {}     # username -> account
        self.alias = {}     # lower-case ID -> username
        taken = set()

        def add(username, **acct):
            base, n = username, 2
            while username in taken:
                username, n = f"{base}{n}", n + 1
            taken.add(username)
            acct["username"] = username
            self.users[username] = acct
            if acct.get("id"):
                self.alias[acct["id"].lower()] = username
            return acct

        for e in sorted(pack.employees.values(), key=lambda x: x["employee_id"]):
            add(_slug(e["first_name"], e["last_name"].replace(" ", "")), role="employee", id=e["employee_id"],
                name=f"{e['first_name']} {e['last_name']}", lang=e["preferred_language"],
                tag=FEATURED.get(e["employee_id"]))
        for mid, name in sorted(pack.managers.items()):
            add("mgr." + _slug(*name.replace("Al ", "Al").split(" ", 1)), role="manager", id=mid, name=name)
        for hid, name in sorted(pack.hrbps.items()):
            add("hr." + _slug(*name.replace("Al ", "Al").split(" ", 1)), role="hrbp", id=hid, name=name)
        for role, (name, _c) in config.ESCALATION_CONTACTS.items():
            if role == "Recruiter":
                continue
            add("owner." + _slug(*name.replace("Al ", "Al").split(" ", 1)), role="owner", id=name, name=name, title=role)
        if ADMIN_PASSWORD:
            add("admin", role="admin", id="admin", name="Demo administrator")

    def find(self, login):
        login = (login or "").strip().lower()
        return self.users.get(login) or self.users.get(self.alias.get(login, ""))


directory = Directory()


# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------
def password_for(acct):
    if acct["role"] == "admin":
        return ADMIN_PASSWORD
    if PASSWORD_MODE == "per_user":
        raw = hmac.new(SECRET, ("pw:" + acct["username"]).encode(), hashlib.sha256).digest()
        return base64.b32encode(raw).decode()[:10].lower()
    return DEMO_PASSWORD or DEFAULT_DEV_PASSWORD


def check_password(acct, password):
    expected = password_for(acct)
    return bool(expected) and hmac.compare_digest(expected.encode(), (password or "").encode())


def throttle(ip, login):
    key = f"{ip}|{(login or '').lower()}"
    q = _fails[key]
    now = time.time()
    while q and now - q[0] > FAIL_WINDOW_S:
        q.popleft()
    if len(q) >= MAX_FAILS:
        raise HTTPException(429, "Too many failed sign-in attempts. Try again in 15 minutes.")
    return key


def record_fail(key):
    _fails[key].append(time.time())


# --------------------------------------------------------------------------
# Signed session tokens
# --------------------------------------------------------------------------
def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue(acct):
    payload = {"u": acct["username"], "r": acct["role"], "i": acct["id"], "exp": int(time.time() + SESSION_HOURS * 3600),
               "n": secrets.token_hex(8)}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(SECRET, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify(token):
    try:
        body, sig = token.split(".", 1)
        good = _b64(hmac.new(SECRET, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(good, sig):
            return None
        payload = json.loads(_unb64(body))
        if payload["exp"] < time.time():
            return None
        acct = directory.users.get(payload["u"])
        if not acct or acct["role"] != payload["r"] or acct["id"] != payload["i"]:
            return None
        return acct
    except Exception:  # noqa: BLE001 - any malformed token is simply "not signed in"
        return None


def current_user(request: Request):
    acct = verify(request.cookies.get(COOKIE, ""))
    if not acct:
        raise HTTPException(401, "Please sign in.")
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.headers.get("x-rafiq-request") != "1":
        raise HTTPException(403, "Missing request header.")  # CSRF guard: cross-site forms cannot set it
    return acct


def public(acct):
    return {k: acct.get(k) for k in ("username", "role", "id", "name", "title", "lang", "tag")}


def home_for(acct):
    return {"employee": "journey", "manager": "team", "hrbp": "cases", "owner": "cases", "admin": "admin"}[acct["role"]]


def demo_accounts():
    """Featured accounts for the sign-in page (usernames only, never passwords)."""
    emps = [public(a) for a in directory.users.values() if a["role"] == "employee" and a.get("tag")]
    feat_mgr_ids = {pack.employees[e["id"]]["manager_id"] for e in emps}
    feat_hrbp_ids = {pack.employees[e["id"]]["hrbp_id"] for e in emps}
    mgrs = []
    for a in directory.users.values():
        if a["role"] == "manager" and a["id"] in feat_mgr_ids:
            team = [pack.employees[e["id"]]["first_name"] for e in emps if pack.employees[e["id"]]["manager_id"] == a["id"]]
            mgrs.append({**public(a), "tag": "Manages " + ", ".join(team)})
    hrbps = []
    for a in directory.users.values():
        if a["role"] == "hrbp":
            people = [pack.employees[e["id"]]["first_name"] for e in emps if pack.employees[e["id"]]["hrbp_id"] == a["id"]]
            hrbps.append({**public(a), "tag": ("Partner for " + ", ".join(people)) if people else "HR Business Partner",
                          "featured": a["id"] in feat_hrbp_ids})
    owners = [{**public(a), "tag": a.get("title")} for a in directory.users.values() if a["role"] == "owner"]
    return {"employees": emps, "managers": mgrs, "hrbps": hrbps, "owners": owners,
            "counts": {r: sum(1 for a in directory.users.values() if a["role"] == r)
                       for r in ("employee", "manager", "hrbp", "owner")},
            "password_mode": PASSWORD_MODE, "admin_enabled": bool(ADMIN_PASSWORD)}


def credentials_csv():
    rows = ["username,id,role,name,password"]
    for a in directory.users.values():
        if a["role"] == "admin":
            continue
        rows.append(f"{a['username']},{a['id']},{a['role']},\"{a['name']}\",{password_for(a)}")
    return "\n".join(rows) + "\n"
