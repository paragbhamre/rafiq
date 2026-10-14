# Journey Maps — Onboarding & Internal Mobility

> **SYNTHETIC / MOCK DATA.** Created by APEX Partners as a stand-in for the official challenge pack, which had not been published at build time. The column names follow the challenge brief. Steps, owners and targets are illustrative and are **not** real Emirates processes.

## How to read these maps

- **Day 0 (onboarding)** = the employee's joining date (`employees.journey_anchor_date`). Negative days are pre-arrival.
- **Day 0 (internal mobility)** = the date the move was requested (`employees.journey_anchor_date`). The move becomes effective on **Day 30** (`employees.move_effective_date`).
- **Target day** = the latest day by which the step should be complete.
- **Grace (days)** = the tolerance after the target day before the step counts as **stalled**. Between the target day and the end of grace it is **at risk**.
- **Applies when** = the step only exists for employees meeting that condition. Fields come from `employees.csv`.
- **Event code** = the value written to `journey_events.event_code` when the step completes.
- **Escalation owner** = the named role who receives a human handoff when the step stalls.

Every step listed here is a candidate for a hidden test scenario. The rules engine should evaluate all of them, not just the demo cases.

---

## Journey A — Onboarding (new joiner)

| # | Event code | Step | Owner team | Owner role | Target day | Grace (days) | Applies when | Prerequisite | Escalation owner |
|---|---|---|---|---|---|---|---|---|---|
| A1 | `OFFER_ACCEPTED` | Offer accepted | Talent Acquisition | Recruiter | -45 | 0 | always | — | Recruiter |
| A2 | `BACKGROUND_CHECK_CLEARED` | Background and reference check cleared | Talent Acquisition | Recruiter | -30 | 5 | always | A1 | Recruiter |
| A3 | `VISA_APPLICATION_SUBMITTED` | Employment visa application submitted | Government Relations (PRO) | PRO Officer | -28 | 3 | `visa_required = true` | A2 | PRO Team Lead |
| A4 | `MEDICAL_COMPLETED` | Visa medical fitness test completed | Government Relations (PRO) | PRO Officer | -18 | 3 | `visa_required = true` | A3 | PRO Team Lead |
| A5 | `VISA_ISSUED` | Entry or employment visa issued | Government Relations (PRO) | PRO Officer | -10 | 2 | `visa_required = true` | A4 | PRO Team Lead |
| A6 | `JOINING_TICKET_ISSUED` | Joining flight ticket issued | HR Operations | HR Officer | -7 | 2 | `relocating_from_abroad = true` | A5 (if visa) else A2 | HR Business Partner |
| A7 | `ACCOMMODATION_ASSIGNED` | Staff accommodation or temporary housing assigned | Facilities | Accommodation Coordinator | -5 | 2 | `accommodation_eligible = true` | A2 | Facilities Manager |
| A8 | `IT_KIT_ISSUED` | Laptop and phone issued | IT Service Desk | IT Onboarding Analyst | 1 | 1 | always | A2 | IT Service Delivery Manager |
| A9 | `SYSTEM_ACCESS_GRANTED` | Network, email and core system access granted | IT Service Desk | IT Onboarding Analyst | 2 | 1 | always | A8 | IT Service Delivery Manager |
| A10 | `STAFF_ID_ISSUED` | Staff ID and airside or building pass issued | Security | Pass Office | 3 | 2 | always | A2 | Security Duty Manager |
| A11 | `BUDDY_ASSIGNED` | Onboarding buddy assigned | Line Management | Line Manager | 1 | 2 | always | — | HR Business Partner |
| A12 | `EMIRATES_ID_APPLIED` | Emirates ID and residency stamping applied | Government Relations (PRO) | PRO Officer | 7 | 3 | `visa_required = true` | A5 | PRO Team Lead |
| A13 | `INDUCTION_COMPLETED` | Corporate induction attended | Learning & Development | L&D Coordinator | 5 | 2 | always | A9 | L&D Manager |
| A14 | `MANDATORY_TRAINING_BOOKED` | Mandatory compliance training booked | Learning & Development | L&D Coordinator | 7 | 3 | always | A13 | L&D Manager |
| A15 | `PROBATION_OBJECTIVES_SET` | Probation objectives agreed with manager | Line Management | Line Manager | 30 | 5 | always | — | HR Business Partner |
| A16 | `CHECKIN_30_DONE` | 30-day check-in completed | HR Business Partnering | HR Business Partner | 30 | 5 | always | — | HR Business Partner |

### Onboarding stages (`employees.journey_stage`)

| Stage | Day window | Meaning |
|---|---|---|
| `PRE_ARRIVAL` | Day -60 to -1 | Offer accepted, joining preparations in progress |
| `FIRST_WEEK` | Day 0 to 6 | Joined; kit, access, ID, induction |
| `FIRST_MONTH` | Day 7 to 30 | Training, objectives, 30-day check-in |
| `SETTLING_IN` | Day 31 to 90 | Post check-in, until probation review |

---

## Journey B — Internal mobility (new role, team or location)

`move_type` is one of `ROLE_CHANGE` (same location), `TEAM_CHANGE` (same location), `LOCATION_DOMESTIC` (a different UAE site), or `LOCATION_INTERNATIONAL` (an outstation abroad).

