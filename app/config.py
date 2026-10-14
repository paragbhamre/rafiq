"""Runtime configuration (environment variables) and journey definitions.

Journey definitions mirror data/journey_maps.md. When the official pack arrives, update
STEPS / ESCALATION_CONTACTS here and the column map in data.py; nothing else should change.
"""
import datetime as dt
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("RAFIQ_DATA_DIR", ROOT / "data"))
RUNTIME_DIR = Path(os.getenv("RAFIQ_RUNTIME_DIR", ROOT / "runtime"))

# "Today" for the prototype. The synthetic pack is built for 2026-10-14.
AS_OF = dt.date.fromisoformat(os.getenv("RAFIQ_AS_OF", "2026-10-14"))

# LLM provider: "offline" (deterministic, no external calls), "anthropic", or "openai"
# ("openai" covers any OpenAI-compatible endpoint, including Azure OpenAI and local gateways).
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "offline").lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_STYLE = os.getenv("OPENAI_API_STYLE", "openai")  # "openai" or "azure"
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "25"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "3000"))

# Minimum group size for any aggregated insight (POL-PRV-001 §5.3)
MIN_GROUP_SIZE = int(os.getenv("RAFIQ_MIN_GROUP_SIZE", "10"))

# --------------------------------------------------------------------------
# Journey steps
# applies: None (always) or a (field, allowed_values) tuple on the employee record
# prereqs: list of codes; "A|B" = A if A applies to this employee, else B
# policy:  citations most relevant to the step (used for routing answers)
# --------------------------------------------------------------------------
LOC_MOVES = ("LOCATION_DOMESTIC", "LOCATION_INTERNATIONAL")

