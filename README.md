# Rafiq — Employee Journey Companion (prototype v1)

Prototype for **The Employee Journey Companion Challenge** (Emirates, on Ignyte). Built by APEX Partners.

Rafiq (رفيق, "companion") gives every new or moving employee one place to ask, get cited policy answers, start routine requests, and see what happens next. It spots friction early from journey events and request delays, and routes issues to a **named human owner** before they escalate.

> **Synthetic data only.** `data/` holds a mock pack that follows the brief's schema. The official pack had not been published at build time. No real employee data is used or required.

---

## Hosted demo

**Live:** https://rafiq-journey-companion.onrender.com

**Sign-in.** Every person has their own account: 220 employees, 30 managers, 6 HR partners and 8 service owners (including the Talent Acquisition Lead, `owner.reem.alhashimi`), plus a demo admin. The sign-in page lists the accounts set up for the test scenarios. Usernames look like `aisha.rahman`, `mgr.hassan.brown`, `hr.nadia.farouk` and `owner.priya.raman`; IDs such as `EMP-1001` also work. Passwords are set in Render (`RAFIQ_DEMO_PASSWORD`, `RAFIQ_ADMIN_PASSWORD`) and are never in this repository. Set `RAFIQ_PASSWORD_MODE=per_user` to give every account a distinct password; the admin can then download the credentials sheet.

Identity comes only from a signed, HttpOnly, SameSite session cookie issued by the server (8-hour expiry). Writes require a same-origin request header, and repeated failed sign-ins lock out for 15 minutes. In a pilot, sign-in is replaced by single sign-on (Microsoft Entra ID / OIDC) with the same role rules.

Deployed on Render from this repository using `render.yaml` (Docker, Frankfurt region, health check `/api/health`). The build runs the full test suite, so a broken commit never replaces the live version, and every push to `main` redeploys automatically.

- The web service runs on Render **Starter** during judging, so it never sleeps and the first visit loads in about 2 seconds. (On the free plan it would sleep after 15 idle minutes and take about 50 seconds to wake.)
- **Data storage.** The synthetic pack is read-only files in `data/`. Everything created while using the app lives in **Render Postgres** (`rafiq-db`, Frankfurt, private network only, no public access): `requests`, `cases`, `consent_events` (append-only), `audit_log` (append-only), `notifications`, `conversations`, `request_priority` and `flags`. It survives sleeps and redeploys, and is safe with more than one instance (early warnings are seeded once, under a Postgres advisory lock). Locally, without `DATABASE_URL`, a JSON file is used instead.
- Demo data is shared by all accounts. Sign in as `admin` to reset it to the starting state.
- The optional AI writer is configured by environment variables in Render (see `.env.example`). Without them, or if the provider fails, Rafiq answers in offline mode automatically.

## Run it

**Docker (recommended)**
```bash
docker build -t rafiq .
docker run -p 8000:8000 rafiq                 # offline mode, no keys needed
# with the AI writer: pass the provider settings from .env.example
docker run -p 8000:8000 --env-file .env rafiq
```

**Local Python (3.11+)**
```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8000
python -m pytest -q          # everything: scenarios, responsible AI, workflow, views, AI writer, i18n, ops,
                             # pack swap rehearsal and the browser suite (run before every push)
python -m pytest -q -m "not slow"   # the fast subset the Render build runs (under a minute)
pip install playwright && python -m pytest -q -m slow tests/test_browser.py   # browser checks: RTL, phone width, keyboard, labels
DATABASE_URL=postgresql://user@host/db python -m pytest -q   # same suite against Postgres
```

Open http://localhost:8000 and sign in. Locally the demo password is `rafiq-demo`; set `RAFIQ_ADMIN_PASSWORD` to enable the `admin` account. Add `?lang=ar` for Arabic.

To reset the demo state, sign in as `admin` and use **Reset demo**.

