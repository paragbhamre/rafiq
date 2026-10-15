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
