"""Reads journey steps, stages and named escalation owners from a pack's journey_maps.md.

The official pack is expected to describe its journeys as markdown tables, like ours. When it
does, Rafiq follows the pack (steps, target days, grace, prerequisites, owners). Anything the
pack doesn't specify falls back to the built-in definitions in config.py, matched by event code
(for example Arabic labels and the policy sections a step relates to).

Pure functions, no app imports, so config.py can call it.
"""
import re

ROW_REF = re.compile(r"\b([A-Z]{1,2}\d{1,2})\b")
CODE_RE = re.compile(r"`?([A-Z][A-Z0-9_]{2,})`?")


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _tables(text):
    """Yield (heading, header_cells, rows) for each markdown table, with the nearest heading above it."""
    heading, lines = "", text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("#"):
            heading = ln.lstrip("#").strip()
        if ln.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|\s*:?-", lines[i + 1]):
            header = [h.lower() for h in _cells(ln)]
            rows, j = [], i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append(_cells(lines[j]))
                j += 1
            yield heading, header, rows
            i = j
            continue
        i += 1


def _col(header, *names):
    for n in names:
        for k, h in enumerate(header):
            if n in h:
                return k
    return None


def _journey_of(heading):
    h = heading.lower()
    if "onboard" in h or "joiner" in h or "new hire" in h:
        return "ONBOARDING"
    if "mobil" in h or "transfer" in h or "move" in h:
        return "MOBILITY"
    return None


def _num(s, default=0):
    m = re.search(r"-?\d+", s or "")
    return int(m.group()) if m else default


def _applies(s):
    s = (s or "").strip().strip("`").strip()
    if not s or s.lower() in ("always", "all", "—", "-", "n/a"):
        return None
    s = s.replace("`", "")
    m = re.match(r"^(\w+)\s*(?:=|==|is)\s*([\w-]+)$", s, re.I)
    if m:
        return (m.group(1), (m.group(2),))
    m = re.match(r"^(\w+)\s+in\s*\(([^)]*)\)$", s, re.I)
    if m:
        return (m.group(1), tuple(v.strip() for v in m.group(2).split(",") if v.strip()))
    return ("__unparsed__", (s,))


def _prereqs(s, ref_to_code):
    """'A5 (if visa) else A2' -> ['VISA_ISSUED|BACKGROUND_CHECK_CLEARED'];
    'B5; B7 for international moves' -> ['TRANSFER_LETTER_ISSUED', 'WORK_PERMIT_ISSUED|TRANSFER_LETTER_ISSUED']."""
    s = (s or "").strip()
    if not s or s in ("—", "-", "none", "None"):
        return []
    out, first = [], None
    for part in re.split(r"[;,]|\band\b", s):
        refs = [ref_to_code.get(r, r) for r in ROW_REF.findall(part)] or [c for c in CODE_RE.findall(part) if "_" in c]
        if not refs:
            continue
        if "else" in part or len(refs) > 1 and "or" in part:
            out.append("|".join(refs))
        elif re.search(r"\b(if|for|when|only)\b", part) and first:
            out.append(f"{refs[0]}|{first}")
        else:
            out.append(refs[0])
        first = first or refs[0]
    return out