**Dates.** Rafiq runs on today's date (Dubai time; set `RAFIQ_TZ` to change). The pack is written against a reference date (`RAFIQ_PACK_REFERENCE_DATE`, 2026-10-14 for the synthetic pack), and every date in it is moved forward to today when the app loads and again when the day changes. Each seeded journey therefore looks the same on any day, with real dates on screen. `RAFIQ_FREEZE_DATE` fixes "today" for rehearsals; `RAFIQ_SHIFT_PACK_DATES=false` evaluates the pack on its own dates.

---

## What it does (mapped to the brief)

| Brief requirement | How Rafiq does it |
|---|---|
| Knows the journey stage and what should happen next | A deterministic journey engine (`app/journey.py`) computes stage, day, the status of every step (done, late, stalled, waiting, upcoming) and next steps from `journey_events` against `journey_maps.md` targets. The employee sees it as a route ribbon and a timeline. |
| Answers policy questions, citing the source | Section-level policy index with stable citations (`POL-IT-001 §5.1`), searched locally with no external embeddings. Every policy statement carries its citation; tapping a citation opens the section. If nothing covers the question, Rafiq says it isn't sure and offers a handoff. |
| Completes or starts routine requests via other agents | Proposed actions route to service agents (IT, Learning & Development, Facilities, Government Relations, Payroll, Global Mobility, HR Operations, Security) with a complete, pre-filled request. The agents are simulated in `app/agents.py`; in a pilot each becomes an adapter to the real workflow. |
| Spots friction early | Rules for at-risk, stalled and blocking steps (a late step that holds up something due within 7 days), ageing requests (over SLA or over 2× SLA), bounced requests (waiting for information for more than 3 days), low pulse scores (opt-in only) and compound friction. |
| Escalates to the right human owner with a summary | Employee-confirmed handoffs, and system early warnings for red operational friction, open cases owned by a **named** person, with the HRBP copied, a summary, signals, policy references and a next-update date. |
| Nice to have: Arabic and English | Full right-to-left interface; replies in the language of the question. |
| Nice to have: manager view | Step progress only for the manager's own team. |
| Nice to have: where journeys stall | Heatmap by site or department, with groups under 10 people hidden. |

## Responsible AI and privacy (built in, and tested)

- **Works for the employee.** Only the employee can open their chat, journey or data. Managers get step progress for their own team only. A request for another person's data, monitoring, or rule-bypass is refused (tests A01–A02).
- **Opt-in sentiment.** Pulse feedback is used only while consent is active, and is never attached to a handoff unless the employee ticks the box in the confirmation dialog. Withdrawing consent takes effect immediately and schedules deletion.
- **"My data".** Shows everything held about the employee: consent state, check-in responses and whether each is used, signals flagged, what was shared with whom, and an access log. The employee can delete their conversation history.
- **Human in the loop.** Rafiq never approves, changes dates or decides. Every intervention goes to a named owner (test A03). Early warnings carry operational data only, never sentiment.
- **Grounded answers.** Routing and facts are deterministic. The optional LLM only rewrites the grounded draft, may cite only the sections it was given (invalid citations are stripped), and any provider failure falls back to the deterministic answer.
- **No performance use.** Stated in every HR view and in the policy layer. Cases carry the reminder.
- **Data handling.** Runs fully offline by default. When an LLM is enabled, only the minimum facts are sent, plus consented pulse data. Use a provider or enterprise endpoint whose terms exclude training on and retention of the data, as the challenge guardrail requires.

## Architecture

```
static/  (vanilla JS, no build)          app/
  Employee | Manager | HR | Owner          main.py       FastAPI routes + role-based access
  Insights | EN/AR RTL                     journey.py    stage, step status, friction signals (rules)
        │  signed session cookie            policies.py   section index + BM25 + Arabic glossary
        ▼  (SSO in a pilot)                 companion.py  guardrails → router → grounded draft
  /api/employee/{id}/chat ───────────────▶  llm.py        optional writer: any approved provider (configured by environment)
  /api/employee/{id}/actions ────────────▶  agents.py     service agents + named-owner cases
  /api/cases  /api/manager  /api/insights   data.py       read-only pack
  store.py      runtime state: PostgreSQL (DATABASE_URL) or local JSON
```

