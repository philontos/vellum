from app.llm import client as llm


def test_tools_stripped_on_400_rejection():
    payload = {"model": "m", "messages": [], "tools": [{"x": 1}], "tool_choice": "auto"}
    changed = llm._strip_unsupported_params_if_rejected(
        payload, 400, "Error: this model does not support tools")
    assert changed is True
    assert "tools" not in payload and "tool_choice" not in payload


def test_tools_kept_when_400_unrelated():
    payload = {"model": "m", "messages": [], "tools": [{"x": 1}], "tool_choice": "auto"}
    llm._strip_unsupported_params_if_rejected(payload, 400, "bad request: messages required")
    assert "tools" in payload
