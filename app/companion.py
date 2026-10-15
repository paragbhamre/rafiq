"""The employee-side companion.

Pipeline for every message:
  1. Guardrails   - refuse requests for other people's data, monitoring, rule-bypass, approvals.
  2. Router       - deterministic intent + journey-step matching against the employee's live journey.
  3. Composer     - builds a grounded draft: facts from the journey engine, cited policy sections,
                    and proposed actions (each with a named owner). Nothing is executed here.
  4. Writer (opt) - if an LLM is configured, it rewrites the draft in natural language in the
                    employee's language. It may only cite sections it was given; citations are
                    validated afterwards. Any LLM failure falls back to the deterministic draft.
Routing decisions never depend on the LLM, so behaviour on test scenarios is reproducible.
"""
import datetime as dt
import re

from . import config, llm
from .data import pack, state, usable_pulse
from .journey import evaluate, step_def
from .policies import has_arabic, library, tokenize

# --------------------------------------------------------------------------
# Intent lexicon
# --------------------------------------------------------------------------
TOPICS = [
    # (topic, regex, candidate step codes)
    ("laptop", r"laptop|computer|\bphone\b|\bkit\b|equipment|device|حاسوب|لابتوب|جهاز", ["IT_KIT_ISSUED"]),
    ("access", r"log ?in|access|account|\bemail\b|system|rostering|password|portal|can.?t get into|صلاحي|دخول", ["SYSTEM_ACCESS_GRANTED", "ACCESS_TRANSFERRED"]),
    ("allowance", r"allowance|\bpaid\b|payment|money|reimburse|بدل|مبلغ", ["RELOCATION_ALLOWANCE_PAID"]),
    ("visa", r"visa|medical|emirates id|entry permit|residency|biometric|تأشيرة|التأشيرة|فحص|الطبي|الهوية", ["VISA_APPLICATION_SUBMITTED", "MEDICAL_COMPLETED", "VISA_ISSUED", "EMIRATES_ID_APPLIED"]),
    ("permit", r"work permit|employment pass|\bpermit\b|تصريح", ["WORK_PERMIT_ISSUED"]),
    ("accommodation", r"accommodation|housing|\bflat\b|apartment|\baddress\b|hotel|where (will|do|am|shall) i (stay|staying|live|living|sleep)|سكن|السكن", ["ACCOMMODATION_ASSIGNED", "HOUSING_ARRANGED"]),
    ("ticket", r"ticket|\bflight\b|\bfly\b|baggage|luggage|تذكرة", ["JOINING_TICKET_ISSUED"]),
    ("lost", r"\blost\b|where to go|nobody (told|has)|no one (told|has)|who (do i|to) ask|don.?t know who|buddy|confus|overwhelm|ضائع|لا أعرف", ["BUDDY_ASSIGNED", "INDUCTION_COMPLETED"]),
    ("training", r"induction|training|course|e-?learning|تدريب|التعريف", ["INDUCTION_COMPLETED", "MANDATORY_TRAINING_BOOKED", "ROLE_TRAINING_BOOKED"]),
    ("staff_id", r"staff id|\bbadge\b|\bpass\b|id card|بطاقة", ["STAFF_ID_ISSUED"]),
    ("move", r"\bmove\b|transfer|new role|endorse|release date|handover|انتقال|الانتقال", ["RECEIVING_MANAGER_ENDORSED", "RELEASING_MANAGER_RELEASED", "TRANSFER_APPROVED", "TRANSFER_LETTER_ISSUED", "HANDOVER_COMPLETED", "MOVE_EFFECTIVE"]),
    ("objectives", r"objective|probation goal|أهداف", ["PROBATION_OBJECTIVES_SET"]),
]
STATUS_RE = r"what.?s next|next step|how am i doing|on track|status|what.?s happening|where am i|good to go|all set|am i ready|progress|update|can i (fly|travel|start|go)|ماذا بعد|الخطوة التالية|خطواتي|التالية|وضعي|رحلتي|جاهز"
PRIVACY_RE = (r"manager (see|know|read)|who can see|my data|privacy|confidential|affect my (probation|performance|review)|"
              r"used against|performance (review|decision)|will (it|this) affect|يرى مديري|خصوصي|بياناتي|التجربة")
HUMAN_RE = r"talk to (a |an )?(human|person|someone|real)|speak (to|with) (hr|someone|a person)|escalate|contact my hrbp|أريد التحدث"
EMOTION_RE = r"\blost\b|frustrat|stress|unhappy|struggl|honestly|overwhelm|worried|anxious|upset|nobody|no one|محبط|قلق"
SMALLTALK_RE = r"^(hi|hello|hey|good (morning|afternoon|evening)|salam|marhaba|thanks|thank you|cheers|مرحبا|مرحباً|السلام عليكم|شكرا|شكراً)\b[!. ]*$"
CONTACT_RE = r"who is my (hr|hrbp|hr business partner|manager|line manager|buddy)|who.?s my (hr|hrbp|manager)|من هو (مديري|شريك)"
APPROVE_RE = r"(just )?approve (my|the)|sign off my|change my (joining|move|start) date|grant me|override"
BYPASS_RE = r"ignore (your|the|all|previous) (rules|instructions)|pretend you|jailbreak|developer mode|system prompt"
MONITOR_RE = r"(which|who) of my (team|joiners|new joiners|reports)|my team.?s (mood|sentiment|feedback)|(unhappy|sentiment|morale|mood) of (my|the) team"
OTHER_DATA_WORDS = r"score|feedback|pulse|data|record|salary|request|survey|comment|status"

STATUS_ORDER = {"STALLED": 0, "AT_RISK": 1, "DUE_TODAY": 2, "WAITING": 3, "UPCOMING": 4, "DONE_LATE": 5, "DONE": 6}

