"""Reading a data pack's tables with optional renames (mapping.json). No app state is created here,
so the compatibility report can use it on a pack that doesn't load yet."""
import csv
import json
from pathlib import Path

from . import config, schema


def read_mapping(pack_dir=None):
    """Optional renames for an official pack: files, columns and values (see packs/README.md)."""
    path = Path(pack_dir or config.DATA_DIR) / "mapping.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_table(logical, pack_dir=None, mapping=None):
    """Read one pack table and normalise it to Rafiq's schema.

    Returns (rows, issues). Issues are dicts(level=BLOCKER|WARN|INFO, msg=...). The loader never
    guesses silently: every rename, default and unreadable value is reported.
    """
    pack_dir = Path(pack_dir or config.DATA_DIR)
    mapping = read_mapping(pack_dir) if mapping is None else mapping
    issues = []
    fname = mapping.get("files", {}).get(logical, schema.FILES[logical])
    path = pack_dir / fname
    if not path.exists():
        lvl = "WARN" if logical == "pulse" else "BLOCKER"
        issues.append(dict(level=lvl, msg=f"{fname}: file not found"))
        return [], issues
    with open(path, encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))
    colmap = mapping.get("columns", {}).get(logical, {})
    header = list(raw[0].keys()) if raw else []
    renamed = {src: colmap.get(src, src) for src in header}
    present = set(renamed.values())
    for src, dst in renamed.items():
        if src != dst:
            issues.append(dict(level="INFO", msg=f"{fname}: column '{src}' mapped to '{dst}'"))
    missing_req = [c for c in schema.REQUIRED[logical] if c not in present]
    for c in missing_req:
        issues.append(dict(level="BLOCKER", msg=f"{fname}: required column '{c}' missing"))
    for c, d in schema.OPTIONAL[logical].items():
        if c not in present:
            issues.append(dict(level="INFO", msg=f"{fname}: optional column '{c}' absent, using default '{d}'"))
    known = set(schema.REQUIRED[logical]) | set(schema.OPTIONAL[logical])
    extra = sorted(present - known)
    if extra:
        issues.append(dict(level="INFO", msg=f"{fname}: extra columns kept but unused: {', '.join(extra)}"))
    valmap = mapping.get("values", {}).get(logical, {})
    rows, bad_dates, bad_bools, bad_enums = [], {}, {}, {}
    for r in raw:
        row = {renamed[k]: (v or "").strip() for k, v in r.items() if k is not None}
        for c, d in schema.OPTIONAL[logical].items():
            row.setdefault(c, d)
        for col, vm in valmap.items():
            if col in row and row[col] in vm:
                row[col] = vm[row[col]]
        for col in schema.BOOLEAN.get(logical, []):
            b = schema.norm_bool(row.get(col))
            if b is None:
                bad_bools.setdefault(col, set()).add(row.get(col))
                b = "false"
            row[col] = b
        for col in schema.DATES.get(logical, []):
            if row.get(col):
                d = schema.norm_date(row[col], with_time=col.endswith(("_at", "timestamp")))
                if d is None:
                    bad_dates.setdefault(col, set()).add(row[col])
                else:
                    row[col] = d
        for col, allowed in schema.ENUMS.get(logical, {}).items():
            if col in row and row[col] not in allowed:
                up = row[col].upper() if col != "preferred_language" else row[col].lower()
                if up in allowed:
                    row[col] = up
                else:
                    bad_enums.setdefault(col, set()).add(row[col])
        rows.append(row)
    for col, vals in bad_bools.items():
        issues.append(dict(level="WARN", msg=f"{fname}: '{col}' has values that aren't true/false, read as false: {sorted(vals)[:5]}"))
    for col, vals in bad_dates.items():
        issues.append(dict(level="BLOCKER" if col in schema.REQUIRED[logical] else "WARN",
                           msg=f"{fname}: '{col}' has dates that can't be read: {sorted(vals)[:5]}"))
    for col, vals in bad_enums.items():
        lvl = "BLOCKER" if (logical, col) in schema.BLOCKING_ENUMS else "WARN"
        issues.append(dict(level=lvl, msg=f"{fname}: '{col}' has unexpected values {sorted(vals)[:6]}; "
                                          f"add them to mapping.json values (expected {sorted(schema.ENUMS[logical][col])})"))
    return rows, issues


