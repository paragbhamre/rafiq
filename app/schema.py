"""What Rafiq expects from a data pack, in one place.

Used by the loader (app/data.py) to normalise a pack and by the compatibility report
(tools/ingest.py) to check one. A pack may rename files, columns and values through an
optional `mapping.json` in the pack folder; see packs/README.md.
"""
import datetime as dt
import re

# logical name -> default file name
FILES = {
    "employees": "employees.csv",
    "events": "journey_events.csv",
    "requests": "service_requests.csv",
    "pulse": "pulse_feedback.csv",
}

# Columns: required (load fails without them) and optional (filled with the default when absent)
REQUIRED = {
    "employees": ["employee_id", "first_name", "last_name", "journey_type", "journey_anchor_date",
                  "manager_id", "manager_name", "hrbp_id", "hrbp_name"],
    "events": ["employee_id", "event_code", "event_timestamp"],
    "requests": ["request_id", "employee_id", "status"],
    "pulse": ["employee_id", "submitted_at", "score", "consent_status"],
}
OPTIONAL = {
    "employees": {"preferred_language": "en", "journey_stage": "", "journey_day": "", "move_effective_date": "",
                  "move_type": "", "department": "", "role_title": "", "grade": "", "location": "",
                  "from_location": "", "from_department": "", "from_role_title": "", "releasing_manager_name": "",
                  "visa_required": "false", "relocating_from_abroad": "false", "accommodation_eligible": "false",
                  "family_status": "", "pulse_opt_in": "false"},
    "events": {"event_id": "", "journey_type": "", "event_label": "", "actor_team": "", "source_system": "", "notes": ""},
    "requests": {"category": "", "request_type": "", "linked_event_code": "", "subject": "", "description": "",
                 "priority": "MEDIUM", "owner_team": "", "owner_name": "", "created_at": "", "last_updated_at": "",
                 "resolved_at": "", "sla_days": "", "days_open": ""},
    "pulse": {"response_id": "", "journey_type": "", "journey_stage": "", "question_id": "", "question_text": "",
              "comment": "", "language": "en"},
}

BOOLEAN = {"employees": ["visa_required", "relocating_from_abroad", "accommodation_eligible", "pulse_opt_in"]}
DATES = {
    "employees": ["journey_anchor_date", "move_effective_date"],
    "events": ["event_timestamp"],
    "requests": ["created_at", "last_updated_at", "resolved_at"],
    "pulse": ["submitted_at"],
}
# Allowed values after mapping. Values outside these sets are reported (and, for blockers, refused).
ENUMS = {
    "employees": {"journey_type": {"ONBOARDING", "MOBILITY"}, "preferred_language": {"en", "ar"},
                  "move_type": {"", "ROLE_CHANGE", "TEAM_CHANGE", "LOCATION_DOMESTIC", "LOCATION_INTERNATIONAL"},
                  "family_status": {"", "SINGLE", "FAMILY"}},
    "requests": {"status": {"OPEN", "IN_PROGRESS", "PENDING_INFO", "RESOLVED", "CLOSED"},
                 "priority": {"", "LOW", "MEDIUM", "HIGH"}},
    "pulse": {"consent_status": {"ACTIVE", "WITHDRAWN"}},
}
# Enum problems that stop the app from working correctly (others are warnings)
BLOCKING_ENUMS = {("employees", "journey_type"), ("pulse", "consent_status"), ("requests", "status")}

TRUE_WORDS = {"true", "yes", "y", "1", "t"}
FALSE_WORDS = {"false", "no", "n", "0", "f", ""}


def norm_bool(v):
    s = str(v or "").strip().lower()
    if s in TRUE_WORDS:
        return "true"
    if s in FALSE_WORDS:
        return "false"
    return None


_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d %b %Y", "%d %B %Y", "%Y/%m/%d"]


def norm_date(v, with_time=False):
    """Return an ISO date (or the original ISO timestamp) or None if it can't be read."""
    s = str(v or "").strip()
    if not s:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}([T ].*)?$", s):
        try:
            dt.date.fromisoformat(s[:10])
            return s.replace(" ", "T", 1) if with_time and len(s) > 10 else (s if with_time else s[:10])
        except ValueError:
            return None
    for fmt in _DATE_FORMATS:
        for cand in (s, s.split(" ")[0], s.split("T")[0]):
            try:
                d = dt.datetime.strptime(cand, fmt).date()
                return d.isoformat()
            except ValueError:
                continue
    return None