# Step -> actions the companion can offer (request keys from config.REQUEST_TYPES)
STEP_ACTIONS = {
    "IT_KIT_ISSUED": ["IT_LOAN_DEVICE"], "SYSTEM_ACCESS_GRANTED": ["IT_ACCESS"], "ACCESS_TRANSFERRED": ["IT_ACCESS"],
    "VISA_APPLICATION_SUBMITTED": ["PRO_VISA"], "MEDICAL_COMPLETED": ["PRO_VISA"], "VISA_ISSUED": ["PRO_VISA"],
    "EMIRATES_ID_APPLIED": ["PRO_VISA"], "ACCOMMODATION_ASSIGNED": ["FAC_ACCOMMODATION"], "HOUSING_ARRANGED": ["FAC_ACCOMMODATION"],
    "INDUCTION_COMPLETED": ["LD_REBOOK_INDUCTION"], "MANDATORY_TRAINING_BOOKED": ["LD_BOOK_TRAINING"],
    "ROLE_TRAINING_BOOKED": ["LD_BOOK_TRAINING"], "RELOCATION_ALLOWANCE_PAID": ["PAYROLL_ALLOWANCE"],
    "WORK_PERMIT_ISSUED": ["MOBILITY_QUERY"], "STAFF_ID_ISSUED": ["SEC_ID"], "JOINING_TICKET_ISSUED": ["HR_QUERY"],
}

# Extra reassurance that matters when a step is late
STEP_REASSURE = {
    "IT_KIT_ISSUED": ["POL-IT-001 §5.1", "POL-LRN-001 §5.1"],
    "SYSTEM_ACCESS_GRANTED": ["POL-IT-001 §5.2", "POL-LRN-001 §5.1"],
    "ACCESS_TRANSFERRED": ["POL-IT-001 §5.2", "POL-IT-001 §4.3"],
    "MEDICAL_COMPLETED": ["POL-PRO-001 §6.2", "POL-PRO-001 §6.3"],
    "VISA_ISSUED": ["POL-PRO-001 §6.2", "POL-PRO-001 §6.3"],
    "ACCOMMODATION_ASSIGNED": ["POL-ACC-001 §2.2", "POL-ACC-001 §4.3"],
    "HOUSING_ARRANGED": ["POL-ACC-001 §3.3", "POL-MOB-002 §5.1"],
    "WORK_PERMIT_ISSUED": ["POL-MOB-002 §3.2", "POL-MOB-002 §5.2"],
    "RELOCATION_ALLOWANCE_PAID": ["POL-MOB-002 §4.1", "POL-SRV-001 §4.2"],
    "BUDDY_ASSIGNED": ["POL-ONB-001 §3.4"],
    "INDUCTION_COMPLETED": ["POL-LRN-001 §1.2"],
    "RECEIVING_MANAGER_ENDORSED": ["POL-MOB-001 §4.1", "POL-MOB-001 §4.3"],
    "RELEASING_MANAGER_RELEASED": ["POL-MOB-001 §4.1", "POL-MOB-001 §4.2"],
    "TRANSFER_APPROVED": ["POL-MOB-001 §4.1"],
    "PROBATION_OBJECTIVES_SET": ["POL-ONB-002 §2.2"],
}

GENERIC_WORDS = set(tokenize("""please tell help know want need question ask still yet when where why how much many
long time day days week weeks month today tomorrow next going start started starting meant supposed due
honestly really just also actually get got thing things anything something everything okay ok hi hello
thank thanks dear sir madam company pay cover allowed bring take make give new old first"""))


TEAM_AR = {
    "IT Service Desk": "مكتب خدمات تقنية المعلومات", "Line Management": "المدير المباشر",
    "HR Business Partnering": "شريك الموارد البشرية", "HR Operations": "عمليات الموارد البشرية",
    "Government Relations (PRO)": "العلاقات الحكومية", "Facilities": "إدارة المرافق", "Security": "الأمن",
    "Learning & Development": "التعلم والتطوير", "Global Mobility": "التنقل العالمي", "Payroll": "الرواتب",
    "Talent Acquisition": "استقطاب المواهب",
    "Facilities / Global Mobility": "إدارة المرافق / التنقل العالمي",
}


def _team(name, ar):
    """Arabic team name; joint teams ("Facilities / Global Mobility") are translated part by part."""
    if not ar:
        return name
    if name in TEAM_AR:
        return TEAM_AR[name]
    return " / ".join(TEAM_AR.get(part.strip(), part.strip()) for part in name.split("/"))


def _fmt_date(iso, ar=False):
    d = dt.date.fromisoformat(iso[:10])
    if ar:
        return d.strftime("%d/%m/%Y")
    return d.strftime("%a %d %b").replace(" 0", " ")


class Draft:
    def __init__(self, lang):
        self.lang = lang
        self.lines = []
        self.cites = []
        self.actions = []
        self.intent = None
        self.refused = False
        self.unsure = False
        self.steps = []
        self.shown = set()
        self._msg = ""

    def t(self, en, ar):
        return ar if self.lang == "ar" else en

    def say(self, en, ar=None):
        self.lines.append(self.t(en, ar or en))

    def cite(self, *cites):
        # Citations in code name rules by their synthetic-pack reference; library.lookup maps them to the loaded pack
        for c in cites:
            sec = library.lookup(c)
            if sec and sec["cite"] not in self.cites:
                self.cites.append(sec["cite"])

    def policy_line(self, cite, prefix_en="", prefix_ar=""):
        sec = library.lookup(cite)
        if not sec or sec["cite"] in self.shown:
            return False
        cite = sec["cite"]
        self.shown.add(cite)
        self.cite(cite)
        note = self.t("", " (نص السياسة بالإنجليزية)")
        self.say(f"{prefix_en}{sec['text']} [{cite}]", f"{prefix_ar}{sec['text']} [{cite}]{note}")
        return True

    def action(self, a):
        if any(x["id"] == a["id"] for x in self.actions):
            return
        if a["type"] == "ESCALATE":
            same = next((x for x in self.actions if x["type"] == "ESCALATE"
                         and x["owner"].get("name") == a["owner"].get("name")), None)
            if same:
                same["primary"] = same.get("primary") or a.get("primary")
                same["can_include_pulse"] = same.get("can_include_pulse") or a.get("can_include_pulse")
                return
        self.actions.append(a)