## Demo script (3 minutes)

Before recording: sign in as `admin` and **Reset demo**, then reload the page.

1. **Aisha, day 5, no laptop** (`aisha.rahman`, 0:15–1:05). Home shows the laptop step stalled and two steps waiting on it. In **Ask Rafiq**: "It's my first week and I still don't have a laptop. What do I do?" Rafiq names the root cause and what it holds up, cites the loan-device and training-extension rules, and offers actions. **Request a temporary loan device** previews the complete request before it is sent. **Escalate to Priya Raman** shows exactly what she will receive, what is not shared, and that it joins the case already open.
2. **The named owner** (`owner.priya.raman`, 1:05–1:30). One case for Aisha, marked not for performance use. Tick "the step itself is now complete" and **Mark resolved**: Aisha's journey updates and her IT request closes.
3. **Rafael, visa stalled, flying next week** (`rafael.santos`, 1:30–1:55). "Is my visa on track? I'm meant to fly next week." The medical is stalled and the visa at risk; Rafiq says not to book or travel yet and routes to the PRO Team Lead.
4. **Shamma in Arabic** (`shamma.alfalasi`, 1:55–2:15). Switch to العربية: "كم بدل السكن الخاص بي؟" The amount for her grade, in Arabic, with the citation.
5. **Privacy** (2:15–2:40). Hannah (`hannah.brown`): "If I tell you I'm struggling, will my manager see it? Will it affect my probation?" Then Andrei (`andrei.novak`) → **My data**: consent withdrawn, answers unused and due for deletion.
6. **Insights** (`hr.nadia.farouk`, 2:40–3:00). Where journeys stall, by site, with groups under 10 people hidden.

Fourteen seeded scenarios and their expected outcomes are listed in `data/scenarios.md`.

## Look and feel

All colours, fonts, radii and shadows live in one file, `static/theme.css`. The default theme is an airline-premium style (white header with a red rule, charcoal text, a deep red accent, gold detail, serif display headings that pair with Arabic). It is not an official brand of any airline: no logos, wordmarks or proprietary typefaces. To adopt an organisation's design system, replace the values in `theme.css` with its approved tokens; nothing else changes.

## Swapping in the official data pack

Rafiq reads the pack it is pointed at (`RAFIQ_PACK=synthetic|official|<folder>`) and adapts to it: renames go in a
`mapping.json`, journeys and named owners are read from the pack's `journey_maps.md`, policy rules are found in the
official policies by their text, and demo accounts come from the pack's `scenarios.md`. One command checks a pack
and lists anything that needs attention:

```bash
python tools/ingest.py packs/official
```

Full runbook: [`packs/README.md`](packs/README.md). A rehearsal pack that differs in every way
(`tools/make_test_pack.py`) is checked on every build.

## Path to a pilot (next quarter)

| Area | Prototype | Pilot |
|---|---|---|
| Identity | Per-person accounts, signed session cookies | Microsoft Entra ID SSO; roles from HR system groups |
| Data | CSV pack | Read-only feeds from HRIS, ITSM and LMS; events streamed nightly or near-real-time |
| Agents | Simulated | Adapters to ServiceNow, SuccessFactors or Workday, and the PRO and Payroll queues |
| LLM | Offline or any provider | An approved in-country or enterprise endpoint with no training or retention |
| Hosting | Single container plus managed Postgres | Containerised on the customer's cloud with Azure Database for PostgreSQL (same schema) |
| Governance | Built-in rules | DPO sign-off, a model card, quarterly bias and accuracy review, an employee feedback loop |
