"""Service agents and human handoffs.

The companion never changes an employee's situation by itself. It either
  (a) hands a complete, correctly routed request to a service agent (IT, L&D, Facilities, PRO,
      Payroll, Global Mobility, HR Operations, Security), which acknowledges it, or
  (b) opens a case owned by a NAMED human (escalation owner / HRBP).
In the prototype the service agents are simulated; in a pilot each adapter calls the real
workflow (e.g. ServiceNow, SAP SuccessFactors, Workday) behind the same interface.
"""
import datetime as dt

from . import config
from .data import pack, state, usable_pulse
from .journey import escalation_owner, step_def

TEAM_ESCALATION = {
    "IT Service Desk": "IT Service Delivery Manager", "Facilities": "Facilities Manager",
    "Government Relations (PRO)": "PRO Team Lead", "Payroll": "Payroll Manager",
    "Global Mobility": "Global Mobility Lead", "Learning & Development": "L&D Manager",
    "Security": "Security Duty Manager", "HR Operations": "HR Business Partner",
    "Line Management": "HR Business Partner", "HR Business Partnering": "HR Business Partner",
    "Talent Acquisition": "Recruiter",
}

AGENT_DESK = {
    "IT Service Desk": "IT Service Desk agent", "Learning & Development": "Learning agent",
    "Facilities": "Facilities agent", "Government Relations (PRO)": "Government Relations agent",
    "Payroll": "Payroll agent", "Global Mobility": "Global Mobility agent",
    "HR Operations": "HR Operations agent", "Security": "Security pass agent",
}

AGENT_REPLY = {
    "IT_LOAN_DEVICE": ("A loan laptop is reserved for you at the IT Service Desk. Collect it within 4 working hours with your temporary pass. Your permanent kit request stays open.",
                       "تم حجز جهاز حاسوب مؤقت لك لدى مكتب خدمات تقنية المعلومات. يمكنك استلامه خلال 4 ساعات عمل. يبقى طلب جهازك الدائم مفتوحاً."),
    "IT_EQUIPMENT": ("Your equipment request is with the IT Service Desk. Service level: 2 working days.",
                     "طلب المعدات لدى مكتب خدمات تقنية المعلومات. مستوى الخدمة: يوما عمل."),
    "IT_ACCESS": ("Your access request is with the IT access team. Service level: 1 working day after approval.",
                  "طلب الصلاحيات لدى فريق الصلاحيات. مستوى الخدمة: يوم عمل واحد بعد الموافقة."),
    "LD_REBOOK_INDUCTION": ("Learning & Development will rebook your induction into the next session (Mondays and Wednesdays). If you work shifts, they will choose a session that does not clash with your roster.",
                            "سيعيد فريق التعلم والتطوير حجز برنامج التعريف في أقرب جلسة (الإثنين والأربعاء) بما لا يتعارض مع جدول مناوبتك."),
    "LD_BOOK_TRAINING": ("Learning & Development will book your training within 3 working days.",
                         "سيحجز فريق التعلم والتطوير تدريبك خلال 3 أيام عمل."),
    "FAC_ACCOMMODATION": ("Facilities has your accommodation request. If permanent housing is not ready, temporary housing is provided from your arrival date.",
                          "استلم فريق المرافق طلب السكن. إذا لم يكن السكن الدائم جاهزاً يُوفَّر سكن مؤقت من تاريخ وصولك."),
    "PRO_VISA": ("Government Relations has your request for a visa update. They acknowledge within 1 working day.",
                 "استلم فريق العلاقات الحكومية طلب تحديث التأشيرة وسيرد خلال يوم عمل واحد."),
    "PAYROLL_ALLOWANCE": ("Payroll has your follow-up. Once your bank details are in the HR portal, payment is processed within 5 working days.",
                          "استلم فريق الرواتب متابعتك. بعد إدخال بياناتك البنكية في بوابة الموارد البشرية تتم المعالجة خلال 5 أيام عمل."),
    "MOBILITY_QUERY": ("Global Mobility has your question and will reply within 3 working days.",
                       "استلم فريق التنقل العالمي سؤالك وسيرد خلال 3 أيام عمل."),
    "HR_QUERY": ("HR Operations has your question and will reply within 3 working days.",
                 "استلم فريق عمليات الموارد البشرية سؤالك وسيرد خلال 3 أيام عمل."),
    "SEC_ID": ("Security has your staff ID request. Service level: 2 working days after your photo is received.",
               "استلم فريق الأمن طلب بطاقة الموظف. مستوى الخدمة: يوما عمل بعد استلام صورتك."),
}


def _emp(emp_id):
    return pack.employees[emp_id]


OPEN = ("OPEN", "IN_PROGRESS", "PENDING_INFO", "ACKNOWLEDGED")