# --------------------------------------------------------------------------
# Actions (proposed only; executed by the employee via /api/actions)
# --------------------------------------------------------------------------
def _request_action(draft, key, step_code, emp):
    spec = config.REQUEST_TYPES[key]
    draft.action({"id": f"req:{key}:{step_code or ''}", "type": "RAISE_REQUEST", "request_key": key,
                  "step": step_code, "label": draft.t(spec["label"], spec["label_ar"]),
                  "owner": {"role": spec["team"], "name": spec["team"]}, "policy": spec["policy"]})


def _escalate_action(draft, step, primary=True):
    owner = step["escalation"]
    draft.action({"id": f"esc:{step['code']}", "type": "ESCALATE", "step": step["code"], "primary": primary,
                  "label": draft.t(f"Escalate to {owner['name']} ({owner['role']})",
                                   f"التصعيد إلى {owner['name']} ({owner['role']})"),
                  "owner": owner, "can_include_pulse": False})


def _hrbp_action(draft, emp, pulse_available):
    draft.action({"id": "esc:HRBP", "type": "ESCALATE", "step": None, "primary": False,
                  "label": draft.t(f"Ask my HR Business Partner ({emp['hrbp_name']}) to help",
                                   f"طلب المساعدة من شريك الموارد البشرية ({emp['hrbp_name']})"),
                  "owner": {"role": "HR Business Partner", "name": emp["hrbp_name"]},
                  "can_include_pulse": pulse_available})


# --------------------------------------------------------------------------
# Composers
# --------------------------------------------------------------------------
def _request_for(ev, code):
    return next((q for q in ev["requests"] if q.get("linked_event_code") == code
                 and q["status"] not in ("RESOLVED", "CLOSED")), None)


def _describe_step(draft, ev, step, emp, detail=True):
    ar = draft.lang == "ar"
    label = step["label_ar"] if ar else step["label"]
    due = _fmt_date(step["target_date"], ar)
    st = step["status"]
    if st in ("DONE", "DONE_LATE"):
        draft.say(f"✅ **{label}** — done on {_fmt_date(step['completed_at'], ar)}.",
                  f"✅ **{label}** — اكتمل بتاريخ {_fmt_date(step['completed_at'], ar)}.")
    elif st == "STALLED":
        draft.say(f"🔴 **{label}** — target {due}, **{step['days_late']} days late**. Owner: {step['owner_team']}.",
                  f"🔴 **{label}** كان مستحقاً بتاريخ {due} وهو **متأخر {step['days_late']} أيام**. الجهة المسؤولة: {_team(step['owner_team'], True)}.")
    elif st == "AT_RISK":
        draft.say(f"🟠 **{label}** — target {due}, {step['days_late']} day{'s' if step['days_late'] != 1 else ''} late. Owner: {step['owner_team']}.",
                  f"🟠 **{label}** كان مستحقاً بتاريخ {due} ومتأخر {step['days_late']} يوم. الجهة المسؤولة: {_team(step['owner_team'], True)}.")
    elif st == "DUE_TODAY":
        draft.say(f"🟡 **{label}** is due today. Owner: {step['owner_team']}.",
                  f"🟡 **{label}** مستحق اليوم. الجهة المسؤولة: {_team(step['owner_team'], True)}.")
    elif st == "WAITING":
        waits = ", ".join((step_def(ev["journey_type"], w) or {}).get("label_ar" if ar else "label", w) for w in step["waiting_on"])
        draft.say(f"⏳ **{label}** (target {due}) is waiting on: {waits}.",
                  f"⏳ **{label}** (الموعد {due}) بانتظار: {waits}.")
    else:
        draft.say(f"🗓️ **{label}** — on track, target {due}. Owner: {step['owner_team']}.",
                  f"🗓️ **{label}** — يسير وفق الخطة، الموعد المستهدف {due}. الجهة المسؤولة: {_team(step['owner_team'], True)}.")
    if not detail:
        return
    req = _request_for(ev, step["code"])
    if req:
        sla = float(req["sla_days"])
        breach = req.get("sla_state") != "OK"
        draft.say(
            f"Request **{req['request_id']}** is with {req['owner_name']} ({req['owner_team']}), status {req['status'].replace('_', ' ').lower()}, "
            f"open {req['days_open']} days against a {sla:g}-day service level" + (" — **over the service level**." if breach else "."),
            f"الطلب **{req['request_id']}** لدى {req['owner_name']} ({req['owner_team']})، الحالة {req['status']}، "
            f"مفتوح منذ {req['days_open']} أيام مقابل مستوى خدمة {sla:g} يوم" + (" — **تجاوز مستوى الخدمة**." if breach else "."))
        if req["status"] == "PENDING_INFO":
            draft.say(f"They are waiting for something from you: _{req['description']}_",
                      f"الفريق بانتظار معلومات منك: _{req['description']}_")
            draft.cite("POL-SRV-001 §4.1", "POL-SRV-001 §4.2")
        if breach:
            draft.cite("POL-SRV-001 §3.2")
    for s in ev["signals"]:
        if s["type"] == "BLOCKING" and s["step"] == step["code"]:
            draft.say(f"⚠️ {s['message_ar'] if ar else s['message']}.")
    if step["status"] in ("STALLED", "AT_RISK"):
        held = [x for x in ev["steps"] if step["code"] in x["waiting_on"] and x["status"] not in ("DONE", "DONE_LATE")]
        if held:
            names = ", ".join(x["label_ar" if ar else "label"].lower() if not ar else x["label_ar"] for x in held[:3])
            draft.say(f"This is also holding up: {names}.", f"هذا يؤخر أيضاً: {names}.")


def _step_policy(draft, step, max_lines=2):
    lines = 0
    late = step["status"] in ("STALLED", "AT_RISK", "DUE_TODAY")
    cites = (STEP_REASSURE.get(step["code"], []) + step["policy"]) if late else step["policy"]
    for c in dict.fromkeys(cites):
        if lines >= max_lines:
            draft.cite(c)
            continue
        if draft.policy_line(c, "• ", "• "):
            lines += 1


