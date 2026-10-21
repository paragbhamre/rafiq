#!/usr/bin/env python3
"""Compatibility report for a data pack.

    python tools/ingest.py packs/official            # check a folder
    python tools/ingest.py packs/official --out r.md # also save the report

Checks every file, column, value, journey step, named owner and policy section Rafiq relies on,
then dry-runs the journey engine and the companion on the pack (offline, no AI calls, nothing
leaves this machine). Exit code: 0 ready, 1 ready with warnings, 2 blocked.
"""
import argparse
import collections
import datetime as dt
import os
import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pack", help="folder holding the pack (employees.csv, journey_events.csv, ..., policies/)")
    ap.add_argument("--out", help="also write the report to this markdown file")
    ap.add_argument("--as-of", help="evaluate as of this date (default: pack.json, then inferred from the data)")
    args = ap.parse_args()
    pack_dir = Path(args.pack).resolve()
    if not pack_dir.is_dir():
        sys.exit(f"Not a folder: {pack_dir}")

    # Point the app at this pack before importing it; offline only, separate runtime state
    os.environ["RAFIQ_PACK"] = str(pack_dir)
    os.environ.pop("RAFIQ_DATA_DIR", None)
    os.environ["LLM_PROVIDER"] = "offline"
    os.environ.pop("DATABASE_URL", None)
    os.environ["RAFIQ_RUNTIME_DIR"] = str(ROOT / "runtime" / "ingest-check")
    sys.path.insert(0, str(ROOT))

    rep = Report(pack_dir)
    try:
        run(rep, pack_dir, args)
    except Exception:
        rep.blocker("Unexpected error while checking the pack:\n```\n" + traceback.format_exc()[-1500:] + "\n```")
    text = rep.render()
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    sys.exit(2 if rep.n["BLOCKER"] else 1 if rep.n["WARN"] else 0)


class Report:
    ICON = {"BLOCKER": "⛔", "WARN": "⚠️", "INFO": "·", "OK": "✅"}

    def __init__(self, pack_dir):
        self.pack_dir = pack_dir
        self.sections = []
        self.n = collections.Counter()

    def section(self, title):
        self.sections.append([title, []])

    def add(self, level, msg):
        self.n[level] += 1
        self.sections[-1][1].append(f"- {self.ICON[level]} {msg}")

    def blocker(self, msg):
        if not self.sections:
            self.section("Errors")
        self.add("BLOCKER", msg)

    def raw(self, text):
        self.sections[-1][1].append(text)

    def render(self):
        verdict = ("⛔ BLOCKED — fix the blockers below, then run this again" if self.n["BLOCKER"]
                   else "⚠️ READY WITH WARNINGS — Rafiq runs on this pack; review the warnings" if self.n["WARN"]
                   else "✅ READY — Rafiq runs on this pack")
        out = [f"# Rafiq compatibility report", "", f"**Pack:** `{self.pack_dir}`  ",
               f"**Checked:** {dt.datetime.now():%Y-%m-%d %H:%M}  ", f"**Verdict:** {verdict}  ",
               f"**Counts:** {self.n['BLOCKER']} blockers · {self.n['WARN']} warnings · {self.n['OK']} checks passed", ""]
        for title, lines in self.sections:
            out += [f"## {title}", ""] + lines + [""]
        return "\n".join(out)