def open_request(emp_id, key=None, subject=None):
    """An open request the companion already raised for this employee (same type), if any."""
    for r in reversed(state.requests_for(emp_id)):
        if r.get("status") in OPEN and ((key and r.get("request_key") == key) or (subject and r.get("subject") == subject)):
            return r
    return None


def open_early_warning_for(emp_id, owner_name):
    """An open system early warning for this employee that is already with the same named owner."""
    for c in reversed(state.cases(employee_id=emp_id)):
        if c["type"] == "EARLY_WARNING" and c["status"] in OPEN and c["owner"]["name"] == owner_name:
            return c
    return None


def open_handoff(emp_id, owner_name):
    """An open employee handoff to the same named owner, if any."""
    for c in reversed(state.cases(employee_id=emp_id)):
        if c["type"] == "EMPLOYEE_HANDOFF" and c["status"] in OPEN and c["owner"]["name"] == owner_name:
            return c
    return None


def raise_request(emp_id, key, subject, description, linked_step=None, actor="employee"):
    spec = config.REQUEST_TYPES[key]
    existing = open_request(emp_id, key, subject)
    if existing:  # never raise the same thing twice; point to the open one
        return {"request": existing, "agent": AGENT_DESK.get(spec["team"], spec["team"]), "duplicate": True,
                "agent_reply": f"You already have this request open ({existing['request_id']}, {existing['status'].replace('_', ' ').lower()}). Nothing new was raised.",
                "agent_reply_ar": f"لديك هذا الطلب مفتوحاً بالفعل ({existing['request_id']}). لم يتم فتح طلب جديد.",
                "policy": _cites([spec["policy"]])}
    owners = {"IT Service Desk": "Kevin Lim", "Learning & Development": "Leila Haddad", "Facilities": "Joseph Dsouza",
              "Government Relations (PRO)": "Yousef Al Hammadi", "Payroll": "Ravi Shankar",
              "Global Mobility": "Emma Clarke", "HR Operations": "Grace Mensah", "Security": "Saeed Al Nuaimi"}
    now = state.now_iso()
    req = {
        "request_id": state.new_id("SR"), "employee_id": emp_id, "category": spec["category"],
        "request_type": spec["request_type"], "linked_event_code": linked_step or "", "subject": subject,
        "description": description, "status": "OPEN", "priority": "MEDIUM", "owner_team": spec["team"],
        "owner_name": owners.get(spec["team"], "Unassigned"), "created_at": now, "last_updated_at": now,
        "resolved_at": "", "sla_days": spec["sla"], "days_open": 0, "raised_via": "companion", "request_key": key,
    }
    state.add_request(req)
    reply, reply_ar = AGENT_REPLY.get(key, ("Request received.", "تم استلام الطلب."))
    state.audit(actor, "request_raised", emp_id, f"{req['request_id']} {spec['request_type']} -> {spec['team']}")
    state.notify(emp_id, f"{AGENT_DESK.get(spec['team'], spec['team'])}: {reply}",
                 f"{AGENT_DESK.get(spec['team'], spec['team'])}: {reply_ar}", "request", req["request_id"])
    return {"request": req, "agent": AGENT_DESK.get(spec["team"], spec["team"]), "agent_reply": reply,
            "agent_reply_ar": reply_ar, "policy": _cites([spec["policy"]])}


def _cites(refs):
    """Rafiq's rule references resolved to citations in the loaded pack (unresolvable ones dropped)."""
    from .policies import library
    out = []
    for r in refs or []:
        c = library.resolve(r)
        if c and c not in out:
            out.append(c)
    return out


def _case(emp_id, ctype, title, summary, owner, signals, shared_items, policy, linked_request=None, actor="companion"):
    emp = _emp(emp_id)
    case = {
        "case_id": state.new_id("CASE"), "employee_id": emp_id,
        "employee_name": f"{emp['first_name']} {emp['last_name']}", "journey_type": emp["journey_type"],
        "type": ctype, "title": title, "summary": summary, "owner": owner,
        "hrbp": {"id": emp["hrbp_id"], "name": emp["hrbp_name"]}, "status": "OPEN",
        "created_at": state.now_iso(), "signals": signals, "shared_items": shared_items,
        "policy": _cites(policy), "linked_request": linked_request, "notes": [],
        "next_update_due": (config.AS_OF + dt.timedelta(days=1)).isoformat(),
    }
    state.add_case(case)
    state.audit(actor, "case_opened", emp_id, f"{case['case_id']} {ctype} -> {owner['name']} ({owner['role']})")
    return case


def _clean_signal(s):
    return {k: s.get(k) for k in ("level", "type", "step", "step_label", "message", "request_id", "owner_team")}


