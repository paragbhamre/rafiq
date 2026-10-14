# Swapping in the official data pack

Rafiq runs on the synthetic pack in `data/` by default. When the organisers publish their pack, this is the
path to running on it, usually 1–2 hours. Nothing here sends the pack anywhere: the checks run locally and offline.

## 1. Put the files in `packs/official/`

```
packs/official/
  employees.csv  journey_events.csv  service_requests.csv  pulse_feedback.csv
  journey_maps.md  scenarios.md  policies/*.md
  mapping.json   (only if names differ, see step 3)
  pack.json      (optional: {"as_of": "YYYY-MM-DD"}, the "today" the pack was built for)
```

Policies must be markdown. Convert PDF or Word policies first and keep their section numbers
(`## 1. Heading` and `1.1 rule text`). Policies without numbering still load, cited by paragraph.

## 2. Run the compatibility report

```bash
python tools/ingest.py packs/official --out packs/official/compatibility_report.md
```

It checks every file, column and value; reads the journeys, stages and named owners from `journey_maps.md`;
matches every policy rule Rafiq relies on to the official policies (same text, renumbered, or by meaning);
evaluates every employee; and runs each prompt in the pack's `scenarios.md` through Rafiq. Verdicts:

| Exit | Verdict | Meaning |
|---|---|---|
| 0 | READY | Runs as is |
| 1 | READY WITH WARNINGS | Runs; read the warnings (e.g. rules matched by meaning: confirm each one) |
| 2 | BLOCKED | Fix the listed blockers, usually with `mapping.json`, and run again |

## 3. Renames go in `mapping.json`, not in code

Start from `packs/mapping.example.json`. Keys under `columns` are the pack's names, values are Rafiq's.
Value maps (e.g. `NEW_JOINER` → `ONBOARDING`) are keyed by Rafiq's column names. Booleans (Yes/No, Y/N, 1/0)
and dates (YYYY-MM-DD, DD/MM/YYYY, …) are normalised automatically.

## 4. Test on the official pack

```bash
RAFIQ_PACK=official python -m pytest -q          # pack-independent checks run; synthetic scenarios are skipped
RAFIQ_PACK=official uvicorn app.main:app          # click through it locally
```

## 5. Switch the live site

Set `RAFIQ_PACK=official` (and `RAFIQ_AS_OF` if the pack has no `pack.json`) on the Render service, then
sign in as `admin` and reset the demo. To switch back, set `RAFIQ_PACK=synthetic`.

If the official pack can't load, the app refuses to start with the reason (it never runs on half-read data),
the deploy fails its health check, and the previous version stays live.

**Data handling.** Commit the official pack only if the challenge terms allow it in a private repository.
The repository for this prototype is private. Rafiq sends the AI writer only the facts needed for each
answer; use an AI provider whose terms exclude training on and retention of that data.

## What adapts automatically

| Area | How |
|---|---|
| Files, columns, values | `mapping.json`; booleans and dates normalised |
| Journey steps, target days, grace, prerequisites, owner teams | Read from the pack's `journey_maps.md` tables |
| Stages and named escalation owners | Read from `journey_maps.md` |
| Policy citations in answers, cases and the interface | Each rule Rafiq uses is found in the official policies by its text: unchanged, renumbered, or the closest match by meaning; rules with no close match are left out and listed in the report |
| Built-in figures (allowance amounts) | Stated only if the official rule's text is unchanged; otherwise Rafiq quotes the policy |
| Demo accounts and suggested questions | The people and prompts in the pack's `scenarios.md`; otherwise chosen from the journeys (friction, a move, Arabic, consent withdrawn, on track) |
| Steps new to Rafiq | Status, owners, escalation and related policy sections work; no one-click service request until added to `STEP_ACTIONS` |
| Tests | `tests/test_any_pack.py` runs on any pack; `tests/test_scenarios.py` is synthetic-only |

## Rehearsal

`python tools/make_test_pack.py runtime/altered-pack` builds a pack that differs from ours in every way
above (renamed files, columns and values, new IDs, renamed, renumbered and reworded policies, a changed
allowance figure, a different named owner). `tests/test_pack_kit.py` checks Rafiq adapts to it on every build.