def run(rep, pack_dir, args):
    from app import packio, schema

    # ---------------------------------------------------------------- 1. files and columns
    rep.section("1. Files and columns")
    mapping = packio.read_mapping(pack_dir)
    rep.add("INFO", f"mapping.json: {'used' if mapping else 'none (names as in the brief)'}")
    blocked = False
    counts = {}
    for logical in schema.FILES:
        rows, issues = packio.load_table(logical, pack_dir, mapping)
        counts[logical] = len(rows)
        fname = mapping.get("files", {}).get(logical, schema.FILES[logical])
        if rows:
            rep.add("OK", f"{fname}: {len(rows)} rows")
        for i in issues:
            if i["level"] == "INFO" and "absent, using default" in i["msg"]:
                continue
            rep.add(i["level"], i["msg"])
            blocked |= i["level"] == "BLOCKER"
    absent = [(logical, c) for logical in schema.FILES for c in schema.OPTIONAL[logical]
              if c not in _present_cols(packio, logical, pack_dir, mapping)]
    if absent:
        rep.add("INFO", "optional columns absent (defaults used): " + ", ".join(f"{schema.FILES[l]}:{c}" for l, c in absent[:12])
                + (" …" if len(absent) > 12 else ""))
    if blocked:
        rep.section("Next step")
        rep.raw("Add the renames to `mapping.json` in the pack folder (see `packs/README.md`) and run this again. "
                "The remaining checks need the files to load.")
        return

    # ---------------------------------------------------------------- 2. as-of date
    from app import config
    rep.section("2. Evaluation date")
    emps, _ = packio.load_table("employees", pack_dir, mapping)
    inferred = collections.Counter()
    for e in emps:
        if e.get("journey_day") and e.get("journey_anchor_date"):
            try:
                inferred[(dt.date.fromisoformat(e["journey_anchor_date"]) + dt.timedelta(days=int(e["journey_day"]))).isoformat()] += 1
            except ValueError:
                pass
    guess = inferred.most_common(1)[0][0] if inferred else None
    as_of = args.as_of or config.PACK_META.get("as_of") or guess
    if as_of:
        # Evaluate the pack on its own dates: reference date = as_of, no shift, "today" frozen at as_of
        os.environ["RAFIQ_PACK_REFERENCE_DATE"] = os.environ["RAFIQ_FREEZE_DATE"] = as_of
        config.PACK_REFERENCE_DATE = config.FREEZE_DATE = dt.date.fromisoformat(as_of)
    src = "--as-of" if args.as_of else "pack.json" if config.PACK_META.get("as_of") else "inferred from journey_day" if guess else "default"
    rep.add("OK" if as_of else "WARN", f"evaluating as of **{config.AS_OF}** ({src})"
            + ("" if as_of else ". Set it in pack.json: {\"as_of\": \"YYYY-MM-DD\"}"))
    if guess and as_of and guess != as_of:
        rep.add("WARN", f"the data's journey_day suggests {guess}; set RAFIQ_PACK_REFERENCE_DATE or pack.json to match")

    # ---------------------------------------------------------------- 3. journeys and owners
    rep.section("3. Journey steps and named owners (journey_maps.md)")
    jm = config.JOURNEY_MAP
    if jm["steps"]:
        for jt, lst in jm["steps"].items():
            built = {s["code"] for s in config.BUILTIN_STEPS.get(jt, [])}
            codes = [s["code"] for s in lst]
            new = [c for c in codes if c not in built]
            gone = [c for c in built if c not in codes]
            rep.add("OK", f"{jt}: {len(codes)} steps read from the pack")
            if new:
                rep.add("INFO", f"{jt}: steps new to Rafiq (status, owners and escalation work; no quick actions yet): {', '.join(new)}")
            if gone:
                rep.add("INFO", f"{jt}: built-in steps the pack doesn't have (ignored): {', '.join(gone)}")
    else:
        rep.add("WARN", "no journey step tables found in journey_maps.md; using Rafiq's built-in journeys")
    for jt in ("ONBOARDING", "MOBILITY"):
        rep.add("OK" if jt in jm["stages"] else "INFO", f"{jt} stages: " + (", ".join(c for c, *_ in config.STAGES[jt]) +
                (" (from the pack)" if jt in jm["stages"] else " (built-in)")))
    for note in jm["notes"]:
        rep.add("WARN", note)
    rep.add("OK" if jm["contacts"] else "WARN", f"named escalation owners: " + ", ".join(
        f"{role} → {name}" for role, (name, _ch) in config.ESCALATION_CONTACTS.items()))
    roles = {s["esc"] for lst in config.STEPS.values() for s in lst}
    unnamed = sorted(r for r in roles if r not in config.ESCALATION_CONTACTS and r != "HR Business Partner")
    if unnamed:
        rep.add("WARN", "escalation roles with no named person (handoffs would show the role only): " + ", ".join(unnamed))
    # prerequisites refer to real steps
    for jt, lst in config.STEPS.items():
        codes = {s["code"] for s in lst}
        for s in lst:
            for p in s["prereqs"]:
                for c in p.split("|"):
                    if c not in codes:
                        rep.add("WARN", f"{jt} {s['code']}: prerequisite '{c}' is not a step in this journey")

    # ---------------------------------------------------------------- 4. load the app on the pack
    rep.section("4. Data integrity")
    from app.data import pack
    known = set(pack.employees)
    for name, coll in (("journey_events.csv", pack.events), ("service_requests.csv", pack.requests), ("pulse_feedback.csv", pack.pulse)):
        orphans = [k for k in coll if k not in known]
        rep.add("WARN" if orphans else "OK", f"{name}: " + (f"{len(orphans)} employee IDs not in employees.csv: {orphans[:5]}" if orphans else "every row belongs to a known employee"))
    by_jt = collections.Counter(e["journey_type"] for e in pack.employees.values())
    rep.add("OK", "employees by journey: " + ", ".join(f"{k} {v}" for k, v in by_jt.items()))
    all_codes = {s["code"] for lst in config.STEPS.values() for s in lst}
    unknown = collections.Counter(ev["event_code"] for evs in pack.events.values() for ev in evs if ev["event_code"] not in all_codes)
    if unknown:
        rep.add("WARN", "event codes not in any journey (ignored): " + ", ".join(f"{c} ×{n}" for c, n in unknown.most_common(8)))
    else:
        rep.add("OK", "every event code matches a journey step")
    rep.add("OK", f"{len(pack.managers)} managers, {len(pack.hrbps)} HR partners")

    # ---------------------------------------------------------------- 5. policies
    rep.section("5. Policies and citations")
    from app.policies import library, reference, CITE_PATTERN
    rep.add("OK" if library.sections else "BLOCKER", f"{len(library.policies)} policies, {len(library.sections)} citable sections")
    if library.skipped:
        rep.add("WARN", "files in policies/ that aren't markdown (convert to .md so Rafiq can cite them): " + ", ".join(library.skipped))
    if library.fallback:
        rep.add("WARN", "policies without numbered sections, cited by paragraph number instead: " + ", ".join(library.fallback))
    refs = _rule_refs(config, CITE_PATTERN)
    if library is reference:
        missing = [r for r in refs if r not in library.by_cite]
        rep.add("OK" if not missing else "WARN", f"synthetic reference pack: {len(refs) - len(missing)}/{len(refs)} rule references exist"
                + (f"; missing {missing}" if missing else ""))
    else:
        res = {r: library.resolution(r) for r in refs}
        same = [r for r, x in res.items() if x[2] == "identical text" and x[0] == r]
        moved = [r for r, x in res.items() if x[2] == "identical text" and x[0] != r]
        meaning = [r for r, x in res.items() if x[2] == "matched by meaning"]
        none = [r for r, x in res.items() if x[0] is None]
        rep.add("OK", f"{len(refs)} policy rules Rafiq relies on: {len(same)} unchanged, {len(moved)} renamed or renumbered "
                      f"(same text), {len(meaning)} matched by meaning (text differs), {len(none)} not found")
        if moved or meaning:
            rep.raw("\n| Rule in Rafiq (synthetic ref) | Cited in this pack as | How | Similarity | Rule text in this pack |\n|---|---|---|---|---|")
            for r in sorted(meaning) + sorted(moved):
                c, sim, how = res[r]
                rep.raw(f"| {r} | {c} | {how if c == r or how != 'identical text' else 'renumbered'} | {sim:.2f} | {library.by_cite[c]['text'][:80]}… |")
            rep.raw("")
        if none:
            rep.add("WARN", "rules with no close match (Rafiq leaves these citations out): " + ", ".join(sorted(none)))
        figures = {"housing allowance by grade": ["POL-ALW-001 §2.2"], "transport allowance": ["POL-ALW-001 §3.1"],
                   "settling-in allowance": ["POL-ALW-001 §1.2"], "relocation allowance": ["POL-ALW-001 §4.1", "POL-ALW-001 §4.2"]}
        changed = [k for k, v in figures.items() if not library.same_text(*v)]
        if changed:
            rep.add("INFO", "amounts Rafiq has built in are not stated for: " + ", ".join(changed) +
                    " (their policy text differs, so Rafiq quotes the policy instead of giving a figure)")

    # ---------------------------------------------------------------- 6. dry run
    rep.section("6. Dry run on every employee (offline)")
    from app import companion, journey
    overall, sigs, fails = collections.Counter(), collections.Counter(), []
    for eid in pack.employees:
        try:
            ev = journey.evaluate(eid)
            overall[ev["overall"]] += 1
            for s in ev["signals"]:
                sigs[s["type"]] += 1
        except Exception as e:  # noqa: BLE001
            fails.append(f"{eid}: {type(e).__name__}: {e}")
    rep.add("BLOCKER" if fails else "OK", f"journey engine: {sum(overall.values())}/{len(pack.employees)} employees evaluated"
            + (f"; failures: {fails[:5]}" if fails else ""))
    rep.add("INFO", "journeys: " + ", ".join(f"{k} {v}" for k, v in overall.items()) + " · signals: " +
            ", ".join(f"{k} {v}" for k, v in sigs.most_common()))
    from app import auth
    rep.add("OK", f"demo accounts chosen: {len(auth.FEATURED)} — " + ", ".join(
        f"{pack.employees[i]['first_name']} {pack.employees[i]['last_name']} ({i})" for i in auth.FEATURED[:14]))
    chat_fail = []
    for eid in list(auth.FEATURED)[:14]:
        for q in auth.suggestions_for(eid)[:2] + ["What's next for me?", "Will my manager see my feedback?"]:
            try:
                r = companion.chat(eid, q)
                bad = [c["cite"] for c in r["citations"] if c["cite"] not in library.by_cite]
                if bad:
                    chat_fail.append(f"{eid} '{q}': unknown citations {bad}")
            except Exception as e:  # noqa: BLE001
                chat_fail.append(f"{eid} '{q}': {type(e).__name__}: {e}")
    rep.add("BLOCKER" if chat_fail else "OK", "companion answers for demo accounts" + (f": {chat_fail[:4]}" if chat_fail else ": all answered, every citation exists in this pack"))

    # ---------------------------------------------------------------- 7. the pack's own scenarios
    rep.section("7. The pack's test scenarios (scenarios.md)")
    from app import scenarios
    try:
        scen = scenarios.parse((pack_dir / "scenarios.md").read_text(encoding="utf-8"), pack.employees)
    except OSError:
        scen = []
    if not scen:
        rep.add("INFO", "no scenario table with employee IDs and prompts found; demo accounts were chosen from the journeys")
        return
    rep.add("OK", f"{len(scen)} scenarios read. Each prompt run through Rafiq (offline) below; compare with the expected behaviour.")
    rep.raw("\n| ID | Employee | Prompt | Rafiq's route | Actions offered | Citations | Expected (from the pack) |\n|---|---|---|---|---|---|---|")
    for sc in scen:
        try:
            r = companion.chat(sc["employee_id"], sc["prompt"])
            acts = "; ".join(a["label"] for a in r["actions"])[:120]
            cites = ", ".join(c["cite"] for c in r["citations"])[:80]
            route = r["intent"] + (" · refused" if r["refused"] else "") + (" · unsure" if r["unsure"] else "")
        except Exception as e:  # noqa: BLE001
            acts, cites, route = "", "", f"⛔ {type(e).__name__}"
            rep.n["BLOCKER"] += 1
        cell = lambda t: (t or "").replace("|", "/").replace("\n", " ")[:140]  # noqa: E731
        rep.raw(f"| {sc['id']} | {sc['employee_id']} | {cell(sc['prompt'])} | {route} | {cell(acts)} | {cites} | {cell(sc['expected'])} |")
    rep.raw("")


