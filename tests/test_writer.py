"""The AI writer must not repeat the options already shown as buttons under the reply."""
from app.llm import drop_button_echo

LABELS = ["Request a temporary loan device", "Escalate to Priya Raman (IT Service Delivery Manager)",
          "Ask my HR Business Partner (Nadia Farouk) to help"]


def test_option_list_that_repeats_the_buttons_is_removed():
    text = ("Nadia can pull things together.\n\nNothing has been sent yet. You can choose any of the options below:\n"
            "- Request a temporary loan device\n- Escalate to Priya Raman (IT Service Delivery Manager)\n- Ask Nadia Farouk to help")
    out = drop_button_echo(text, LABELS)
    assert "- " not in out and out.endswith("options below.")


def test_bullets_with_real_content_are_kept():
    text = ("- **Priya Raman (IT Service Delivery Manager):** the escalation you asked for.\n"
            "- The IT Service Desk can provide a temporary loan device within 4 working hours on request. [POL-IT-001 §5.1]")
    assert drop_button_echo(text, LABELS) == text


def test_arabic_echo_is_removed():
    out = drop_button_echo("يمكنك الاختيار:\n- طلب جهاز مؤقت", ["طلب جهاز مؤقت"])
    assert out == "يمكنك الاختيار."


def test_slow_writer_falls_back_to_the_grounded_draft_within_the_deadline(monkeypatch):
    # NFR-01 / DEF-019: a slow AI provider must not keep the employee waiting
    import time
    from app import companion, config, llm
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(config, "LLM_DEADLINE_S", 1.0)
    monkeypatch.setattr(llm, "_anthropic", lambda system, msgs: (time.sleep(5), "late text")[1])
    t0 = time.time()
    r = companion.chat("EMP-1001", "It's my first week and I still don't have a laptop. What do I do?")
    assert time.time() - t0 < 3
    assert r["mode"] == "offline_fallback" and "Laptop and phone issued" in r["reply"]


def test_writer_output_has_no_emoji():
    from app.llm import _formal
    assert _formal("Hi Shamma \U0001F60A\n\nYour allowance is AED 9,000.") == "Hi Shamma\n\nYour allowance is AED 9,000."
    assert _formal("مرحباً شمّة 😊") == "مرحباً شمّة"


def test_writer_is_told_when_a_handoff_already_exists():
    # S08-03: after escalating, the writer must not invite the employee to escalate again
    from app import agents, companion, llm
    from app.data import state
    from app.journey import evaluate
    state.reset()
    agents.escalate("EMP-1008", evaluate("EMP-1008"), "ACCOMMODATION_ASSIGNED")
    d, ev = companion.route("EMP-1008", "Where am I staying when I arrive on Friday?")
    _, _, journey, buttons = llm._context("EMP-1008", d, ev)
    assert any("Already handed to Omar Haddad" in x for x in journey["already_done"])
    assert not any("Omar Haddad" in b for b in buttons)


def test_follow_up_replies_are_not_re_greeted(monkeypatch):
    from app import companion, config, llm
    from app.data import state
    state.reset()
    seen = []
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(llm, "_anthropic", lambda system, msgs: (seen.append(system), "Dear Tariq,\n\nYour access step is late.")[1])
    monkeypatch.setattr(llm, "validate", lambda text, allowed, draft: text)
    first = companion.chat("EMP-1010", "I can't get into the DWC rostering system.")
    second = companion.chat("EMP-1010", "I'm locked out of the system I need at my new site.", thread_id=first["thread_id"])
    # the chat opens with Rafiq's own welcome, so no reply adds a salutation (not even the first)
    assert not first["reply"].startswith("Dear") and not second["reply"].startswith("Dear")
    assert "do NOT greet" in seen[0] and "do NOT greet" in seen[-1]


def test_arabic_reply_never_opens_in_english_and_sent_question_is_known(monkeypatch):
    from app import agents, companion, config, llm
    from app.data import state
    state.reset()
    agents.ask_human("EMP-1012", "Can I bring my cat?")
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(llm, "_anthropic", lambda system, msgs: "Dear Liam,\n\nلست متأكداً.")
    monkeypatch.setattr(llm, "validate", lambda text, allowed, draft: text)
    r = companion.chat("EMP-1012", "هل يمكنني إحضار قطتي على رحلة الالتحاق، وهل ستدفع الشركة تكاليفها؟")
    assert not r["reply"].startswith("Dear")
    d, ev = companion.route("EMP-1012", "هل يمكنني إحضار قطتي على رحلة الالتحاق؟")
    assert any("Already requested" in x for x in llm._context("EMP-1012", d, ev)[2]["already_done"])
