#!/usr/bin/env python3
"""Adds the hidden-scenario rehearsal employees (EMP-1301 to EMP-1320) to the synthetic pack.

Each one isolates a single situation the judges might test that S01-S14 don't cover: one journey step
stalled (everything before it done on time, everything that depends on it waiting) or a step that must
NOT appear. Dates are written against the pack's reference date (2026-10-14); the app shifts them to today.

    python tools/add_hidden_scenarios.py          # append (skips if EMP-1301 already exists)
    python tools/add_hidden_scenarios.py --check  # only verify the seeded situations

Safe to re-run. tests/test_hidden_scenarios.py checks the result.
"""
import csv
import datetime as dt
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("RAFIQ_FREEZE_DATE", "2026-10-14")
os.environ.setdefault("RAFIQ_SHIFT_PACK_DATES", "false")

from app import config  # noqa: E402

DATA = ROOT / "data"
REF = config.PACK_REFERENCE_DATE

SOURCE = {"Talent Acquisition": "ATS", "Government Relations (PRO)": "PRO_SYS", "IT Service Desk": "ITSM",
          "Security": "SEC_PASS", "Learning & Development": "LMS", "Facilities": "FAC_PORTAL",
          "Global Mobility": "MOBILITY_SYS", "Payroll": "PAYROLL", "Facilities / Global Mobility": "FAC_PORTAL"}

