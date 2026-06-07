"""Generic tool registry. A tool = (OpenAI-style schema, handler(args)->str).
The chat loop calls schemas() to advertise tools and dispatch() to run a call.
Adding a new tool later = register one entry; the loop never changes."""
from typing import Callable


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, dict] = {}

    def register(self, schema: dict, handler: Callable[[dict], str]) -> None:
        name = schema["function"]["name"]
        self._tools[name] = {"schema": schema, "handler": handler}

    def schemas(self) -> list[dict]:
        return [t["schema"] for t in self._tools.values()]

    def dispatch(self, name: str, args: dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"ERROR: unknown tool {name!r}"
        try:
            return tool["handler"](args)
        except Exception as exc:  # tool failures must not crash the chat turn
            return f"ERROR running {name}: {exc}"