def _offer_step_actions(draft, ev, step, emp):
    late = step["status"] in ("STALLED", "AT_RISK", "DUE_TODAY")
    req = _request_for(ev, step["code"])
    breach = bool(req and req.get("sla_state") != "OK")
    team_open = any(q["status"] not in ("RESOLVED", "CLOSED") and q["owner_team"] == step["owner_team"] for q in ev["requests"])
    for key in STEP_ACTIONS.get(step["code"], []):
        if key not in ("IT_LOAN_DEVICE", "LD_REBOOK_INDUCTION") and team_open:
            continue
        if key in ("IT_LOAN_DEVICE",) and late:
            _request_action(draft, key, step["code"], emp)
        elif key == "LD_REBOOK_INDUCTION" and late:
            _request_action(draft, key, step["code"], emp)
        elif late and not req:
            _request_action(draft, key, step["code"], emp)
    if step["status"] in ("STALLED", "AT_RISK") or breach:
        red = step["status"] == "STALLED" or breach or any(
            s["type"] == "BLOCKING" and s["step"] == step["code"] for s in ev["signals"])
        _escalate_action(draft, step, primary=red)


def compose_topic(draft, ev, emp, topic, codes):
    steps = {s["code"]: s for s in ev["steps"]}
    candidates = [steps[c] for c in codes if c in steps]
    if topic == "allowance" and not candidates:
        _entitlement(draft, ev, emp)
        _maybe_compound(draft, ev, emp)
        return
    if not candidates:
        return _not_applicable(draft, ev, emp, topic)
    candidates.sort(key=lambda s: (STATUS_ORDER.get(s["status"], 9), s["target_day"]))
    problem = [s for s in candidates if s["status"] in ("STALLED", "AT_RISK", "DUE_TODAY")]
    focus = problem[:2] or candidates[:1]
    if topic == "allowance" or (topic == "accommodation" and re.search(r"allowance|بدل", draft._msg)):
        _entitlement(draft, ev, emp)
        if topic == "accommodation" or "RELOCATION_ALLOWANCE_PAID" not in steps or re.search(r"transport|settling|housing|سكن|مواصلات", draft._msg):
            return
        focus = [steps["RELOCATION_ALLOWANCE_PAID"]]
    if topic == "lost":
        draft.say("I'm sorry it's felt like that — let's sort out who you can turn to right now.",
                  "يؤسفني أنك شعرت بذلك — دعنا نحدد الآن من يمكنك اللجوء إليه.")
    elif not problem and topic != "allowance":
        draft.say("Good news — this part of your journey is on track.", "أخبار جيدة — هذا الجزء من رحلتك يسير وفق الخطة.")
    for s in focus:
        draft.steps.append(s["code"])
        _describe_step(draft, ev, s, emp)
        _step_policy(draft, s)
        _offer_step_actions(draft, ev, s, emp)
    if topic == "lost":
        draft.say(f"Your HR Business Partner is **{emp['hrbp_name']}** and your manager is **{emp['manager_name']}**.",
                  f"شريك الموارد البشرية الخاص بك هو **{emp['hrbp_name']}** ومديرك هو **{emp['manager_name']}**.")
    _maybe_compound(draft, ev, emp)
    if not problem:
        _next_steps(draft, ev, limit=2)


def _entitlement(draft, ev, emp):
    msg = draft._msg
    if re.search(r"transport|commute|مواصلات|النقل", msg):
        if not library.same_text("POL-ALW-001 §3.1"):
            draft.say("Here's what the policy says:", "هذا ما تنص عليه السياسة:")
        else:
          draft.say("If you're not on a company transport route, you receive a transport allowance of **AED 1,000 a month**.",
                  "إذا لم تكن على أحد خطوط النقل التابعة للشركة، تحصل على بدل مواصلات قدره **1,000 درهم شهرياً**.")
        draft.policy_line("POL-ALW-001 §3.1", "• ", "• ")
        draft.policy_line("POL-ALW-001 §3.2", "• ", "• ")
        return
    if re.search(r"settling|joining allowance|استقرار", msg):
        settle = "AED 8,000" if emp["family_status"] == "FAMILY" else "AED 5,000"
        if not library.same_text("POL-ALW-001 §1.2"):
            draft.say("Here's what the policy says:", "هذا ما تنص عليه السياسة:")
        else:
          draft.say(f"The settling-in allowance for new joiners from abroad is **{settle}** for you, paid once with your first salary.",
                  f"بدل الاستقرار للموظفين الجدد القادمين من الخارج هو **{settle}** بالنسبة لك، يُصرف مرة واحدة مع أول راتب.")
        for c in ("POL-ALW-001 §1.1", "POL-ALW-001 §1.2", "POL-ALW-001 §1.3"):
            draft.policy_line(c, "• ", "• ")
        return
    if re.search(r"housing|سكن|السكن|rent", msg):
        if emp["accommodation_eligible"] == "true":
            draft.say("You're eligible for company accommodation, so a housing allowance doesn't apply while you're in it.",
                      "أنت مؤهل للسكن الذي توفره الشركة، لذلك لا ينطبق بدل السكن أثناء إقامتك فيه.")
            draft.policy_line("POL-ALW-001 §2.4", "• ", "• ")
            return
        amt = config.HOUSING_ALLOWANCE.get(emp["grade"]) if library.same_text("POL-ALW-001 §2.2") else None
        if amt:
            draft.say(f"For your grade ({emp['grade']}), the housing allowance is **AED {amt:,} a month**, paid with your salary from your joining date.",
                      f"لدرجتك الوظيفية ({emp['grade']})، بدل السكن هو **{amt:,} درهم شهرياً**، ويُصرف مع راتبك اعتباراً من تاريخ التحاقك.")
        elif library.same_text("POL-ALW-001 §2.2"):
            draft.say(f"For grade {emp['grade']}, the housing allowance is the amount stated in your contract.",
                      f"للدرجة {emp['grade']}، بدل السكن هو المبلغ المنصوص عليه في عقدك.")
        else:
            draft.say(f"Here's what the policy says for your grade ({emp['grade']}):", f"هذا ما تنص عليه السياسة لدرجتك ({emp['grade']}):")
        draft.policy_line("POL-ALW-001 §2.2", "• ", "• ")
        draft.policy_line("POL-ALW-001 §2.3", "• ", "• ")
        draft.policy_line("POL-ALW-001 §6.1", "• ", "• ")
        return
    mt = emp.get("move_type")
    if mt in ("LOCATION_INTERNATIONAL", "LOCATION_DOMESTIC") and not library.same_text("POL-ALW-001 §4.1", "POL-ALW-001 §4.2"):
        draft.say("Here's what the policy says about relocation allowances:", "هذا ما تنص عليه السياسة بشأن بدل الانتقال:")
        draft.policy_line("POL-ALW-001 §4.2" if mt == "LOCATION_INTERNATIONAL" else "POL-ALW-001 §4.1", "• ", "• ")
    elif mt == "LOCATION_INTERNATIONAL":
        draft.say("For an international move, your relocation allowance is **one month's basic salary, up to AED 25,000**, paid once.",
                  "في الانتقال الدولي، بدل الانتقال هو **راتب أساسي لشهر واحد بحد أقصى 25,000 درهم** يُصرف مرة واحدة.")
        draft.policy_line("POL-ALW-001 §4.2", "• ", "• ")
    elif mt == "LOCATION_DOMESTIC":
        draft.say("For a move within the UAE, your relocation allowance is **AED 3,000**, paid once.",
                  "في الانتقال داخل الدولة، بدل الانتقال هو **3,000 درهم** يُصرف مرة واحدة.")
        draft.policy_line("POL-ALW-001 §4.1", "• ", "• ")
    elif mt in ("ROLE_CHANGE", "TEAM_CHANGE"):
        draft.say("A relocation allowance isn't payable for a role or team change at the same location.",
                  "لا يُصرف بدل الانتقال عند تغيير الدور أو الفريق في نفس الموقع.")
        draft.policy_line("POL-ALW-001 §4.4", "• ", "• ")
    else:
        settle = "AED 8,000" if emp["family_status"] == "FAMILY" else "AED 5,000"
        if emp["relocating_from_abroad"] == "true" and library.same_text("POL-ALW-001 §1.2"):
            draft.say(f"As a new joiner relocating from abroad, you receive a one-off settling-in allowance of **{settle}** with your first salary.",
                      f"بصفتك موظفاً جديداً قادماً من الخارج، تحصل على بدل استقرار لمرة واحدة قدره **{settle}** مع أول راتب.")
            draft.cite("POL-ALW-001 §1.1", "POL-ALW-001 §1.2", "POL-ALW-001 §1.3")
        for c in ("POL-ALW-001 §2.2", "POL-ALW-001 §3.1"):
            draft.policy_line(c, "• ", "• ")


