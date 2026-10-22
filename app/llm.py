"""Model-agnostic writer. Supports Anthropic (Messages API) and any OpenAI-compatible endpoint
(OpenAI, Azure OpenAI, or a gateway approved by the organisation).

The model only rewrites a grounded draft; it does not decide routing or take actions.
Only non-sensitive facts are sent, plus pulse data when the employee has opted in.
Use providers whose terms exclude training on and retention of submitted data.
"""
import concurrent.futures
import json
import logging
import re
import time

import httpx

from . import config
from .data import pack, usable_pulse
from .policies import library

log = logging.getLogger("rafiq.llm")
logging.basicConfig(level=logging.INFO)


class Truncated(Exception):
    """The provider stopped at its output limit; a partial reply is never shown."""

SYSTEM = """You are Rafiq, a secure employee journey companion. You work FOR the employee, never as a monitoring tool.
Rewrite the DRAFT into a clear, courteous, concise reply for the employee (max ~170 words, short paragraphs or bullets).
Strict rules:
- Use ONLY facts in DRAFT, JOURNEY and ALLOWED_POLICY_SECTIONS. Never invent dates, amounts, names, policies or outcomes.
- Every policy statement must carry its citation in square brackets exactly as given, e.g. [POL-IT-001 §5.1]. Only cite IDs from ALLOWED_POLICY_SECTIONS.
- If the draft says you are not sure, say plainly that you are not sure and offer the handoff. Do not answer from general knowledge.
- Do not promise outcomes. Do not say an action is done unless the draft says so; the employee confirms actions with the buttons shown under your reply.
- Do not list or repeat the options in BUTTONS SHOWN UNDER YOUR REPLY; the employee already sees them. At most say "use the buttons below".
- If JOURNEY.already_done lists a handoff or request, say it is already with that person (with the case number and next update)
  and do NOT invite the employee to escalate or request it again. If there are no buttons left, don't mention buttons.
- Never mention other employees, never reveal sentiment scores to anyone else, never suggest use in performance decisions.
- Tone: formal and professional, as in an official Emirates HR service; polite and empathetic without being casual.
  No emoji, no exclamation marks, no slang.
- Greeting: {greeting}
- Reply in {lang_name}. Keep names, request IDs and citations unchanged."""


def _context(emp_id, draft, ev):
    emp = pack.employees[emp_id]
    allowed = list(draft.cites)
    sections = [{"cite": c, "text": library.get(c)["text"], "heading": library.get(c)["heading"]} for c in allowed]
    journey = {
        "first_name": emp["first_name"], "role": emp["role_title"], "location": emp["location"],
        "journey": emp["journey_type"], "stage": ev["stage_label"], "day": ev["journey_day"],
        "steps_needing_attention": [{"step": s["label"], "status": s["status"], "days_late": s["days_late"],
                                     "owner": s["owner_team"]} for s in ev["steps"] if s["status"] in ("STALLED", "AT_RISK", "DUE_TODAY")],
        "next_steps": [{"step": s["label"], "target_date": s["target_date"]} for s in ev["next_steps"]],
        "manager": emp["manager_name"], "hrbp": emp["hrbp_name"],
    }
    if usable_pulse(emp_id):  # opt-in only
        journey["employee_checkins"] = [{"date": p["submitted_at"][:10], "score": p["score"]} for p in usable_pulse(emp_id)][-2:]
    from .agents import open_handoff, open_request
    from .companion import _fmt_date
    actions, done = [], []
    for a in draft.actions:
        c = open_handoff(emp_id, a["owner"]["name"]) if a["type"] == "ESCALATE" and a.get("owner") else None
        r = (open_request(emp_id, a.get("request_key")) if a["type"] == "RAISE_REQUEST"
             else open_request(emp_id, "HR_QUERY") if a["type"] == "ASK_HUMAN" else None)
        if c:
            done.append(f"Already handed to {a['owner']['name']} (case {c['case_id']}, next update {_fmt_date(c['next_update_due'], draft.lang == 'ar')})")
        elif r:
            done.append(f"Already requested: {a['label']} ({r['request_id']})")
        else:
            actions.append(a["label"])
    journey["already_done"] = done
    return allowed, sections, journey, actions