STEPS = {
    "ONBOARDING": [
        dict(code="OFFER_ACCEPTED", label="Offer accepted", label_ar="قبول العرض", team="Talent Acquisition", role="Recruiter", day=-45, grace=0, applies=None, prereqs=[], esc="Recruiter", policy=["POL-ONB-001 §1.1"]),
        dict(code="BACKGROUND_CHECK_CLEARED", label="Background and reference check cleared", label_ar="اجتياز التحقق من الخلفية", team="Talent Acquisition", role="Recruiter", day=-30, grace=5, applies=None, prereqs=["OFFER_ACCEPTED"], esc="Recruiter", policy=["POL-ONB-001 §2.1"]),
        dict(code="VISA_APPLICATION_SUBMITTED", label="Employment visa application submitted", label_ar="تقديم طلب تأشيرة العمل", team="Government Relations (PRO)", role="PRO Officer", day=-28, grace=3, applies=("visa_required", ("true",)), prereqs=["BACKGROUND_CHECK_CLEARED"], esc="PRO Team Lead", policy=["POL-PRO-001 §3.1", "POL-PRO-001 §3.2", "POL-PRO-001 §2.1"]),
        dict(code="MEDICAL_COMPLETED", label="Visa medical fitness test completed", label_ar="إجراء الفحص الطبي للتأشيرة", team="Government Relations (PRO)", role="PRO Officer", day=-18, grace=3, applies=("visa_required", ("true",)), prereqs=["VISA_APPLICATION_SUBMITTED"], esc="PRO Team Lead", policy=["POL-PRO-001 §4.1", "POL-PRO-001 §4.2", "POL-PRO-001 §4.3"]),
        dict(code="VISA_ISSUED", label="Entry or employment visa issued", label_ar="إصدار التأشيرة", team="Government Relations (PRO)", role="PRO Officer", day=-10, grace=2, applies=("visa_required", ("true",)), prereqs=["MEDICAL_COMPLETED"], esc="PRO Team Lead", policy=["POL-PRO-001 §5.1", "POL-PRO-001 §6.2", "POL-PRO-001 §6.3"]),
        dict(code="JOINING_TICKET_ISSUED", label="Joining flight ticket issued", label_ar="إصدار تذكرة الالتحاق", team="HR Operations", role="HR Officer", day=-7, grace=2, applies=("relocating_from_abroad", ("true",)), prereqs=["VISA_ISSUED|BACKGROUND_CHECK_CLEARED"], esc="HR Business Partner", policy=["POL-TRV-001 §1.3", "POL-TRV-001 §4.1"]),
        dict(code="ACCOMMODATION_ASSIGNED", label="Staff accommodation or temporary housing assigned", label_ar="تخصيص السكن", team="Facilities", role="Accommodation Coordinator", day=-5, grace=2, applies=("accommodation_eligible", ("true",)), prereqs=["BACKGROUND_CHECK_CLEARED"], esc="Facilities Manager", policy=["POL-ACC-001 §2.1", "POL-ACC-001 §2.2", "POL-ACC-001 §4.2", "POL-ACC-001 §4.3"]),
        dict(code="IT_KIT_ISSUED", label="Laptop and phone issued", label_ar="تسليم الحاسوب والهاتف", team="IT Service Desk", role="IT Onboarding Analyst", day=1, grace=1, applies=None, prereqs=["BACKGROUND_CHECK_CLEARED"], esc="IT Service Delivery Manager", policy=["POL-IT-001 §2.1", "POL-IT-001 §5.1", "POL-IT-001 §4.3"]),
        dict(code="SYSTEM_ACCESS_GRANTED", label="Network, email and core system access granted", label_ar="منح صلاحيات الأنظمة", team="IT Service Desk", role="IT Onboarding Analyst", day=2, grace=1, applies=None, prereqs=["IT_KIT_ISSUED"], esc="IT Service Delivery Manager", policy=["POL-IT-001 §2.2", "POL-IT-001 §4.2", "POL-IT-001 §5.2"]),
        dict(code="STAFF_ID_ISSUED", label="Staff ID and building or airside pass issued", label_ar="إصدار بطاقة الموظف", team="Security", role="Pass Office", day=3, grace=2, applies=None, prereqs=["BACKGROUND_CHECK_CLEARED"], esc="Security Duty Manager", policy=["POL-SEC-001 §1.2", "POL-SEC-001 §4.1"]),
        dict(code="BUDDY_ASSIGNED", label="Onboarding buddy assigned", label_ar="تعيين زميل مرافق", team="Line Management", role="Line Manager", day=1, grace=2, applies=None, prereqs=[], esc="HR Business Partner", policy=["POL-ONB-001 §3.4"]),
        dict(code="EMIRATES_ID_APPLIED", label="Emirates ID and residency stamping applied", label_ar="التقديم على الهوية الإماراتية", team="Government Relations (PRO)", role="PRO Officer", day=7, grace=3, applies=("visa_required", ("true",)), prereqs=["VISA_ISSUED"], esc="PRO Team Lead", policy=["POL-PRO-001 §5.2"]),
        dict(code="INDUCTION_COMPLETED", label="Corporate induction attended", label_ar="حضور برنامج التعريف", team="Learning & Development", role="L&D Coordinator", day=5, grace=2, applies=None, prereqs=["SYSTEM_ACCESS_GRANTED"], esc="L&D Manager", policy=["POL-LRN-001 §1.1", "POL-LRN-001 §1.2", "POL-ONB-001 §3.5"]),
        dict(code="MANDATORY_TRAINING_BOOKED", label="Mandatory compliance training booked", label_ar="حجز التدريب الإلزامي", team="Learning & Development", role="L&D Coordinator", day=7, grace=3, applies=None, prereqs=["INDUCTION_COMPLETED"], esc="L&D Manager", policy=["POL-LRN-001 §2.2", "POL-LRN-001 §5.1"]),
        dict(code="PROBATION_OBJECTIVES_SET", label="Probation objectives agreed with manager", label_ar="الاتفاق على أهداف فترة التجربة", team="Line Management", role="Line Manager", day=30, grace=5, applies=None, prereqs=[], esc="HR Business Partner", policy=["POL-ONB-002 §2.1", "POL-ONB-002 §2.2"]),
        dict(code="CHECKIN_30_DONE", label="30-day check-in completed", label_ar="مراجعة الثلاثين يوماً", team="HR Business Partnering", role="HR Business Partner", day=30, grace=5, applies=None, prereqs=[], esc="HR Business Partner", policy=["POL-ONB-001 §4.3"]),
    ],
    "MOBILITY": [
        dict(code="MOVE_REQUESTED", label="Move requested or offered", label_ar="طلب الانتقال", team="HR Business Partnering", role="HR Business Partner", day=0, grace=0, applies=None, prereqs=[], esc="HR Business Partner", policy=["POL-MOB-001 §1.1"]),
        dict(code="RECEIVING_MANAGER_ENDORSED", label="Receiving manager endorsement", label_ar="موافقة المدير المستقبِل", team="Line Management", role="Receiving Manager", day=5, grace=2, applies=None, prereqs=["MOVE_REQUESTED"], esc="HR Business Partner", policy=["POL-MOB-001 §3.1", "POL-MOB-001 §4.1"]),
        dict(code="RELEASING_MANAGER_RELEASED", label="Releasing manager agrees release date", label_ar="موافقة المدير الحالي على موعد الانتقال", team="Line Management", role="Releasing Manager", day=7, grace=3, applies=None, prereqs=["MOVE_REQUESTED"], esc="HR Business Partner", policy=["POL-MOB-001 §3.2", "POL-MOB-001 §4.2"]),
        dict(code="TRANSFER_APPROVED", label="Transfer approved by HR", label_ar="اعتماد الانتقال من الموارد البشرية", team="HR Operations", role="HR Officer", day=12, grace=3, applies=None, prereqs=["RECEIVING_MANAGER_ENDORSED", "RELEASING_MANAGER_RELEASED"], esc="HR Business Partner", policy=["POL-MOB-001 §3.3"]),
        dict(code="TRANSFER_LETTER_ISSUED", label="Transfer letter issued with new terms", label_ar="إصدار خطاب الانتقال", team="HR Operations", role="HR Officer", day=14, grace=2, applies=None, prereqs=["TRANSFER_APPROVED"], esc="HR Business Partner", policy=["POL-MOB-001 §3.4"]),
        dict(code="RELOCATION_ASSESSED", label="Relocation package assessed", label_ar="تقييم حزمة الانتقال", team="Global Mobility", role="Mobility Specialist", day=16, grace=3, applies=("move_type", LOC_MOVES), prereqs=["TRANSFER_APPROVED"], esc="Global Mobility Lead", policy=["POL-MOB-002 §1.1", "POL-MOB-002 §1.2"]),
        dict(code="WORK_PERMIT_ISSUED", label="Destination work permit or visa issued", label_ar="إصدار تصريح العمل في بلد الوجهة", team="Global Mobility", role="Mobility Specialist", day=26, grace=3, applies=("move_type", ("LOCATION_INTERNATIONAL",)), prereqs=["RELOCATION_ASSESSED"], esc="Global Mobility Lead", policy=["POL-MOB-002 §3.1", "POL-MOB-002 §3.2", "POL-MOB-002 §5.1"]),
        dict(code="RELOCATION_ALLOWANCE_PAID", label="Relocation allowance paid", label_ar="صرف بدل الانتقال", team="Payroll", role="Payroll Officer", day=25, grace=3, applies=("move_type", LOC_MOVES), prereqs=["RELOCATION_ASSESSED"], esc="Payroll Manager", policy=["POL-ALW-001 §4.1", "POL-ALW-001 §4.2", "POL-MOB-002 §4.1", "POL-MOB-002 §4.2"]),
        dict(code="HOUSING_ARRANGED", label="Housing at new location arranged", label_ar="ترتيب السكن في الموقع الجديد", team="Facilities", role="Accommodation Coordinator", day=27, grace=2, applies=("move_type", LOC_MOVES), prereqs=["RELOCATION_ASSESSED"], esc="Facilities Manager", policy=["POL-ACC-001 §3.2", "POL-ACC-001 §3.3"]),
        dict(code="HANDOVER_COMPLETED", label="Handover of current role completed", label_ar="إتمام تسليم المهام", team="Line Management", role="Releasing Manager", day=29, grace=2, applies=None, prereqs=["RELEASING_MANAGER_RELEASED"], esc="HR Business Partner", policy=["POL-MOB-001 §3.2"]),
        dict(code="ACCESS_TRANSFERRED", label="Systems access switched to new role", label_ar="نقل صلاحيات الأنظمة للدور الجديد", team="IT Service Desk", role="IT Access Analyst", day=30, grace=1, applies=None, prereqs=["TRANSFER_APPROVED"], esc="IT Service Delivery Manager", policy=["POL-IT-001 §3.1", "POL-IT-001 §4.2", "POL-IT-001 §4.3"]),
        dict(code="MOVE_EFFECTIVE", label="Move effective, starts new role", label_ar="سريان الانتقال وبدء الدور الجديد", team="HR Operations", role="HR Officer", day=30, grace=0, applies=None, prereqs=["TRANSFER_LETTER_ISSUED", "WORK_PERMIT_ISSUED|TRANSFER_LETTER_ISSUED"], esc="HR Business Partner", policy=["POL-MOB-001 §5.1"]),
        dict(code="ROLE_TRAINING_BOOKED", label="Role-specific training booked", label_ar="حجز تدريب الدور الجديد", team="Learning & Development", role="L&D Coordinator", day=40, grace=3, applies=None, prereqs=["MOVE_EFFECTIVE"], esc="L&D Manager", policy=["POL-LRN-001 §3.1", "POL-LRN-001 §3.2"]),
        dict(code="CHECKIN_30_DONE", label="30-day check-in in new role", label_ar="مراجعة الثلاثين يوماً في الدور الجديد", team="HR Business Partnering", role="HR Business Partner", day=60, grace=5, applies=None, prereqs=["MOVE_EFFECTIVE"], esc="HR Business Partner", policy=["POL-MOB-001 §5.3"]),
    ],
}