def _root_first(ev, signals):
    """Owner-facing signals told from the root cause (DEF-045): a late step that is only late because it waits
    on another late step says so, and 'holding up' chains start at the root."""
    steps = {s["code"]: s for s in ev["steps"]}
    out = []
    for sig in signals:
        sig = dict(sig)
        st = steps.get(sig.get("step"))
        root = (st or {}).get("blocked_by")
        if root:
            lbl = sig.get("step_label") or st["label"]
            if sig["type"] == "BLOCKING":
                sig["message"] = sig["message"].replace(f"{lbl} is holding up",
                                                        f"{root['label']} is holding up {lbl}, which is holding up", 1)
            elif sig["type"] in ("STEP_STALLED", "STEP_AT_RISK") and "waiting on" not in sig["message"]:
                sig["message"] = f"{sig['message']}, waiting on {root['label']}"
            sig["blocked_by"] = root["code"]
        out.append(sig)
    # roots first, dependants after, original order otherwise
    return sorted(out, key=lambda x: 1 if x.get("blocked_by") else 0)


def open_early_warning(emp_id, ev, ops_signals):
    """System-raised early warning from operational data only (no sentiment)."""
    ops_signals = _root_first(ev, ops_signals)
    first = ops_signals[0]
    if first.get("escalation"):
        owner = first["escalation"]
    else:
        owner = escalation_owner(TEAM_ESCALATION.get(first.get("owner_team"), "HR Business Partner"), _emp(emp_id))
    title = f"Early warning: {first.get('step_label') or first['message']}"
    summary = (f"{ev['stage_label']}, day {ev['journey_day']}. " +
               " ".join(s["message"] + "." for s in ops_signals[:4]))
    policy = sorted({p for s in ops_signals for p in s.get("policy", [])})[:4]
    case = _case(emp_id, "EARLY_WARNING", title, summary, owner, [_clean_signal(s) for s in ops_signals],
                 ["Journey step status", "Service request status"], policy, actor="friction-monitor")
    state.notify(emp_id,
                 f"Heads-up: we've flagged '{first.get('step_label') or 'a delay'}' to {owner['name']} ({owner['role']}). "
                 "Only step and request status were shared, not your feedback or conversations.",
                 f"تنبيه: أبلغنا {owner['name']} ({owner['role']}) بالتأخير. تمت مشاركة حالة الخطوات والطلبات فقط، وليس ملاحظاتك أو محادثاتك.",
                 "escalation", case["case_id"])
    return case