_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="writer")


_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\uFE0F]")


def _formal(text):
    """Backstop for the tone rule: strip emoji the writer may still add."""
    return re.sub(r"[ \t]{2,}", " ", _EMOJI.sub("", text)).replace(" \n", "\n").strip()


def rewrite(emp_id, msg, draft, ev, history=None):
    allowed, sections, journey, actions = _context(emp_id, draft, ev)
    lang_name = "Arabic (Modern Standard, formal)" if draft.lang == "ar" else "English (UK)"
    user = (f"EMPLOYEE MESSAGE:\n{msg}\n\nDRAFT (grounded, authoritative):\n" + "\n".join(draft.lines) +
            f"\n\nNOT_SURE: {draft.unsure}\nBUTTONS SHOWN UNDER YOUR REPLY: {json.dumps(actions, ensure_ascii=False)}"
            f"\n\nJOURNEY: {json.dumps(journey, ensure_ascii=False)}"
            f"\n\nALLOWED_POLICY_SECTIONS: {json.dumps(sections, ensure_ascii=False)}")
    msgs = []
    for h in (history or [])[-4:]:
        msgs.append({"role": "user" if h["role"] == "user" else "assistant", "content": h["text"][:800]})
    msgs.append({"role": "user", "content": user})
    ongoing = any(h["role"] != "user" for h in (history or []))
    greeting = ("This is a follow-up in an ongoing conversation: do NOT greet or address the employee by name "
                "(no 'Dear …', 'Hi …', 'Hello'); start directly with the answer." if ongoing else
                "This is the first reply in the conversation: you may open once with a salutation IN THE REPLY LANGUAGE "
                "(English: \"Dear <first name>,\"; Arabic: \"<first name>،\" with no English words).")
    system = SYSTEM.format(lang_name=lang_name, greeting=greeting)
    call = {"anthropic": _anthropic, "openai": _openai}.get(config.LLM_PROVIDER)
    if not call:
        return None
    # Hard deadline for the whole call: past it, the employee gets the grounded draft straight away.
    fut = _POOL.submit(call, system, msgs)
    try:
        text = fut.result(timeout=config.LLM_DEADLINE_S)
    except concurrent.futures.TimeoutError:
        log.warning("llm fallback: deadline %.0fs", config.LLM_DEADLINE_S)
        return None
    except Exception as exc:  # noqa: BLE001 - any provider failure falls back to the deterministic draft
        log.warning("llm fallback: %s", type(exc).__name__)
        return None
    if not text:
        return None
    out = validate(text, allowed, draft)
    if out and draft.lang == "ar":  # never an English salutation on an Arabic reply
        out = re.sub(r"^\s*(dear|hi|hello)\s+[^\n,،]{0,30}[,،]?\s*\n+", "", out, count=1, flags=re.I)
    if out and ongoing:
        out = re.sub(r"^\s*(dear|hi|hello)\b[^\n,]{0,40},?\s*\n+|^\s*(عزيزي|عزيزتي|مرحباً|مرحبا)[^\n،,]{0,40}[،,]?\s*\n+", "",
                     out, count=1, flags=re.I)
    return _formal(out) if out else out


_WORD = re.compile(r"\w+", re.U)


def _words(s):
    return {w.lower() for w in _WORD.findall(s) if len(w) > 1 or not w.isascii()}


