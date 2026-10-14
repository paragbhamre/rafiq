#!/usr/bin/env python3
"""Builds a deliberately *different* pack from the synthetic one, to prove Rafiq adapts to a new pack.

    python tools/make_test_pack.py runtime/altered-pack

Differences from data/ (each one is something an official pack might do):
  * column names: employee_id -> staff_id, journey_type -> journey, event_timestamp -> completed_on, ...
  * values: ONBOARDING -> NEW_JOINER, MOBILITY -> INTERNAL_MOVE, true/false -> Yes/No,
    IN_PROGRESS -> In Progress, consent ACTIVE/WITHDRAWN -> Granted/Revoked
  * dates as DD/MM/YYYY; employee IDs E1001 instead of EMP-1001
  * the IT policy renamed (POL-IT-001 -> ICT-POL-07) and its sections 4 and 5 swapped
  * a housing allowance figure changed (G5-G6 AED 9,000 -> 9,500)
  * two rules reworded (loan device, what a manager can see) and the privacy policy's sections renumbered
  * a different named IT escalation owner
  * optionally (--no-scenarios) no scenarios.md, so demo accounts must be chosen from the journeys
All renames are declared in mapping.json, which is what you'd write for the official pack.
"""
import csv
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data"

COLS = {
    "employees": {"employee_id": "staff_id", "journey_type": "journey", "journey_anchor_date": "start_or_request_date",
                  "hrbp_name": "hr_partner", "pulse_opt_in": "pulse_consent"},
    "events": {"employee_id": "staff_id", "event_timestamp": "completed_on"},
    "requests": {"employee_id": "staff_id", "status": "ticket_status"},
    "pulse": {"employee_id": "staff_id", "consent_status": "consent"},
}
VALUES = {
    "employees": {"journey_type": {"ONBOARDING": "NEW_JOINER", "MOBILITY": "INTERNAL_MOVE"}},
    "events": {},
    "requests": {"status": {"OPEN": "Open", "IN_PROGRESS": "In Progress", "PENDING_INFO": "Awaiting info",
                            "RESOLVED": "Resolved", "CLOSED": "Closed"}},
    "pulse": {"consent_status": {"ACTIVE": "Granted", "WITHDRAWN": "Revoked"}},
}
FILES = {"employees": "employees.csv", "events": "journey_events.csv", "requests": "service_requests.csv", "pulse": "pulse_feedback.csv"}
OUT_NAMES = {"employees": "staff.csv", "events": "journey_events.csv", "requests": "tickets.csv", "pulse": "pulse_feedback.csv"}
BOOLS = {"visa_required", "relocating_from_abroad", "accommodation_eligible", "pulse_opt_in"}


def new_id(s):
    return re.sub(r"\bEMP-(\d+)\b", r"E\1", s)


def main(out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    (out / "policies").mkdir(parents=True)
    for logical, fname in FILES.items():
        with open(SRC / fname, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        cols = COLS[logical]
        vals = VALUES[logical]
        header = [cols.get(c, c) for c in rows[0].keys()]
        with open(out / OUT_NAMES[logical], "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            for r in rows:
                row = []
                for c, v in r.items():
                    v = new_id(v or "")
                    if c in vals and v in vals[c]:
                        v = vals[c][v]
                    if c in BOOLS:
                        v = "Yes" if v == "true" else "No"
                    if c in ("journey_anchor_date", "move_effective_date") and v:
                        y, m, d = v.split("-")
                        v = f"{d}/{m}/{y}"
                    row.append(v)
                w.writerow(row)
    # policies
    for p in (SRC / "policies").glob("*.md"):
        text = p.read_text(encoding="utf-8")
        name = p.name
        if p.name.startswith("POL-IT-001"):
            text = text.replace("POL-IT-001", "ICT-POL-07")
            text = text.replace("## 4. Service levels", "## 5. Service levels").replace("## 5. While you wait", "## 4. While you wait")
            text = re.sub(r"^4\.(\d) ", r"X\1 ", text, flags=re.M)
            text = re.sub(r"^5\.(\d) ", r"4.\1 ", text, flags=re.M)
            text = re.sub(r"^X(\d) ", r"5.\1 ", text, flags=re.M)
            name = name.replace("POL-IT-001", "ICT-POL-07")
        if p.name.startswith("POL-IT-001"):
            text = text.replace("If your laptop is not issued by Day 1, the IT Service Desk can provide a temporary loan device within 4 working hours on request.",
                                "Where your laptop hasn't been issued by Day 1, ask the IT Service Desk for a temporary loan device; they provide one within 4 working hours.")
        if p.name.startswith("POL-PRV-001"):
            text = text.replace('Your manager can see the progress of your journey steps (for example, "IT kit issued"). Your manager cannot see',
                                'Managers see only how your journey steps are progressing, such as "IT kit issued". They never see')
            text = re.sub(r"^## (\d+)\.", lambda m: f"## {int(m.group(1)) + 10}.", text, flags=re.M)
            text = re.sub(r"^(\d+)\.(\d+) ", lambda m: f"{int(m.group(1)) + 10}.{m.group(2)} ", text, flags=re.M)
        if p.name.startswith("POL-ALW-001"):
            text = text.replace("G5–G6 AED 9,000", "G5–G6 AED 9,500")
        (out / "policies" / name).write_text(text, encoding="utf-8")
    jm = (SRC / "journey_maps.md").read_text(encoding="utf-8").replace("Priya Raman", "Grace Tan")
    (out / "journey_maps.md").write_text(jm, encoding="utf-8")
    if "--no-scenarios" not in sys.argv:
        sc = new_id((SRC / "scenarios.md").read_text(encoding="utf-8")).replace("Priya Raman", "Grace Tan")
        (out / "scenarios.md").write_text(sc, encoding="utf-8")
    mapping = {
        "files": {k: OUT_NAMES[k] for k in FILES if OUT_NAMES[k] != FILES[k]},
        "columns": {k: {new: old for old, new in v.items()} for k, v in COLS.items()},
        "values": {k: {col: {new: old for old, new in m.items()} for col, m in v.items()} for k, v in VALUES.items() if v},
    }
    # value maps are keyed by Rafiq's column names (applied after the column rename)
    (out / "mapping.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    print(f"Altered pack written to {out}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else ROOT / "runtime" / "altered-pack")
