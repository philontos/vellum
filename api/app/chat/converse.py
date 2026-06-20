"""One chat turn, collected into a string — the same brain as POST /chat
(persist the user turn, assemble context with recall baked in, stream the reply
through the tool loop, persist the assistant turn) for callers that cannot
consume an SSE stream, such as the Feishu adapter."""
from app.chat import assemble, ingest, respond


async def reply(text: str) -> str:
    """Run `text` through the chat pipeline and return the assistant's reply.
    Persists both turns so Feishu conversations share vellum's eternal stream
    with the web UI."""
    await ingest.persist_user(text)
    messages = await assemble.build_messages(query=text)

    final = ""
    async for ev in respond.stream(messages):
        if ev["type"] == "final":
            final = ev["content"]

    ingest.persist_assistant(final)
    return final