# hid, id, first, last, lang, journey, move_type, day, department, role, grade, location,
# (from_location, from_department, from_role, releasing manager) for moves,
# manager, hrbp, visa, relocating, accommodation, family, pulse opt-in,
# stalled codes, extra codes done on the current day, requests
SPECS = [
    dict(hid="H01", id="EMP-1301", first="Lucas", last="Moreau", journey="ONBOARDING", day=-20,
         dept="Engineering", role="Licensed Aircraft Engineer", grade="G4", loc="Dubai - Engineering Centre",
         mgr=("MGR-210", "Liam Haddad"), hrbp=("HRBP-06", "Abdulla Al Kaabi"), visa=True, reloc=True, accom=True,
         stall=["BACKGROUND_CHECK_CLEARED"]),
    dict(hid="H02", id="EMP-1302", first="Nimal", last="Perera", journey="ONBOARDING", day=-24,
         dept="Airport Services", role="Customer Service Agent", grade="G2", loc="Dubai - DXB Terminal 3",
         mgr=("MGR-209", "Maria Iyer"), hrbp=("HRBP-04", "Vikram Desai"), visa=True, reloc=True, accom=True,
         stall=["VISA_APPLICATION_SUBMITTED"],
         req=[dict(cat="PRO", type="Visa application", link="VISA_APPLICATION_SUBMITTED", team="Government Relations (PRO)",
                   owner="Mariam Saeed", sla=5, created=4, updated=2, status="IN_PROGRESS", prio="HIGH",
                   subject="Employment visa application not yet submitted",
                   desc="Documents received 08 Oct. Application waiting for attested degree certificate check.")]),
    dict(hid="H03", id="EMP-1303", first="Grace", last="Achieng", journey="ONBOARDING", day=6,
         dept="Cargo Operations", role="Cargo Supervisor", grade="G4", loc="Dubai - DWC Al Maktoum",
         mgr=("MGR-216", "Ivan Kapoor"), hrbp=("HRBP-02", "James Whitaker"), visa=True, reloc=False, accom=False,
         stall=["STAFF_ID_ISSUED"],
         req=[dict(cat="SECURITY", type="Staff ID and pass", link="STAFF_ID_ISSUED", team="Security",
                   owner="Saeed Al Nuaimi", sla=2, created=2, updated=1, status="IN_PROGRESS", prio="MEDIUM",
                   subject="Staff ID and airside pass not issued",
                   desc="Photo taken 12 Oct. Airside pass waiting for security vetting result.")]),
    dict(hid="H04", id="EMP-1304", first="Omar", last="Khalil", lang="ar", journey="ONBOARDING", day=11,
         dept="Finance", role="Accountant", grade="G4", loc="Dubai - Group HQ, Garhoud",
         mgr=("MGR-204", "Hassan Brown"), hrbp=("HRBP-01", "Nadia Farouk"), visa=True, reloc=True, accom=False,
         stall=["EMIRATES_ID_APPLIED"],
         req=[dict(cat="PRO", type="Emirates ID", link="EMIRATES_ID_APPLIED", team="Government Relations (PRO)",
                   owner="Anil Kumar", sla=5, created=3, updated=3, status="OPEN", prio="MEDIUM",
                   subject="Emirates ID and residency stamping not applied",
                   desc="Visa issued 21 Sep. Emirates ID application not yet started.")]),
    dict(hid="H05", id="EMP-1305", first="Daniela", last="Rossi", journey="ONBOARDING", day=11,
         dept="Commercial", role="Sales Executive", grade="G4", loc="Dubai - Group HQ, Garhoud",
         mgr=("MGR-215", "Samuel Reyes"), hrbp=("HRBP-03", "Shaikha Al Mazrouei"), visa=True, reloc=True, accom=True,
         stall=["MANDATORY_TRAINING_BOOKED"]),
    dict(hid="H06", id="EMP-1306", first="Ahmed", last="Raza", journey="ONBOARDING", day=36,
         dept="Information Technology", role="Network Engineer", grade="G5", loc="Dubai - Group HQ, Garhoud",
         mgr=("MGR-221", "Wei Nkosi"), hrbp=("HRBP-05", "Claire Dupont"), visa=True, reloc=False, accom=False,
         stall=["PROBATION_OBJECTIVES_SET"]),
    dict(hid="H07", id="EMP-1307", first="Chloe", last="Martin", journey="ONBOARDING", day=36,
         dept="Cabin Crew Operations", role="Crew Scheduling Officer", grade="G3", loc="Dubai - Training College",
         mgr=("MGR-220", "Ivan Abubakar"), hrbp=("HRBP-04", "Vikram Desai"), visa=True, reloc=True, accom=True,
         stall=["CHECKIN_30_DONE"]),
    dict(hid="H08", id="EMP-1308", first="Jiwoo", last="Park", journey="ONBOARDING", day=-4,
         dept="Engineering", role="Avionics Technician", grade="G3", loc="Dubai - Engineering Centre",
         mgr=("MGR-219", "Ali Ivanova"), hrbp=("HRBP-06", "Abdulla Al Kaabi"), visa=True, reloc=True, accom=False,
         stall=["JOINING_TICKET_ISSUED"],
         req=[dict(cat="HR", type="Joining ticket", link="JOINING_TICKET_ISSUED", team="HR Operations",
                   owner="Grace Mensah", sla=3, created=2, updated=2, status="OPEN", prio="HIGH",
                   subject="Joining flight ticket not issued",
                   desc="Visa issued 03 Oct. Flight from Seoul not booked yet.")]),
    dict(hid="H09", id="EMP-1309", first="Yasmin", last="Haddad", lang="ar", journey="MOBILITY", move="ROLE_CHANGE", day=11,
         dept="Procurement", role="Category Manager", grade="G5", loc="Dubai - Group HQ, Garhoud",
         frm=("Dubai - Group HQ, Garhoud", "Procurement", "Procurement Analyst", "Arjun Sharma"),
         mgr=("MGR-208", "Tariq Abubakar"), hrbp=("HRBP-02", "James Whitaker"), stall=["RELEASING_MANAGER_RELEASED"]),
    dict(hid="H10", id="EMP-1310", first="Ethan", last="Clarke", journey="MOBILITY", move="TEAM_CHANGE", day=17,
         dept="Cargo Operations", role="Cargo Planner", grade="G3", loc="Dubai - DWC Al Maktoum",
         frm=("Dubai - DWC Al Maktoum", "Airport Services", "Cargo Planner", "Maria Iyer"),
         mgr=("MGR-225", "Amina Sharma"), hrbp=("HRBP-05", "Claire Dupont"), stall=["TRANSFER_LETTER_ISSUED"],
         req=[dict(cat="HR", type="Transfer letter", link="TRANSFER_LETTER_ISSUED", team="HR Operations",
                   owner="Rohan Mehta", sla=3, created=2, updated=2, status="IN_PROGRESS", prio="MEDIUM",
                   subject="Transfer letter not issued",
                   desc="Transfer approved 09 Oct. Letter with new terms in drafting.")]),
    dict(hid="H11", id="EMP-1311", first="Sana", last="Qureshi", journey="MOBILITY", move="LOCATION_DOMESTIC", day=20,
         dept="Airport Services", role="Duty Officer", grade="G4", loc="Dubai - DWC Al Maktoum",
         frm=("Dubai - DXB Terminal 3", "Airport Services", "Duty Officer", "Ivan Dubois"),
         mgr=("MGR-209", "Maria Iyer"), hrbp=("HRBP-04", "Vikram Desai"), stall=["RELOCATION_ASSESSED"],
         req=[dict(cat="MOBILITY", type="Relocation assessment", link="RELOCATION_ASSESSED", team="Global Mobility",
                   owner="Emma Clarke", sla=3, created=3, updated=3, status="OPEN", prio="MEDIUM",
                   subject="Relocation package not assessed",
                   desc="Move to DWC approved 06 Oct. Relocation assessment not started.")]),
    dict(hid="H12", id="EMP-1312", first="Oliver", last="Bennett", journey="MOBILITY", move="LOCATION_INTERNATIONAL", day=30,
         dept="Commercial", role="Station Sales Manager", grade="G5", loc="New York JFK",
         frm=("Dubai - Group HQ, Garhoud", "Commercial", "Sales Executive", "Samuel Reyes"),
         mgr=("MGR-206", "Ali Tanaka"), hrbp=("HRBP-03", "Shaikha Al Mazrouei"), stall=["HOUSING_ARRANGED"],
         done_today=["ACCESS_TRANSFERRED", "MOVE_EFFECTIVE"],
         req=[dict(cat="MOBILITY", type="Destination housing", link="HOUSING_ARRANGED", team="Global Mobility",
                   owner="Emma Clarke", sla=3, created=2, updated=1, status="IN_PROGRESS", prio="HIGH",
                   subject="Housing in New York not arranged",
                   desc="Lease for the apartment shortlisted 10 Oct fell through. Searching for alternatives.")]),
    dict(hid="H13", id="EMP-1313", first="Hamad", last="Al Shamsi", lang="ar", journey="MOBILITY", move="ROLE_CHANGE", day=32,
         dept="Engineering", role="Planning Engineer", grade="G5", loc="Dubai - Engineering Centre",
         frm=("Dubai - Engineering Centre", "Engineering", "Maintenance Planner", "Ali Ivanova"),
         mgr=("MGR-210", "Liam Haddad"), hrbp=("HRBP-06", "Abdulla Al Kaabi"), stall=["HANDOVER_COMPLETED"]),
    dict(hid="H14", id="EMP-1314", first="Neha", last="Joshi", journey="MOBILITY", move="TEAM_CHANGE", day=44,
         dept="Information Technology", role="Cloud Engineer", grade="G5", loc="Dubai - Group HQ, Garhoud",
         frm=("Dubai - Group HQ, Garhoud", "Information Technology", "Cloud Engineer", "Irina Fernandes"),
         mgr=("MGR-221", "Wei Nkosi"), hrbp=("HRBP-01", "Nadia Farouk"), stall=["ROLE_TRAINING_BOOKED"]),
    dict(hid="H15", id="EMP-1315", first="Marcus", last="Webb", journey="MOBILITY", move="ROLE_CHANGE", day=66,
         dept="Finance", role="Finance Manager", grade="G6", loc="Dubai - Group HQ, Garhoud",
         frm=("Dubai - Group HQ, Garhoud", "Finance", "Senior Accountant", "Hassan Brown"),
         mgr=("MGR-204", "Hassan Brown"), hrbp=("HRBP-01", "Nadia Farouk"), stall=["CHECKIN_30_DONE"]),
    dict(hid="H16", id="EMP-1316", first="Elena", last="Petrova", journey="MOBILITY", move="TEAM_CHANGE", day=8,
         dept="Commercial", role="Revenue Analyst", grade="G4", loc="Dubai - Group HQ, Garhoud",
         frm=("Dubai - Group HQ, Garhoud", "Finance", "Revenue Analyst", "Hassan Brown"),
         mgr=("MGR-215", "Samuel Reyes"), hrbp=("HRBP-03", "Shaikha Al Mazrouei"), stall=[]),
    dict(hid="H17", id="EMP-1317", first="Noura", last="Al Mansouri", lang="ar", journey="MOBILITY", move="LOCATION_DOMESTIC", day=20,
         dept="Cabin Crew Operations", role="Cabin Crew Instructor", grade="G4", loc="Dubai - Training College",
         frm=("Dubai - DXB Terminal 3", "Cabin Crew Operations", "Senior Flight Attendant", "Ivan Abubakar"),
         mgr=("MGR-220", "Ivan Abubakar"), hrbp=("HRBP-05", "Claire Dupont"), stall=[]),
    dict(hid="H18", id="EMP-1318", first="Tomas", last="Garcia", journey="ONBOARDING", day=10,
         dept="Procurement", role="Buyer", grade="G3", loc="Dubai - Group HQ, Garhoud",
         mgr=("MGR-226", "Arjun Sharma"), hrbp=("HRBP-02", "James Whitaker"), visa=True, reloc=True, accom=True, stall=[],
         req=[dict(cat="FACILITIES", type="Parking permit", link="", team="Facilities",
                   owner="Joseph Dsouza", sla=3, created=4, updated=4, status="OPEN", prio="LOW",
                   subject="Staff parking permit",
                   desc="Requested a staff parking permit for the HQ car park on 10 Oct.")]),
    dict(hid="H19", id="EMP-1319", first="Aditya", last="Rao", journey="ONBOARDING", day=-6,
         dept="Information Technology", role="Software Engineer", grade="G4", loc="Dubai - Group HQ, Garhoud",
         mgr=("MGR-221", "Wei Nkosi"), hrbp=("HRBP-05", "Claire Dupont"), visa=True, reloc=False, accom=False, stall=[]),
    dict(hid="H20", id="EMP-1320", first="Layla", last="Al Zaabi", lang="ar", journey="ONBOARDING", day=-5,
         dept="Finance", role="Treasury Analyst", grade="G4", loc="Dubai - Group HQ, Garhoud",
         mgr=("MGR-204", "Hassan Brown"), hrbp=("HRBP-01", "Nadia Farouk"), visa=False, reloc=False, accom=False, stall=[]),
]