def _not_applicable(draft, ev, emp, topic):
    if topic == "visa" and emp.get("visa_required") == "false":
        draft.say("Good news: as a UAE national you don't need an employment visa, so there's **no visa medical test** for you.",
                  "خبر سار: بصفتك مواطناً إماراتياً لا تحتاج إلى تأشيرة عمل، لذلك **لا يوجد فحص طبي للتأشيرة** بالنسبة لك.")
        draft.policy_line("POL-PRO-001 §1.2", "• ", "• ")
    elif topic in ("permit", "allowance", "accommodation") and ev["journey_type"] == "MOBILITY":
        mt = emp.get("move_type", "").replace("_", " ").lower()
        draft.say(f"That step isn't part of your move ({mt}).", f"هذه الخطوة ليست جزءاً من انتقالك ({mt}).")
    elif topic == "accommodation":
        draft.say("Company accommodation isn't part of your onboarding plan, based on your offer.",
                  "السكن الذي توفره الشركة ليس جزءاً من خطة التحاقك وفقاً لعرضك الوظيفي.")
        draft.policy_line("POL-ACC-001 §1.3", "• ", "• ")
    else:
        draft.say("That step isn't part of your journey.", "هذه الخطوة ليست جزءاً من رحلتك.")
    _next_steps(draft, ev, limit=3)


def _next_steps(draft, ev, limit=3):
    nxt = [s for s in ev["next_steps"] if s["status"] not in ("DONE", "DONE_LATE") and s["code"] not in draft.steps][:limit]
    if not nxt and draft.steps:
        return
    if not nxt:
        draft.say("All your journey steps are complete. 🎉", "اكتملت جميع خطوات رحلتك. 🎉")
        return
    draft.say("**What's next for you:**", "**خطواتك التالية:**")
    for s in nxt:
        _describe_step(draft, ev, s, None, detail=False)


def _maybe_compound(draft, ev, emp):
    if any(s["type"] == "COMPOUND" for s in ev["signals"]):
        pulse = len(usable_pulse(emp["employee_id"])) > 0
        draft.say("A few things are off track at once. Your HR Business Partner can pull them together — you decide what's shared.",
                  "هناك عدة أمور متأخرة في الوقت نفسه. يمكن لشريك الموارد البشرية متابعتها معاً — وأنت من يقرر ما تتم مشاركته.")
        draft.cite("POL-PRV-001 §5.2")
        _hrbp_action(draft, emp, pulse)