def escalate(emp_id, ev, step_code=None, include_pulse=False, employee_note="", actor="employee", preview=False):
    """Employee-confirmed escalation to the named owner of a step (and HRBP cc).
    preview=True returns exactly what the owner would receive, without opening a case or changing anything."""
    emp = _emp(emp_id)
    step = next((s for s in ev["steps"] if s["code"] == step_code), None) if step_code else None
    rel = [s for s in ev["signals"] if (step_code is None or s.get("step") == step_code or s["type"] == "COMPOUND")]
    ops = [s for s in rel if not s.get("sensitive")]
    shared = ["Journey step status", "Service request status"]
    if employee_note:
        shared.append("Employee's note")
    pulse_lines = []
    if include_pulse:
        pulse_lines = [f"Check-in {p['submitted_at'][:10]}: score {p['score']}/5 — \"{p['comment']}\""
                       for p in usable_pulse(emp_id)][-2:]
        if pulse_lines:
            shared.append("Pulse feedback you chose to share")
    target = step["escalation"] if step else escalation_owner("HR Business Partner", emp)
    existing = open_handoff(emp_id, target["name"])
    if existing and not preview:  # one open handoff per owner; show the case that's already with them
        return {**existing, "duplicate": True}
    late = [x for x in ev["steps"] if x["status"] in ("STALLED", "AT_RISK")]
    if target.get("role") == "HR Business Partner" and (step is None or len(late) > 1):
        # The HRBP pulls everything together, so the case carries every off-track item, not just one step
        owner = target
        ops = [s for s in ev["signals"] if not s.get("sensitive")]
        if len(late) > 1:
            title = "Several items off track: " + ", ".join(x["label"] for x in late[:3])
            policy = list(dict.fromkeys(p for x in late[:3] for p in x["policy"][:2]))[:4]
        else:
            title = "Employee asked for help: several items off track"
            policy = ["POL-SRV-001 §3.2", "POL-PRV-001 §5.2"]
    else:
        owner = step["escalation"]
        title = f"{step['label']} — {step['status'].replace('_', ' ').lower()}"
        policy = step["policy"]
    linked = next((q for q in ev["requests"] if q.get("linked_event_code") == step_code and
                   q["status"] not in ("RESOLVED", "CLOSED")), None) if step_code else None
    if linked and not preview:
        _set_priority(linked["request_id"], "HIGH")
    summary = (f"{emp['first_name']} {emp['last_name']} — {emp['role_title']}, {emp['location']}. "
               f"{ev['stage_label']}, day {ev['journey_day']}. " +
               " ".join(s["message"] + "." for s in ops[:4]))
    if linked:
        verb = "will be raised" if preview else "raised"
        if linked["request_id"] in summary:   # already described by its signal: just say what changes
            summary += f" {linked['request_id']} (owner {linked['owner_name']}) {verb} to HIGH priority."
        else:
            summary += (f" Linked request {linked['request_id']} ({linked['status']}, open {linked.get('days_open')} days, "
                        f"owner {linked['owner_name']}) {verb} to HIGH priority.")
    if employee_note:
        note = employee_note.strip()
        summary += f" Employee's note: \"{note}\"" + ("" if note[-1:] in ".!?؟" else ".")
    if pulse_lines:
        summary += " Shared with consent: " + " | ".join(pulse_lines)
    warning = open_early_warning_for(emp_id, owner["name"])
    if preview:
        return {"owner": owner, "hrbp": emp["hrbp_name"], "title": title, "summary": summary,
                "shared_items": shared, "policy": _cites(policy), "existing_case": existing["case_id"] if existing else None,
                "joins_case": warning["case_id"] if warning else None,
                "not_shared": ["Your conversations with Rafiq"] + ([] if include_pulse else ["Your check-in (pulse) answers"]),
                "next_update_due": (config.AS_OF + dt.timedelta(days=1)).isoformat()}
    if warning:
        # One case per problem (DEF-014): the employee's handoff joins the early warning already with this owner
        case = warning
        case.update({"type": "EMPLOYEE_HANDOFF", "title": title, "summary": summary,
                     "signals": [_clean_signal(s) for s in ops], "shared_items": shared, "policy": _cites(policy),
                     "linked_request": linked["request_id"] if linked else case.get("linked_request"),
                     "status": "OPEN", "joined_early_warning": True,
                     "next_update_due": (config.AS_OF + dt.timedelta(days=1)).isoformat()})
        case.setdefault("notes", []).append({"at": state.now_iso(), "by": "system", "by_name": "Rafiq (system)",
                                             "text": "The employee asked for help through Rafiq; this early warning is now their handoff."})
        state.save_case(case)
        state.audit(actor, "case_joined", emp_id, f"{case['case_id']} early warning -> employee handoff ({owner['name']})")
    else:
        case = _case(emp_id, "EMPLOYEE_HANDOFF", title, summary, owner, [_clean_signal(s) for s in ops],
                     shared, policy, linked["request_id"] if linked else None, actor=actor)
    state.notify(emp_id, f"Handed to {owner['name']} ({owner['role']}). Case {case['case_id']}. "
                         f"You'll hear back by {case['next_update_due']}. Your HRBP {emp['hrbp_name']} is copied.",
                 f"تم تحويل طلبك إلى {owner['name']} ({owner['role']}). رقم الحالة {case['case_id']}. "
                 f"ستتلقى تحديثاً بحلول {case['next_update_due']}. تم إشعار شريك الموارد البشرية {emp['hrbp_name']}.",
                 "escalation", case["case_id"])
    return case


def ask_human(emp_id, question, actor="employee"):
    """Policy question the companion could not answer with confidence."""
    r = raise_request(emp_id, "HR_QUERY", "Question the companion could not answer",
                      f"Employee asked: \"{question}\". No policy section covers this; please reply directly.",
                      actor=actor)
    emp = _emp(emp_id)
    owner = {"role": "HR Operations", "name": r["request"]["owner_name"], "contact": "hr.ops@example.test"}
    case = _case(emp_id, "POLICY_QUESTION", "Unanswered policy question",
                 f"Question: \"{question}\". The companion found no policy covering it and did not guess.",
                 owner, [], ["Your question"], [], r["request"]["request_id"], actor=actor)
    return {"case": case, **r}


def _set_priority(request_id, priority):
    state.set_priority(request_id, priority)


def update_case(case_id, status=None, note=None, actor="hrbp", actor_name=None):
    c = state.get_case(case_id)
    if not c:
        return None
    if status:
        c["status"] = status
    if note:
        c["notes"].append({"at": state.now_iso(), "by": actor, "by_name": actor_name or actor, "text": note})
    state.save_case(c)
    state.audit(actor, "case_updated", c["employee_id"], f"{case_id} status={status} note={bool(note)}")
    if status in ("ACKNOWLEDGED", "RESOLVED"):
        word = "acknowledged" if status == "ACKNOWLEDGED" else "resolved"
        word_ar = "استلم" if status == "ACKNOWLEDGED" else "أغلق"
        state.notify(c["employee_id"], f"{c['owner']['name']} {word} case {case_id}." + (f" Note: {note}" if note else ""),
                     f"{word_ar} {c['owner']['name']} الحالة {case_id}.", "case", case_id)
    return c