def parse(text):
    """Return dict(steps={journey: [step...]}, stages={journey: [...]}, contacts={role: (name, channel)}, notes=[...])."""
    steps, stages, contacts, notes = {}, {}, {}, []
    for heading, header, rows in _tables(text):
        jt = _journey_of(heading)
        c_code = _col(header, "event code", "code")
        c_day = _col(header, "target day", "target")
        if c_code is not None and c_day is not None and jt:
            c_ref = _col(header, "#", "ref", "id")
            c_label = _col(header, "step", "label", "milestone")
            c_team = _col(header, "owner team", "team")
            c_role = _col(header, "owner role", "role")
            c_grace = _col(header, "grace")
            c_app = _col(header, "applies")
            c_pre = _col(header, "prereq", "depends")
            c_esc = _col(header, "escalation")
            ref_to_code = {}
            for r in rows:
                if c_ref is not None and c_ref != c_code and len(r) > c_code:
                    ref_to_code[r[c_ref]] = CODE_RE.search(r[c_code]).group(1) if CODE_RE.search(r[c_code]) else r[c_code]
            out = []
            for r in rows:
                if len(r) <= max(c_code, c_day):
                    continue
                m = CODE_RE.search(r[c_code])
                if not m:
                    continue
                g = lambda k: r[k] if k is not None and k < len(r) else ""  # noqa: E731
                out.append(dict(code=m.group(1), label=g(c_label) or m.group(1).replace("_", " ").capitalize(),
                                team=g(c_team), role=g(c_role), day=_num(g(c_day)), grace=_num(g(c_grace), 2),
                                applies=_applies(g(c_app)), prereqs=_prereqs(g(c_pre), ref_to_code),
                                esc=g(c_esc) or "HR Business Partner"))
            if out:
                steps.setdefault(jt, []).extend(out)
            continue
        c_stage = _col(header, "stage")
        c_win = _col(header, "day window", "window", "days")
        if c_stage is not None and c_win is not None and jt:
            st = []
            for r in rows:
                m = CODE_RE.search(r[c_stage]) if c_stage < len(r) else None
                nums = re.findall(r"-?\d+", r[c_win]) if c_win < len(r) else []
                if m and len(nums) >= 2:
                    st.append((m.group(1), int(nums[0]), int(nums[1])))
            if st:
                stages[jt] = st
            continue
        c_owner = _col(header, "escalation owner", "owner")
        c_name = _col(header, "named contact", "contact", "name")
        if c_owner is not None and c_name is not None and c_owner != c_name:
            c_ch = _col(header, "channel", "email")
            for r in rows:
                if max(c_owner, c_name) >= len(r):
                    continue
                name = r[c_name]
                if re.search(r"assigned per|per employee|varies", name, re.I):
                    continue
                contacts[r[c_owner]] = (name, r[c_ch] if c_ch is not None and c_ch < len(r) else "")
    for jt, lst in steps.items():
        bad = [s["code"] for s in lst if s["applies"] and s["applies"][0] == "__unparsed__"]
        if bad:
            notes.append(f"{jt}: 'applies when' not understood for {', '.join(bad)} (treated as always)")
            for s in lst:
                if s["applies"] and s["applies"][0] == "__unparsed__":
                    s["applies"] = None
    return dict(steps=steps, stages=stages, contacts=contacts, notes=notes)


def merge(parsed, base_steps, base_stages, base_contacts):
    """Pack wins where it specifies something; built-in definitions fill the gaps by event code."""
    steps = {}
    for jt in set(base_steps) | set(parsed["steps"]):
        base = {s["code"]: s for s in base_steps.get(jt, [])}
        if jt not in parsed["steps"]:
            steps[jt] = base_steps[jt]
            continue
        merged = []
        for p in parsed["steps"][jt]:
            b = base.get(p["code"], {})
            merged.append(dict(code=p["code"], label=p["label"] or b.get("label", p["code"]),
                               label_ar=b.get("label_ar") if b and b.get("label") == p["label"] else (b.get("label_ar") or p["label"]),
                               team=p["team"] or b.get("team", ""), role=p["role"] or b.get("role", ""),
                               day=p["day"], grace=p["grace"], applies=p["applies"], prereqs=p["prereqs"],
                               esc=p["esc"] or b.get("esc", "HR Business Partner"), policy=list(b.get("policy", []))))
        steps[jt] = merged
    stages = {}
    for jt in set(base_stages) | set(parsed["stages"]):
        if jt not in parsed["stages"]:
            stages[jt] = base_stages[jt]
            continue
        labels = {code: (en, ar) for code, _lo, _hi, en, ar in base_stages.get(jt, [])}
        lst = parsed["stages"][jt]
        out = []
        for k, (code, lo, hi) in enumerate(lst):
            en, ar = labels.get(code, (code.replace("_", " ").capitalize(),) * 2)
            out.append((code, -999 if k == 0 else lo, 9999 if k == len(lst) - 1 else hi, en, ar))
        stages[jt] = out
    contacts = dict(base_contacts) if not parsed["contacts"] else {**{k: v for k, v in base_contacts.items() if k == "Recruiter"}, **parsed["contacts"]}
    return steps, stages, contacts
