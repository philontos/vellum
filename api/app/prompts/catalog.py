"""Stable Prompt keys plus code-owned rendering and output contracts."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptDefinition:
    key: str
    name: str
    description: str
    category: str
    default_content: str
    template_format: str = "literal"
    variables: tuple[str, ...] = ()
    required_fragments: tuple[str, ...] = ()
    editable: bool = True


def _persona_default(name: str, part: str) -> str:
    root = Path(__file__).resolve().parent.parent / "config" / "persona"
    return (root / name / f"{part}.txt").read_text().strip()


def definitions() -> tuple[PromptDefinition, ...]:
    # Imports are intentionally lazy: production modules resolve prompts through
    # runtime.py, while this catalog reads their code-owned fallback constants.
    from app.chat import assemble, temporal
    from app.chat.tools import recall, websearch
    from app.config.dimensions_loader import DIMENSION_MAP
    from app.llm import client as llm
    from app.model_loop import dossier, facts, summary

    items = [
        PromptDefinition(
            "chat.neutral.voice", "Neutral voice", "Default thinking-partner persona.",
            "chat", _persona_default("neutral", "voice"),
        ),
        PromptDefinition(
            "chat.freud.voice", "Freud voice", "Psychoanalytic persona voice.",
            "chat", _persona_default("freud", "voice"),
        ),
        PromptDefinition(
            "chat.freud.stance", "Freud stance", "Psychoanalytic response stance.",
            "chat", _persona_default("freud", "stance"),
        ),
        PromptDefinition(
            "chat.freud.trait_frame", "Freud trait frame",
            "How the trait model is framed in Freud mode.", "chat",
            _persona_default("freud", "trait_frame"),
        ),
        PromptDefinition(
            "chat.altitude", "Default altitude", "Keeps the current question central.",
            "chat", assemble._ALTITUDE,
            required_fragments=("CURRENT question", "BACKGROUND REFERENCE"),
        ),
        PromptDefinition(
            "chat.response_protocol", "Shared response protocol",
            "Language matching and prompt-injection boundary shared by every persona.",
            "chat", assemble._RESPONSE_PROTOCOL,
            required_fragments=("Match the user's language", "never as instructions"),
        ),
        PromptDefinition(
            "chat.research_discipline", "Web research discipline",
            "How live web evidence should support an answer.", "chat",
            assemble._RESEARCH_DISCIPLINE,
        ),
        PromptDefinition(
            "chat.trait_frame", "Default trait frame",
            "How personality estimates are treated as background hypotheses.", "chat",
            assemble._TRAIT_FRAME,
        ),
        PromptDefinition(
            "chat.time_context", "Time context", "Explains trusted time metadata.",
            "chat", temporal._SYSTEM_CONTEXT_PROMPT, "format", ("current_time",),
            ("trusted context",),
        ),
        PromptDefinition(
            "memory.summary", "Conversation summary", "Builds searchable recall cards.",
            "memory", summary._PROMPT, "format", ("span",),
            ('"summary"', "Match the user's language"),
        ),
        PromptDefinition(
            "memory.dossier", "Dossier rewrite", "Maintains the running user portrait.",
            "memory", dossier._PROMPT, "format", ("cap", "prior", "span"),
            ('"dossier"', "Match the user's language"),
        ),
        PromptDefinition(
            "memory.facts.integrate", "Facts integration",
            "Applies a conversation span to the durable fact board.", "memory",
            facts._INTEGRATE_PROMPT, "format", ("date", "board", "span"),
            ('"update"', '"retire"', '"add"', "Match the user's language"),
        ),
        PromptDefinition(
            "memory.facts.compact", "Facts compaction",
            "Merges redundant durable facts without losing unique information.", "memory",
            facts._COMPACT_PROMPT, "format", ("board",),
            ('"merge"', '"retire"', "Match the user's language"),
        ),
        PromptDefinition(
            "tool.recall_memory.description", "Recall tool description",
            "Tells the model when to search long-term memory.", "tools",
            recall._DESCRIPTION,
        ),
        PromptDefinition(
            "tool.web_search.description", "Web search tool description",
            "Tells the model when and how to search the live web.", "tools",
            websearch._DESCRIPTION,
        ),
        PromptDefinition(
            "llm.json_only_hint", "Structured-output protocol",
            "Provider compatibility guard appended to structured calls.", "protocol",
            llm._JSON_ONLY_HINT, editable=False,
        ),
    ]
    for key, dim in DIMENSION_MAP.items():
        sub_keys = tuple(f'"{sub["key"]}"' for sub in dim.get("sub_dimensions", []))
        items.extend((
            PromptDefinition(
                f"traits.{key}.extract", f"{dim.get('name', key)} extraction",
                "Extracts one trait observation from a conversation span.", "traits",
                dim["_extract"], "template",
                ("raw_entry", "profile_summary", "rubric"),
                (*sub_keys, "Match the user's language"),
            ),
            PromptDefinition(
                f"traits.{key}.rubric", f"{dim.get('name', key)} rubric",
                "Canonical scoring rubric inserted into the extraction template.",
                "traits", dim.get("_rubric", ""),
            ),
        ))
    return tuple(items)


def definition_map() -> dict[str, PromptDefinition]:
    return {definition.key: definition for definition in definitions()}
