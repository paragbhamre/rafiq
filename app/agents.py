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


def raise_request(emp_id, key, subject, description, linked_step=None, actor="employee"):
    spec = config.REQUEST_TYPES[key]
    owners = {"IT Service Desk": "Kevin Lim", "Learning & Development": "Leila Haddad", "Facilities": "Joseph Dsouza",
              "Government Relations (PRO)": "Yousef Al Hammadi", "Payroll": "Ravi Shankar",
              "Global Mobility": "Emma Clarke", "HR Operations": "Grace Mensah", "Security": "Saeed Al Nuaimi"}
    now = state.now_iso()
    req = {
        "request_id": state.new_id("SR"), "employee_id": emp_id, "category": spec["category"],
        "request_type": spec["request_type"], "linked_event_code": linked_step or "", "subject": subject,
        "description": description, "status": "OPEN", "priority": "MEDIUM", "owner_team": spec["team"],
        "owner_name": owners.get(spec["team"], "Unassigned"), "created_at": now, "last_updated_at": now,
        "resolved_at": "", "sla_days": spec["sla"], "days_open": 0, "raised_via": "companion",
    }
    state.add_request(req)
    reply, reply_ar = AGENT_REPLY.get(key, ("Request received.", "تم استلام الطلب."))
    state.audit(actor, "request_raised", emp_id, f"{req['request_id']} {spec['request_type']} -> {spec['team']}")
    state.notify(emp_id, f"{AGENT_DESK.get(spec['team'], spec['team'])}: {reply}",
                 f"{AGENT_DESK.get(spec['team'], spec['team'])}: {reply_ar}", "request", req["request_id"])
    return {"request": req, "agent": AGENT_DESK.get(spec["team"], spec["team"]), "agent_reply": reply,
            "agent_reply_ar": reply_ar, "policy": spec["policy"]}


def _case(emp_id, ctype, title, summary, owner, signals, shared_items, policy, linked_request=None, actor="companion"):
    emp = _emp(emp_id)
    case = {
        "case_id": state.new_id("CASE"), "employee_id": emp_id,
        "employee_name": f"{emp['first_name']} {emp['last_name']}", "journey_type": emp["journey_type"],
        "type": ctype, "title": title, "summary": summary, "owner": owner,
        "hrbp": {"id": emp["hrbp_id"], "name": emp["hrbp_name"]}, "status": "OPEN",
        "created_at": state.now_iso(), "signals": signals, "shared_items": shared_items,
        "policy": policy, "linked_request": linked_request, "notes": [],
        "next_update_due": (config.AS_OF + dt.timedelta(days=1)).isoformat(),
    }
    state.add_case(case)
    state.audit(actor, "case_opened", emp_id, f"{case['case_id']} {ctype} -> {owner['name']} ({owner['role']})")
    return case


def _clean_signal(s):
    return {k: s.get(k) for k in ("level", "type", "step", "step_label", "message", "request_id", "owner_team")}


def open_early_warning(emp_id, ev, ops_signals):
    """System-raised early warning from operational data only (no sentiment)."""
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


def escalate(emp_id, ev, step_code=None, include_pulse=False, employee_note="", actor="employee"):
    """Employee-confirmed escalation to the named owner of a step (and HRBP cc)."""
    emp = _emp(emp_id)
    step = next((s for s in ev["steps"] if s["code"] == step_code), None) if step_code else None
    rel = [s for s in ev["signals"] if (step_code is None or s.get("step") == step_code or s["type"] == "COMPOUND")]
    ops = [s for s in rel if not s.get("sensitive")]
    shared = ["Journey step status", "Service request status"]
    if employee_note:
        shared.append("Your note")
    pulse_lines = []
    if include_pulse:
        pulse_lines = [f"Check-in {p['submitted_at'][:10]}: score {p['score']}/5 — \"{p['comment']}\""
                       for p in usable_pulse(emp_id)][-2:]
        if pulse_lines:
            shared.append("Pulse feedback you chose to share")
    if step:
        owner = step["escalation"]
        title = f"{step['label']} — {step['status'].replace('_', ' ').lower()}"
        policy = step["policy"]
    else:
        owner = escalation_owner("HR Business Partner", emp)
        title = "Employee asked for help: several items off track"
        policy = ["POL-SRV-001 §3.2", "POL-PRV-001 §5.2"]
    linked = next((q for q in ev["requests"] if q.get("linked_event_code") == step_code and
                   q["status"] not in ("RESOLVED", "CLOSED")), None) if step_code else None
    if linked:
        _set_priority(linked["request_id"], "HIGH")
    summary = (f"{emp['first_name']} {emp['last_name']} — {emp['role_title']}, {emp['location']}. "
               f"{ev['stage_label']}, day {ev['journey_day']}. " +
               " ".join(s["message"] + "." for s in ops[:4]))
    if linked:
        summary += f" Linked request {linked['request_id']} ({linked['status']}, open {linked.get('days_open')} days, owner {linked['owner_name']}) raised to HIGH priority."
    if employee_note:
        summary += f" Employee's note: \"{employee_note}\"."
    if pulse_lines:
        summary += " Shared with consent: " + " | ".join(pulse_lines)
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


def update_case(case_id, status=None, note=None, actor="hrbp"):
    c = state.get_case(case_id)
    if not c:
        return None
    if status:
        c["status"] = status
    if note:
        c["notes"].append({"at": state.now_iso(), "by": actor, "text": note})
    state.save_case(c)
    state.audit(actor, "case_updated", c["employee_id"], f"{case_id} status={status} note={bool(note)}")
    if status in ("ACKNOWLEDGED", "RESOLVED"):
        word = "acknowledged" if status == "ACKNOWLEDGED" else "resolved"
        word_ar = "استلم" if status == "ACKNOWLEDGED" else "أغلق"
        state.notify(c["employee_id"], f"{c['owner']['name']} {word} case {case_id}." + (f" Note: {note}" if note else ""),
                     f"{word_ar} {c['owner']['name']} الحالة {case_id}.", "case", case_id)
    return c