def compose_status(draft, ev, emp, greeting=False):
    ar = draft.lang == "ar"
    stage = ev["stage_label_ar"] if ar else ev["stage_label"]
    day = ev["journey_day"]
    if ev["journey_type"] == "ONBOARDING":
        when = (draft.t(f"{-day} days before your joining date", f"{-day} يوماً قبل تاريخ التحاقك") if day < 0
                else draft.t(f"day {day} since you joined", f"اليوم {day} منذ التحاقك"))
    else:
        eff = ev["move_effective_date"]
        until = (dt.date.fromisoformat(eff) - config.AS_OF).days if eff else None
        when = (draft.t(f"your move is effective {_fmt_date(eff)}" + (" (tomorrow)" if until == 1 else f" ({until} days away)" if until and until > 1 else " (today)" if until == 0 else ""),
                        f"انتقالك يسري بتاريخ {_fmt_date(eff, True)}") if until is not None and until >= 0
                else draft.t(f"day {day - 30} in your new role", f"اليوم {day - 30} في دورك الجديد"))
    p = ev["progress"]
    prefix = draft.t(f"Hi {emp['first_name']}. ", f"مرحباً {emp['first_name']}. ") if greeting else ""
    draft.say(f"{prefix}You're in **{stage}** — {when}. {p['done']} of {p['total']} steps done.",
              f"{prefix}أنت في مرحلة **{stage}** — {when}. اكتملت {p['done']} من أصل {p['total']} خطوة.")
    problems = sorted([s for s in ev["steps"] if s["status"] in ("STALLED", "AT_RISK")],
                      key=lambda s: STATUS_ORDER[s["status"]])
    asked_ready = bool(re.search(r"good to go|all set|ready|can i (fly|travel|start|go)|جاهز", draft._msg))
    if problems:
        blocking = [s for s in ev["signals"] if s["type"] == "BLOCKING"]
        if asked_ready:
            draft.say("**Not yet** — something needs to be resolved first:", "**ليس بعد** — هناك أمر يجب حله أولاً:")
        else:
            draft.say("Not everything is on track:", "ليست كل الأمور تسير وفق الخطة:")
        ordered = sorted(problems, key=lambda s: (0 if any(b["step"] == s["code"] for b in blocking) else 1,
                                                  STATUS_ORDER[s["status"]]))
        for s in ordered[:2]:
            draft.steps.append(s["code"])
            _describe_step(draft, ev, s, emp)
            _step_policy(draft, s, max_lines=2 if s is ordered[0] else 1)
            _offer_step_actions(draft, ev, s, emp)
        if len(problems) > 2:
            draft.say(f"…and {len(problems) - 2} more item(s) — see your journey timeline.",
                      f"…و{len(problems) - 2} عنصر آخر — راجع المخطط الزمني لرحلتك.")
        _maybe_compound(draft, ev, emp)
    else:
        if asked_ready:
            draft.say("**Yes — everything due so far is done.**", "**نعم — كل ما هو مستحق حتى الآن قد اكتمل.**")
        else:
            draft.say("Everything due so far is on track. 👍", "كل ما هو مستحق حتى الآن يسير وفق الخطة. 👍")
    _next_steps(draft, ev, limit=3)


def compose_privacy(draft, ev, emp):
    draft.say("Short answer: **no** — your manager can't see what you tell me, and it can't be used in your probation or performance.",
              "الإجابة المختصرة: **لا** — لا يستطيع مديرك رؤية ما تخبرني به، ولا يمكن استخدامه في تقييم فترة التجربة أو الأداء.")
    for c in ("POL-PRV-001 §5.1", "POL-PRV-001 §6.2", "POL-ONB-002 §4.2"):
        draft.policy_line(c, "• ", "• ")
    draft.say("Your HR Business Partner only sees a summary when you (or a stalled step) trigger a handoff, and you're told what's shared. "
              "You can see everything held about you, and withdraw pulse consent, in **My data**.",
              "لا يرى شريك الموارد البشرية سوى ملخص عند التحويل، ويتم إعلامك بما تمت مشاركته. يمكنك رؤية كل ما هو محفوظ عنك وسحب موافقتك من صفحة **بياناتي**.")
    draft.cite("POL-PRV-001 §5.2", "POL-PRV-001 §4.1", "POL-PRV-001 §3.1")
    draft.action({"id": "nav:mydata", "type": "OPEN_MY_DATA", "label": draft.t("Open My data", "فتح بياناتي")})


def compose_policy(draft, ev, emp, msg):
    q_tokens = [t for t in tokenize(msg) if t not in GENERIC_WORDS]
    vocab = library.idf
    oov = [t for t in q_tokens if t not in vocab and not t.isdigit()]
    hits = library.search(msg, k=4)
    if has_arabic(msg):
        oov = []  # glossary-based for Arabic; rely on score threshold
    top = hits[0] if hits else None
    covered = [t for t in q_tokens if t in vocab]
    weak = (not top) or top["score"] < 4.0 or (oov and len(oov) >= 1) or (q_tokens and len(covered) / len(q_tokens) < 0.5)
    if weak:
        draft.unsure = True
        draft.say("I'm not sure — I couldn't find a policy that covers this, and I don't want to guess.",
                  "لست متأكداً — لم أجد سياسة تغطي هذا السؤال ولا أريد أن أخمّن.")
        draft.say("I can send your question to HR Operations, who will reply directly (service level: 3 working days).",
                  "يمكنني إرسال سؤالك إلى فريق عمليات الموارد البشرية للرد عليك مباشرة (مستوى الخدمة: 3 أيام عمل).")
        draft.cite("POL-PRV-001 §7.1")
        draft.action({"id": "ask:HR", "type": "ASK_HUMAN", "question": msg, "primary": True,
                      "label": draft.t("Send my question to HR Operations", "إرسال سؤالي إلى عمليات الموارد البشرية"),
                      "owner": {"role": "HR Operations", "name": "HR Operations"}})
        return
    draft.say("Here's what the policy says:", "إليك ما تنص عليه السياسة:")
    for h in hits[:3]:
        if h["score"] >= top["score"] * 0.6:
            draft.policy_line(h["cite"], "• ", "• ")
    draft.say("Your offer or transfer letter takes precedence if it says something different.",
              "يُعتمد خطاب العرض أو الانتقال الخاص بك إذا اختلف عن ذلك.")
    draft.cite("POL-ALW-001 §6.1")


# --------------------------------------------------------------------------
# Guardrails
# --------------------------------------------------------------------------
def _mentions_other_employee(msg, emp_id):
    ids = set(re.findall(r"EMP-\d{4}", msg.upper()))
    if ids - {emp_id}:
        return True
    if not re.search(OTHER_DATA_WORDS, msg, re.I):
        return False
    me = pack.employees[emp_id]
    for e in pack.employees.values():
        if e["employee_id"] == emp_id or e["first_name"] == me["first_name"]:
            continue
        if re.search(rf"\b{re.escape(e['first_name'])}('s|’s)?\b", msg) and re.search(rf"\b{re.escape(e['first_name'])}('s|’s)", msg):
            return True
        if f"{e['first_name']} {e['last_name']}".lower() in msg.lower():
            return True
    return False


