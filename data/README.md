# Mock Data Pack — Employee Journey Companion Challenge (v1)

> **SYNTHETIC DATA ONLY.** Built by APEX Partners as a stand-in while the official challenge pack is pending. Every person, contact, policy and amount is fictional. File names and core columns follow the challenge brief, so the prototype can switch to the official pack by remapping columns.

**Reference date:** `2026-10-14`. The dates in these files describe the journeys as they stand on this day. Rafiq runs on today's date and moves every pack date forward by (today − reference date) when it loads, so each seeded journey (Aisha on Day 5, Rafael on Day −9, …) looks the same on any day. Set `RAFIQ_SHIFT_PACK_DATES=false` to evaluate the files on their own dates.

## Contents

| File | Rows | What it holds |
|---|---|---|
| `employees.csv` | 220 | 136 onboarding plus 84 internal mobility (EMP-1301 to EMP-1320 are the H01–H20 rehearsal cases); stage, manager, HRBP, location, eligibility flags, consent |
| `journey_events.csv` | ~1,850 | One row per completed journey step (event codes from `journey_maps.md`) plus a few informational events |
| `service_requests.csv` | ~145 | HR, IT, Facilities, PRO, Payroll, L&D, Security and Mobility requests with status, owner, SLA and days open |
| `pulse_feedback.csv` | ~120 | Opt-in pulse responses (English and Arabic); `consent_status` is ACTIVE or WITHDRAWN |
| `policies/` | 13 | Short, citable policy documents (`POL-xxx §n.n`) |
| `journey_maps.md` | — | Steps, owners, target days, grace periods, prerequisites, friction rules, escalation contacts |
| `scenarios.md` | 14 + 7 | Seeded test scenarios with expected routing, plus view and adversarial checks |
| `tools/generate_pack.py` | — | Deterministic generator (fixed seed); re-run to rebuild the CSVs |
| `tools/check_pack.py` | — | Integrity checks and the reference friction evaluator (the rules-engine spec in code) |

## Data dictionary

### employees.csv
| Column | Type | Notes |
|---|---|---|
| employee_id | string | `EMP-1001`–`EMP-1014` are seeded scenarios; the rest are random |
| first_name, last_name | string | Fictional |
| preferred_language | `en` / `ar` | Companion reply language |
| journey_type | `ONBOARDING` / `MOBILITY` | |
| journey_stage | enum | See the stage tables in `journey_maps.md` |
| journey_day | int | Days since `journey_anchor_date` on the reference date 2026-10-14 (negative = pre-arrival) |
| journey_anchor_date | date | Joining date (onboarding) or move request date (mobility) |
| move_effective_date | date | Mobility only; anchor plus 30 days |
| move_type | enum | `ROLE_CHANGE`, `TEAM_CHANGE`, `LOCATION_DOMESTIC`, `LOCATION_INTERNATIONAL` |
| department, role_title, grade, location | string | New or current values |
| from_location, from_department, from_role_title | string | Mobility only |
| manager_id, manager_name | string | Line manager (receiving manager for moves) |
| releasing_manager_name | string | Mobility only |
| hrbp_id, hrbp_name | string | Named HR Business Partner |
| visa_required | bool | False for UAE nationals |
| relocating_from_abroad | bool | Drives the joining-ticket step |
| accommodation_eligible | bool | Grades G1–G4 relocating from abroad |
| family_status | `SINGLE` / `FAMILY` | Drives baggage and allowance amounts |
| pulse_opt_in | bool | Current consent; must match `pulse_feedback.consent_status` |

### journey_events.csv
`event_id, employee_id, journey_type, event_code, event_label, event_timestamp (ISO, +04:00), actor_team, source_system, notes`. A step is complete when its `event_code` row exists. A missing row means not done.

### service_requests.csv
`request_id, employee_id, category, request_type, linked_event_code, subject, description, status (OPEN | IN_PROGRESS | PENDING_INFO | RESOLVED | CLOSED), priority, owner_team, owner_name, created_at, last_updated_at, resolved_at, sla_days, days_open`. In this mock, `days_open` is in **calendar days**, while SLAs in POL-SRV-001 are stated in working days. Keep this consistent in the engine, or switch both to working days.

### pulse_feedback.csv
`response_id, employee_id, submitted_at, journey_type, journey_stage, question_id, question_text, score (1–5), comment, language, consent_status (ACTIVE | WITHDRAWN)`.

## Known simplifications
- One move per employee; no employee is in both journeys.
- Grace periods and target days are calendar days.
- Prerequisites use "A|B" in the generator to mean "A if it applies to this employee, otherwise B".

## Swapping in the official pack
1. Map the official columns onto the names above (keep the code changes inside the adapter layer).
2. Rebuild the step table from the official `journey_maps.md`.
3. Re-run our scenario sheet against the official data and add any cases it reveals.