| # | Event code | Step | Owner team | Owner role | Target day | Grace (days) | Applies when | Prerequisite | Escalation owner |
|---|---|---|---|---|---|---|---|---|---|
| B1 | `MOVE_REQUESTED` | Move requested or offered | HR Business Partnering | HR Business Partner | 0 | 0 | always | — | HR Business Partner |
| B2 | `RECEIVING_MANAGER_ENDORSED` | Receiving manager endorsement | Line Management | Receiving Manager | 5 | 2 | always | B1 | HR Business Partner |
| B3 | `RELEASING_MANAGER_RELEASED` | Releasing manager agrees release date | Line Management | Releasing Manager | 7 | 3 | always | B1 | HR Business Partner |
| B4 | `TRANSFER_APPROVED` | Transfer approved by HR | HR Operations | HR Officer | 12 | 3 | always | B2, B3 | HR Business Partner |
| B5 | `TRANSFER_LETTER_ISSUED` | Transfer letter issued with new terms | HR Operations | HR Officer | 14 | 2 | always | B4 | HR Business Partner |
| B6 | `RELOCATION_ASSESSED` | Relocation package assessed | Global Mobility | Mobility Specialist | 16 | 3 | `move_type in (LOCATION_DOMESTIC, LOCATION_INTERNATIONAL)` | B4 | Global Mobility Lead |
| B7 | `WORK_PERMIT_ISSUED` | Destination work permit or visa issued | Global Mobility | Mobility Specialist | 26 | 3 | `move_type = LOCATION_INTERNATIONAL` | B6 | Global Mobility Lead |
| B8 | `RELOCATION_ALLOWANCE_PAID` | Relocation allowance paid | Payroll | Payroll Officer | 25 | 3 | `move_type in (LOCATION_DOMESTIC, LOCATION_INTERNATIONAL)` | B6 | Payroll Manager |
| B9 | `HOUSING_ARRANGED` | Housing at new location arranged | Facilities / Global Mobility | Accommodation Coordinator | 27 | 2 | `move_type in (LOCATION_DOMESTIC, LOCATION_INTERNATIONAL)` | B6 | Facilities Manager |
| B10 | `HANDOVER_COMPLETED` | Handover of current role completed | Line Management | Releasing Manager | 29 | 2 | always | B3 | HR Business Partner |
| B11 | `ACCESS_TRANSFERRED` | Systems access switched to new role | IT Service Desk | IT Access Analyst | 30 | 1 | always | B4 | IT Service Delivery Manager |
| B12 | `MOVE_EFFECTIVE` | Move effective, employee starts new role | HR Operations | HR Officer | 30 | 0 | always | B5; B7 for international moves | HR Business Partner |
| B13 | `ROLE_TRAINING_BOOKED` | Role-specific training booked | Learning & Development | L&D Coordinator | 40 | 3 | always | B12 | L&D Manager |
| B14 | `CHECKIN_30_DONE` | 30-day check-in in new role | HR Business Partnering | HR Business Partner | 60 | 5 | always | B12 | HR Business Partner |

### Mobility stages (`employees.journey_stage`)

| Stage | Day window | Meaning |
|---|---|---|
| `MOVE_REQUESTED` | Day 0 to 4 | Request raised, endorsements pending |
| `APPROVALS` | Day 5 to 14 | Approvals and transfer letter |
| `PRE_MOVE` | Day 15 to 29 | Relocation, permits, handover, access |
| `IN_NEW_ROLE` | Day 30 to 60 | Started in new role, until 30-day check-in |

---

## Friction signals the companion should detect

| Signal | Rule | Default severity |
|---|---|---|
| Step at risk | Past target day, within grace | Amber |
| Step stalled | Past target day plus grace, not complete | Red |
| Blocking stall | An at-risk or stalled step is a prerequisite of a step due within 7 days (for example, a visa not issued with the joining date 9 days away) | Red, escalate |
| Request ageing | `service_requests.days_open > sla_days` and status not resolved or closed | Amber; Red if over 2× SLA |
| Request bounced | Status `PENDING_INFO` for more than 3 days | Amber |
| Pulse low score | Opt-in pulse score of 2 or lower in the last 14 days | Amber (employee-facing check-in only) |
| Compound friction | Two or more Amber signals at once, or one Red plus a low pulse score | Red, offer HRBP handoff |

**Consent rule:** pulse signals are used only where `pulse_feedback.consent_status = ACTIVE` at evaluation time. Responses with `WITHDRAWN` consent must be ignored and must not be shown to anyone except the employee.

## Escalation contacts (synthetic)

| Escalation owner | Named contact | Channel |
|---|---|---|
| PRO Team Lead | Khalid Al Mansoori | pro.escalations@example.test |
| IT Service Delivery Manager | Priya Raman | it.delivery@example.test |
| Facilities Manager | Omar Haddad | facilities.mgr@example.test |
| Global Mobility Lead | Sarah Whitfield | mobility.lead@example.test |
| Payroll Manager | Fatima Al Zarooni | payroll.mgr@example.test |
| L&D Manager | Daniel Okafor | ld.mgr@example.test |
| Security Duty Manager | Rashid Al Ketbi | security.duty@example.test |
| Recruiter | Assigned per employee | ta@example.test |
| HR Business Partner | Assigned per employee (`employees.hrbp_name`) | hrbp@example.test |