STAGES = {
    "ONBOARDING": [("PRE_ARRIVAL", -999, -1, "Before you join", "قبل الالتحاق"),
                   ("FIRST_WEEK", 0, 6, "First week", "الأسبوع الأول"),
                   ("FIRST_MONTH", 7, 30, "First month", "الشهر الأول"),
                   ("SETTLING_IN", 31, 9999, "Settling in", "مرحلة الاستقرار")],
    "MOBILITY": [("MOVE_REQUESTED", -999, 4, "Move requested", "تم طلب الانتقال"),
                 ("APPROVALS", 5, 14, "Approvals", "الموافقات"),
                 ("PRE_MOVE", 15, 29, "Preparing to move", "التحضير للانتقال"),
                 ("IN_NEW_ROLE", 30, 9999, "In your new role", "في دورك الجديد")],
}

# Named human owners for escalations (synthetic). HRBP and Recruiter resolve per employee.
ESCALATION_CONTACTS = {
    "PRO Team Lead": ("Khalid Al Mansoori", "pro.escalations@example.test"),
    "IT Service Delivery Manager": ("Priya Raman", "it.delivery@example.test"),
    "Facilities Manager": ("Omar Haddad", "facilities.mgr@example.test"),
    "Global Mobility Lead": ("Sarah Whitfield", "mobility.lead@example.test"),
    "Payroll Manager": ("Fatima Al Zarooni", "payroll.mgr@example.test"),
    "L&D Manager": ("Daniel Okafor", "ld.mgr@example.test"),
    "Security Duty Manager": ("Rashid Al Ketbi", "security.duty@example.test"),
    "Recruiter": ("Talent Acquisition desk", "ta@example.test"),
}

