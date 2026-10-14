# Rafiq — Employee Journey Companion (prototype v1)

Prototype for **The Employee Journey Companion Challenge** (Emirates, on Ignyte). Built by APEX Partners.

Rafiq (رفيق, "companion") gives every new or moving employee one place to ask, get cited policy answers, start routine requests, and see what happens next. It spots friction early from journey events and request delays, and routes issues to a **named human owner** before they escalate.

> **Synthetic data only.** `data/` holds a mock pack that follows the brief's schema. The official pack had not been published at build time. No real employee data is used or required.

---

## Hosted demo

**Live:** https://rafiq-journey-companion.onrender.com — open it and use **Start here** for the guided paths.

Deployed on Render from this repository using `render.yaml` (Docker, Frankfurt region, health check `/api/health`). The build runs the full test suite, so a broken commit never replaces the live version. Every push to `main` redeploys automatically.

- On the **free** plan the app sleeps after 15 minutes idle, and the first visit then takes about 50 seconds. Switch the plan to **Starter** during judging to keep it awake.
- Demo state (requests, cases, consent changes) is shared by everyone using the link and resets on each deploy. Use **Reset demo** in the banner to return to the starting state.
- To enable the AI writer, set `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` in Render, under Environment.

## Run it

**Docker (recommended)**
```bash
docker build -t rafiq .
docker run -p 8000:8000 rafiq                 # offline mode, no keys needed
# with Claude as the writer:
docker run -p 8000:8000 -e LLM_PROVIDER=anthropic -e ANTHROPIC_API_KEY=<key> rafiq
```

**Local Python (3.11+)**
```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8000
python -m pytest -q          # 26 scenario, privacy and guardrail tests
```

Open http://localhost:8000. Use the top bar to switch between **Employee, Manager, HR partner, Service owner, Insights**, and to switch language (English / العربية). Deep links work too, for example `/?role=employee&user=EMP-1001&lang=ar`.

To reset the demo state (raised requests, cases, consent changes), send `POST /api/admin/reset`.

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
        │  X-Rafiq-Role / User headers      policies.py   section index + BM25 + Arabic glossary
        ▼  (SSO claims in a pilot)          companion.py  guardrails → router → grounded draft
  /api/employee/{id}/chat ───────────────▶  llm.py        optional writer: Anthropic / OpenAI-compatible / Azure
  /api/employee/{id}/actions ────────────▶  agents.py     service agents + named-owner cases
  /api/cases  /api/manager  /api/insights   data.py       read-only pack + runtime state (JSON)
```

## Demo script (3 minutes)

1. **Aisha, Day 5, no laptop** (`EMP-1001`). Rafiq flags the stall and that it blocks access and induction. It cites the loan-device and training-extension rules. Tap **Request a temporary loan device** and the IT agent confirms. Tap **Escalate to Priya Raman** and the dialog shows exactly what will be shared.
2. **HR partner view** (Nadia Farouk). The handoff and the earlier early warning are in the inbox, with no sentiment attached. Acknowledge it, and the employee gets the update.
3. **Rafael, visa stalled, flying next week** (`EMP-1002`). This is a blocking stall within 14 days of joining. Rafiq routes to the PRO Team Lead and HRBP and reassures him: no travel without a permit, and the date only changes with his agreement.
4. **Shamma in Arabic** (`EMP-1007`). Housing allowance for her grade, answered in Arabic with citations.
5. **Privacy** (`EMP-1011`): "Will my manager see this?" Then open **My data** for Andrei (`EMP-1006`): his consent was withdrawn, so his responses are unused and due for deletion.
6. **Insights**: where journeys stall, by site, with small groups hidden.

Fourteen seeded scenarios and their expected outcomes are listed in `data/scenarios.md`.

## Swapping in the official data pack

1. Drop the official files into `data/` (same file names).
2. If column names differ, map them in `app/data.py` (the loader).
3. Update `STEPS` and `ESCALATION_CONTACTS` in `app/config.py` from the official `journey_maps.md`.
4. Run `python -m pytest -q`, then add tests for any new cases the official pack reveals.

## Path to a pilot (next quarter)

| Area | Prototype | Pilot |
|---|---|---|
| Identity | Demo role headers | Microsoft Entra ID SSO; roles from HR system groups |
| Data | CSV pack | Read-only feeds from HRIS, ITSM and LMS; events streamed nightly or near-real-time |
| Agents | Simulated | Adapters to ServiceNow, SuccessFactors or Workday, and the PRO and Payroll queues |
| LLM | Offline or any provider | An approved in-country or enterprise endpoint with no training or retention |
| Hosting | Single container | Containerised on the customer's cloud; state in a managed database |
| Governance | Built-in rules | DPO sign-off, a model card, quarterly bias and accuracy review, an employee feedback loop |