def guardrails(draft, msg, emp):
    if re.search(BYPASS_RE, msg, re.I) or _mentions_other_employee(msg, emp["employee_id"]):
        draft.refused = True
        draft.intent = "REFUSED_OTHER_DATA"
        draft.say("I can't help with that. I only ever show you **your own** information, and I can't set aside the rules that protect everyone's privacy.",
                  "لا يمكنني المساعدة في ذلك. أعرض لك **معلوماتك فقط**، ولا يمكنني تجاوز القواعد التي تحمي خصوصية الجميع.")
        draft.policy_line("POL-PRV-001 §4.1", "• ", "• ")
        return True
    if re.search(MONITOR_RE, msg, re.I):
        draft.refused = True
        draft.intent = "REFUSED_MONITORING"
        draft.say("I can't do that — the companion works for each employee and isn't a monitoring tool. Managers see journey step progress only.",
                  "لا يمكنني ذلك — المساعد يعمل لصالح كل موظف وليس أداة مراقبة. يرى المديرون تقدم خطوات الرحلة فقط.")
        draft.policy_line("POL-PRV-001 §1.2", "• ", "• ")
        draft.policy_line("POL-PRV-001 §5.1", "• ", "• ")
        return True
    if re.search(APPROVE_RE, msg, re.I):
        draft.intent = "CANNOT_APPROVE"
        draft.say("I can't approve or change that myself — decisions that affect you are always made by a named person. "
                  "Here's where it stands and who owns it:",
                  "لا يمكنني اعتماد ذلك أو تغييره بنفسي — القرارات التي تخصك يتخذها دائماً شخص مسؤول. إليك الوضع الحالي والمسؤول عنه:")
        draft.policy_line("POL-PRV-001 §6.1", "• ", "• ")
        ev = evaluate(emp["employee_id"])
        pending = [s for s in ev["steps"] if s["status"] not in ("DONE", "DONE_LATE")][:1]
        for s in pending:
            _describe_step(draft, ev, s, emp)
            draft.action({"id": f"esc:{s['code']}", "type": "ESCALATE", "step": s["code"], "primary": False,
                          "label": draft.t(f"Ask {s['escalation']['name']} for an update", f"طلب تحديث من {s['escalation']['name']}"),
                          "owner": s["escalation"], "can_include_pulse": False})
        return True
    return False


# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------
def route(emp_id, msg, ui_lang="en"):
    emp = pack.employees[emp_id]
    lang = "ar" if has_arabic(msg) else ("ar" if ui_lang == "ar" and not re.search(r"[a-zA-Z]{3,}", msg) else "en")
    draft = Draft(lang)
    draft._msg = msg.lower()
    if guardrails(draft, msg, emp):
        return draft, evaluate(emp_id)
    ev = evaluate(emp_id)
    low = msg.lower()
    if re.search(PRIVACY_RE, low) and not re.search(r"objective", low):
        draft.intent = "PRIVACY"
        compose_privacy(draft, ev, emp)
        return draft, ev
    if re.search(HUMAN_RE, low):
        draft.intent = "HANDOFF"
        draft.say("Of course. I'll hand this to a person — choose who below. You'll see exactly what's shared before it goes.",
                  "بالتأكيد. سأحوّل الأمر إلى شخص مسؤول — اختر أدناه. سترى ما ستتم مشاركته قبل الإرسال.")
        bad = [s for s in ev["steps"] if s["status"] in ("STALLED", "AT_RISK")]
        for s in bad[:2]:
            _escalate_action(draft, s)
        _hrbp_action(draft, emp, len(usable_pulse(emp_id)) > 0)
        draft.cite("POL-SRV-001 §3.3", "POL-PRV-001 §5.2")
        return draft, ev
    if re.search(SMALLTALK_RE, low.strip()):
        draft.intent = "SMALLTALK"
        if re.search(r"thank|شكر", low):
            draft.say("You're welcome. I'm here whenever something's unclear or stuck.", "على الرحب والسعة. أنا هنا متى ما احتجت شيئاً.")
            return draft, ev
        compose_status(draft, ev, emp, greeting=True)
        return draft, ev
    if re.search(CONTACT_RE, low):
        draft.intent = "CONTACTS"
        draft.say(f"Your HR Business Partner is **{emp['hrbp_name']}** and your line manager is **{emp['manager_name']}**.",
                  f"شريك الموارد البشرية الخاص بك هو **{emp['hrbp_name']}** ومديرك المباشر هو **{emp['manager_name']}**.")
        if emp.get("releasing_manager_name"):
            draft.say(f"Your current (releasing) manager is **{emp['releasing_manager_name']}**.",
                      f"مديرك الحالي هو **{emp['releasing_manager_name']}**.")
        draft.policy_line("POL-ONB-001 §6.1" if ev["journey_type"] == "ONBOARDING" else "POL-MOB-001 §4.3", "• ", "• ")
        _hrbp_action(draft, emp, len(usable_pulse(emp_id)) > 0)
        return draft, ev
    matched = [(t, codes) for t, rx, codes in TOPICS if re.search(rx, low)]
    if not matched and re.search(r"\bIT\b", msg):
        matched = [("laptop", ["IT_KIT_ISSUED"]), ("access", ["SYSTEM_ACCESS_GRANTED", "ACCESS_TRANSFERRED"])]
    if (matched and _looks_like_general_policy(low) and not has_arabic(msg)
            and not re.search(STATUS_RE, low) and not re.search(r"\bmy\b", low)):
        oov = [w for w in tokenize(msg) if w not in library.idf and w not in GENERIC_WORDS and not w.isdigit()]
        if oov:  # asks about something no policy mentions (e.g. "hardship allowance", "my cat")
            draft.intent = "POLICY"
            compose_policy(draft, ev, emp, msg)
            return draft, ev
    # "how am I doing / what's happening with my move" -> topic if the topic has a problem
    if matched:
        topic, codes = _best_topic(matched, ev)
        status_q = re.search(STATUS_RE, low)
        steps = {s["code"]: s for s in ev["steps"]}
        topic_problem = any(steps.get(c, {}).get("status") in ("STALLED", "AT_RISK", "DUE_TODAY") for c in codes)
        if status_q and re.search(r"good to go|all set|ready|can i (fly|travel|start|go)|جاهز", low):
            draft.intent = "STATUS"
            compose_status(draft, ev, emp)
            return draft, ev
        draft.intent = f"TOPIC:{topic}"
        if re.search(EMOTION_RE, low) and topic != "lost":
            draft.say("That sounds frustrating — let's see what's going on.", "يبدو ذلك محبطاً — دعنا نرى ما يحدث.")
        has_steps = any(c in steps for c in codes)
        if _looks_like_general_policy(low) and not topic_problem and has_steps and topic not in ("allowance", "lost"):
            compose_policy(draft, ev, emp, msg)
            return draft, ev
        compose_topic(draft, ev, emp, topic, codes)
        return draft, ev
    if re.search(STATUS_RE, low):
        draft.intent = "STATUS"
        compose_status(draft, ev, emp)
        return draft, ev
    if re.search(EMOTION_RE, low):
        draft.intent = "SUPPORT"
        draft.say("Thanks for telling me. Let's look at where things are, and I can connect you with your HR Business Partner if you'd like.",
                  "شكراً لإخباري. دعنا نراجع وضعك، ويمكنني توصيلك بشريك الموارد البشرية إذا رغبت.")
        compose_status(draft, ev, emp)
        _hrbp_action(draft, emp, len(usable_pulse(emp_id)) > 0)
        return draft, ev
    draft.intent = "POLICY"
    compose_policy(draft, ev, emp, msg)
    return draft, ev