# Service-request routing for actions the companion can start (POL-SRV-001 §2)
REQUEST_TYPES = {
    "IT_LOAN_DEVICE": dict(category="IT", request_type="Loan device", team="IT Service Desk", sla=0.5, label="Request a temporary loan device", label_ar="طلب جهاز مؤقت", policy="POL-IT-001 §5.1"),
    "IT_EQUIPMENT": dict(category="IT", request_type="Equipment issue", team="IT Service Desk", sla=2, label="Raise an IT equipment request", label_ar="فتح طلب معدات تقنية", policy="POL-IT-001 §4.1"),
    "IT_ACCESS": dict(category="IT", request_type="System access", team="IT Service Desk", sla=1, label="Raise a system access request", label_ar="فتح طلب صلاحيات", policy="POL-IT-001 §4.2"),
    "LD_REBOOK_INDUCTION": dict(category="LEARNING", request_type="Training booking", team="Learning & Development", sla=3, label="Rebook my induction", label_ar="إعادة حجز برنامج التعريف", policy="POL-LRN-001 §1.2"),
    "LD_BOOK_TRAINING": dict(category="LEARNING", request_type="Training booking", team="Learning & Development", sla=3, label="Book my training", label_ar="حجز التدريب", policy="POL-LRN-001 §4.1"),
    "FAC_ACCOMMODATION": dict(category="FACILITIES", request_type="Accommodation", team="Facilities", sla=3, label="Raise an accommodation request", label_ar="فتح طلب سكن", policy="POL-ACC-001 §4.1"),
    "PRO_VISA": dict(category="PRO", request_type="Visa, medical or Emirates ID step", team="Government Relations (PRO)", sla=5, label="Ask PRO for a visa update", label_ar="طلب تحديث من فريق التأشيرات", policy="POL-PRO-001 §6.1"),
    "PAYROLL_ALLOWANCE": dict(category="PAYROLL", request_type="Allowance payment", team="Payroll", sla=5, label="Follow up with Payroll", label_ar="المتابعة مع فريق الرواتب", policy="POL-MOB-002 §4.2"),
    "MOBILITY_QUERY": dict(category="MOBILITY", request_type="Relocation or work permit query", team="Global Mobility", sla=3, label="Ask Global Mobility for an update", label_ar="طلب تحديث من فريق التنقل", policy="POL-SRV-001 §2"),
    "HR_QUERY": dict(category="HR", request_type="General HR query", team="HR Operations", sla=3, label="Send my question to HR Operations", label_ar="إرسال سؤالي إلى عمليات الموارد البشرية", policy="POL-SRV-001 §2"),
    "SEC_ID": dict(category="SECURITY", request_type="Staff ID or pass", team="Security", sla=2, label="Raise a staff ID request", label_ar="فتح طلب بطاقة موظف", policy="POL-SEC-001 §4.1"),
}

# Personalised entitlements (POL-ALW-001). Amounts in AED.
HOUSING_ALLOWANCE = {"G1": 4500, "G2": 4500, "G3": 6500, "G4": 6500, "G5": 9000, "G6": 9000}
