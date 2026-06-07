from app.chat.tools import registry, recall


def test_registry_dispatch():
    reg = registry.ToolRegistry()
    reg.register(
        schema={"type": "function",
                "function": {"name": "echo", "description": "echo",
                             "parameters": {"type": "object",
                                            "properties": {"x": {"type": "string"}}}}},
        handler=lambda args: f"got {args['x']}",
    )
    assert [t["function"]["name"] for t in reg.schemas()] == ["echo"]
    assert reg.dispatch("echo", {"x": "hi"}) == "got hi"


def test_recall_tool_registered_and_calls_retrieval(monkeypatch):
    monkeypatch.setattr(recall.retrieval, "retrieve",
                        lambda q, **kw: [{"start": 0, "end": 0, "text": "user: past thing"}])
    reg = registry.ToolRegistry()
    recall.register_into(reg)
    names = [t["function"]["name"] for t in reg.schemas()]
    assert "recall_memory" in names
    out = reg.dispatch("recall_memory", {"query": "past"})
    assert "past thing" in out