def _best_topic(matched, ev):
    steps = {s["code"]: s for s in ev["steps"]}

    def score(item):
        topic, codes = item
        present = [steps[c] for c in codes if c in steps]
        worst = min((STATUS_ORDER.get(s["status"], 9) for s in present), default=10)
        return (worst, 0 if present else 1)
    # prefer explicit allowance questions
    for t, c in matched:
        if t == "allowance":
            return t, c
    return sorted(matched, key=score)[0]


def _looks_like_general_policy(low):
    return bool(re.search(r"^(can|is|are|do|does|what is|what are|how much|how many|how long|am i (allowed|entitled|eligible)|what.?s the policy|is there)", low.strip())
                or re.search(r"(will|does) the company (pay|cover)|who pays|is it covered|am i (entitled|eligible)", low))


def render(draft):
    return "\n\n".join(draft.lines)


def chat(emp_id, msg, ui_lang="en", thread_id=None):
    """One turn in the employee's conversation. Rafiq keeps one continuous conversation per employee
    (started on the first message); the AI writer sees its recent history."""
    msg = (msg or "").strip()[:1500]
    if thread_id and not state.thread_get(emp_id, thread_id):
        thread_id = None
    if not thread_id:  # one continuous conversation per employee: continue the latest
        latest = state.threads(emp_id)
        thread_id = latest[0]["id"] if latest else None
    draft, ev = route(emp_id, msg, ui_lang)
    text = render(draft)
    mode = "offline"
    if config.LLM_PROVIDER != "offline" and not draft.refused:
        written = llm.rewrite(emp_id, msg, draft, ev, history=_history(emp_id, thread_id) if thread_id else [])
        if written:
            text, mode = written, "ai"
        else:
            mode = "offline_fallback"
    cites = [dict(cite=c, **{k: library.get(c)[k] for k in ("title", "heading", "text")}) for c in draft.cites]
    new = thread_id is None
    if new:
        thread_id = state.thread_create(emp_id, _title(draft, ev, msg))
    out = {"reply": text, "lang": draft.lang, "intent": draft.intent, "citations": cites, "actions": draft.actions,
           "refused": draft.refused, "unsure": draft.unsure, "steps": draft.steps, "mode": mode,
           "overall": ev["overall"], "thread_id": thread_id, "new_thread": new}
    _remember(emp_id, msg, out)
    return out


def _title(draft, ev, msg):
    """A short name for a new conversation: the journey step it's about, else the topic, else the question."""
    ar = draft.lang == "ar"
    if draft.steps:
        s = next((x for x in ev["steps"] if x["code"] == draft.steps[0]), None)
        if s:
            return s["label_ar"] if ar else s["label"]
    named = {"PRIVACY": ("Privacy and your data", "الخصوصية وبياناتك"), "STATUS": ("Your journey", "رحلتك"),
             "SUPPORT": ("Getting support", "الحصول على الدعم"), "CONTACTS": ("Your contacts", "جهات الاتصال")}
    if draft.intent in named:
        return named[draft.intent][1 if ar else 0]
    t = re.sub(r"\s+", " ", msg).strip().rstrip("?.!")
    return (t[:46] + "…") if len(t) > 47 else t


def brief(emp_id, ui_lang="en"):
    emp = pack.employees[emp_id]
    lang = ui_lang if ui_lang in ("en", "ar") else emp["preferred_language"]
    draft = Draft(lang)
    draft._msg = ""
    ev = evaluate(emp_id)
    draft.intent = "BRIEF"
    compose_status(draft, ev, emp, greeting=True)
    cites = [dict(cite=c, **{k: library.get(c)[k] for k in ("title", "heading", "text")}) for c in draft.cites]
    return {"reply": render(draft), "lang": lang, "intent": "BRIEF", "citations": cites, "actions": draft.actions,
            "refused": False, "unsure": False, "steps": draft.steps, "mode": "offline", "overall": ev["overall"]}


def _history(emp_id, thread_id=None):
    return state.conv_recent(emp_id, 6, thread_id)


def _remember(emp_id, msg, out):
    state.conv_append(emp_id, "user", msg, out["thread_id"])
    meta = {k: out[k] for k in ("lang", "intent", "citations", "actions", "refused", "unsure", "mode")}
    state.conv_append(emp_id, "assistant", out["reply"], out["thread_id"], meta)