def _present_cols(packio, logical, pack_dir, mapping):
    return _header(packio, logical, pack_dir, mapping)


def _header(packio, logical, pack_dir, mapping):
    import csv
    from app import schema
    fname = mapping.get("files", {}).get(logical, schema.FILES[logical])
    try:
        with open(pack_dir / fname, encoding="utf-8-sig") as f:
            head = next(csv.reader(f))
    except (OSError, StopIteration):
        return set()
    colmap = mapping.get("columns", {}).get(logical, {})
    return {colmap.get(h, h) for h in head}


def _rule_refs(config, pattern):
    """Every policy rule Rafiq's code refers to (synthetic references)."""
    refs = set()
    for p in list((ROOT / "app").glob("*.py")) + [ROOT / "static" / "app.js"]:
        refs |= set(re.findall(pattern, p.read_text(encoding="utf-8")))
    for lst in config.BUILTIN_STEPS.values():
        for s in lst:
            refs |= set(s["policy"])
    for spec in config.REQUEST_TYPES.values():
        refs.add(spec["policy"])
    from app.policies import reference
    # only real rules (citations that exist in the synthetic reference pack), not mentions in comments
    return sorted(r for r in refs if not r.startswith("@") and r in reference.by_cite)


if __name__ == "__main__":
    main()
