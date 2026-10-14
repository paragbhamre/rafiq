"""Reads a pack's scenarios.md: test cases with an employee, the prompt they type and the expected behaviour.

Used to choose the demo accounts and their suggested first questions, and by the compatibility report
to run every scenario prompt through Rafiq. Column names are matched loosely ("ID", "Employee",
"Prompt", "Expected", "Route"), so a pack that words its table differently still works.
"""
import re

from .journeymap import _cells, _col, _tables

QUOTE_RE = re.compile(r"[\"“]([^\"”]{3,})[\"”]")


def parse(text, employee_ids):
    ids = set(employee_ids)
    id_re = re.compile(r"\b[A-Z]{1,6}[-_]?\d{2,8}\b")
    out = []
    for heading, header, rows in _tables(text):
        c_emp = _col(header, "employee", "persona", "staff")
        c_prompt = _col(header, "prompt", "question", "message", "utterance", "says")
        if c_emp is None or c_prompt is None:
            continue
        c_id = _col(header, "id", "#", "scenario")
        c_exp = _col(header, "expected", "behaviour", "behavior", "outcome")
        c_route = _col(header, "route", "escalat", "owner")
        c_sit = _col(header, "situation", "context")
        for r in rows:
            g = lambda k: r[k] if k is not None and k < len(r) else ""  # noqa: E731
            emp = next((t for t in id_re.findall(g(c_emp)) if t in ids), None)
            if not emp:
                continue
            raw = g(c_prompt)
            quoted = QUOTE_RE.findall(raw)
            prompt = quoted[0] if quoted else raw.strip().strip('"')
            out.append(dict(id=g(c_id) or f"#{len(out) + 1}", employee_id=emp, prompt=prompt,
                            situation=g(c_sit), expected=g(c_exp), route=g(c_route), section=heading))
    return out