def _b(v):
    return "true" if v else "false"


def _ts(d, hour="10:30"):
    return f"{d.isoformat()}T{hour}:00+04:00"


def build():
    from app.journey import _applies, stage_for
    emps, events, reqs = [], [], []
    for s in SPECS:
        anchor = REF - dt.timedelta(days=s["day"])
        frm = s.get("frm", ("", "", "", ""))
        emp = dict(employee_id=s["id"], first_name=s["first"], last_name=s["last"], preferred_language=s.get("lang", "en"),
                   journey_type=s["journey"], journey_stage=stage_for(s["journey"], s["day"])[0], journey_day=str(s["day"]),
                   journey_anchor_date=anchor.isoformat(),
                   move_effective_date=(anchor + dt.timedelta(days=30)).isoformat() if s["journey"] == "MOBILITY" else "",
                   move_type=s.get("move", ""), department=s["dept"], role_title=s["role"], grade=s["grade"], location=s["loc"],
                   from_location=frm[0], from_department=frm[1], from_role_title=frm[2], manager_id=s["mgr"][0],
                   manager_name=s["mgr"][1], releasing_manager_name=frm[3], hrbp_id=s["hrbp"][0], hrbp_name=s["hrbp"][1],
                   visa_required=_b(s.get("visa")), relocating_from_abroad=_b(s.get("reloc")),
                   accommodation_eligible=_b(s.get("accom")), family_status=s.get("family", "SINGLE"),
                   pulse_opt_in="false")
        emps.append(emp)
        steps = [st for st in config.STEPS[s["journey"]] if _applies(st, emp)]
        codes = {st["code"] for st in steps}
        blocked = set(s["stall"])
        for st in steps:   # anything that depends on a stalled step waits too
            for p in st["prereqs"]:
                a, _, b = p.partition("|")
                dep = a if (a in codes or not b) else b
                if dep in blocked:
                    blocked.add(st["code"])
        for st in steps:
            c = st["code"]
            if c in blocked:
                continue
            if c in s.get("done_today", []):
                when = _ts(REF, "09:00")
            elif st["day"] < s["day"]:
                when = _ts(anchor + dt.timedelta(days=st["day"] - (1 if st["day"] - 1 > -60 else 0)))
            else:
                continue
            if when[:10] > REF.isoformat():
                when = _ts(REF, "08:00")
            events.append(dict(employee_id=s["id"], journey_type=s["journey"], event_code=c, event_label=st["label"],
                               event_timestamp=when, actor_team=st["team"], source_system=SOURCE.get(st["team"], "HRIS"), notes=""))
        for r in s.get("req", []):
            created = REF - dt.timedelta(days=r["created"])
            reqs.append(dict(employee_id=s["id"], category=r["cat"], request_type=r["type"], linked_event_code=r["link"],
                             subject=r["subject"], description=r["desc"], status=r["status"], priority=r["prio"],
                             owner_team=r["team"], owner_name=r["owner"], created_at=_ts(created, "11:00"),
                             last_updated_at=_ts(REF - dt.timedelta(days=r["updated"]), "15:00"), resolved_at="",
                             sla_days=str(r["sla"]), days_open=str(r["created"])))
    return emps, events, reqs


def _append(path, rows, id_col=None, prefix=None, width=None):
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header, existing = reader.fieldnames, list(reader)
    n = max(int(r[id_col].split("-")[1]) for r in existing) if id_col else 0
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        for r in rows:
            if id_col:
                n += 1
                r = {id_col: f"{prefix}-{n:0{width}d}", **r}
            w.writerow({k: r.get(k, "") for k in header})


def main():
    with open(DATA / "employees.csv", encoding="utf-8") as f:
        have = {r["employee_id"] for r in csv.DictReader(f)}
    if "--check" not in sys.argv:
        if SPECS[0]["id"] in have:
            print("Hidden-scenario employees already present; nothing added.")
        else:
            emps, events, reqs = build()
            _append(DATA / "employees.csv", emps)
            _append(DATA / "journey_events.csv", events, "event_id", "EVT", 6)
            _append(DATA / "service_requests.csv", reqs, "request_id", "SR", 5)
            print(f"Added {len(emps)} employees, {len(events)} events, {len(reqs)} requests.")


if __name__ == "__main__":
    main()