def drop_button_echo(text, labels):
    """Remove bullet lines that only restate a button label (the buttons are shown under the reply)."""
    if not labels:
        return text
    lab = [_words(l) for l in labels]
    out, dropped = [], False
    for line in text.split("\n"):
        m = re.match(r"^\s*(?:[-*•]|\d+[.)])\s+(.*)$", line)
        if m:
            w = _words(re.sub(r"[*_`]", "", m.group(1)))
            if w and any(len(w & l) / len(w) >= 0.8 for l in lab):
                dropped = True
                continue
        out.append(line)
    if not dropped:
        return text
    # a lead-in that now introduces nothing ("...the options below:") ends with a full stop instead
    for i in range(len(out) - 1, -1, -1):
        if out[i].strip():
            if out[i].rstrip().endswith(":"):
                out[i] = out[i].rstrip()[:-1].rstrip() + "."
            break
    fixed = []
    for i, line in enumerate(out):
        nxt = next((x for x in out[i + 1:] if x.strip()), "")
        if line.rstrip().endswith(":") and not re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", nxt):
            line = line.rstrip()[:-1].rstrip() + "."
        fixed.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(fixed)).strip()


def validate(text, allowed, draft):
    """Drop citations that were not provided; re-attach sources if the model lost them."""
    text = drop_button_echo(text, [a["label"] for a in getattr(draft, "actions", [])])
    def fix(m):
        c = re.sub(r"\s*§\s*", " §", m.group(1).strip()).rstrip(".")
        return f"[{c}]" if c in allowed else ""
    text = re.sub(r"\[([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*\s*§\s*[\d.]+)\]", fix, text)
    cited = set(re.findall(r"\[([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)* §[\d.]+)\]", text))
    if allowed and not cited:
        text += "\n\n" + ("المصادر: " if draft.lang == "ar" else "Sources: ") + ", ".join(f"[{c}]" for c in allowed[:3])
    return text.strip()


def _anthropic(system, msgs):
    if not config.ANTHROPIC_API_KEY:
        return None
    t0 = time.time()
    r = httpx.post("https://api.anthropic.com/v1/messages", timeout=config.LLM_TIMEOUT_S,
                   headers={"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                            "content-type": "application/json"},
                   json={"model": config.ANTHROPIC_MODEL, "max_tokens": config.LLM_MAX_TOKENS,
                         "system": system, "messages": msgs})
    r.raise_for_status()
    body = r.json()
    usage = body.get("usage", {})
    # metadata only: never log message content
    log.info("llm anthropic stop=%s in=%s out=%s ms=%d", body.get("stop_reason"), usage.get("input_tokens"),
             usage.get("output_tokens"), (time.time() - t0) * 1000)
    if body.get("stop_reason") == "max_tokens":
        raise Truncated()
    return "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")


def _openai(system, msgs):
    if not config.OPENAI_API_KEY:
        return None
    if config.OPENAI_API_STYLE == "azure":
        # OPENAI_BASE_URL like https://<resource>.openai.azure.com/openai/deployments/<deployment>
        url = f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions?api-version=2024-10-21"
        headers = {"api-key": config.OPENAI_API_KEY}
    else:
        url = f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
    r = httpx.post(url, timeout=config.LLM_TIMEOUT_S, headers=headers,
                   json={"model": config.OPENAI_MODEL, "temperature": 0.2, "max_tokens": config.LLM_MAX_TOKENS,
                         "messages": [{"role": "system", "content": system}] + msgs})
    r.raise_for_status()
    choice = r.json()["choices"][0]
    if choice.get("finish_reason") == "length":
        raise Truncated()
    return choice["message"]["content"]


def status():
    configured = (config.LLM_PROVIDER == "anthropic" and bool(config.ANTHROPIC_API_KEY)) or \
                 (config.LLM_PROVIDER == "openai" and bool(config.OPENAI_API_KEY))
    model = config.ANTHROPIC_MODEL if config.LLM_PROVIDER == "anthropic" else config.OPENAI_MODEL if config.LLM_PROVIDER == "openai" else None
    return {"provider": config.LLM_PROVIDER, "model": model, "configured": configured}
