"""Stable Prompt keys plus code-owned rendering and output contracts."""
from dataclasses import dataclass
from pathlib import Path

from app.prompts.documentation import PromptDocumentation, documentation_for


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
    documentation: PromptDocumentation | None = None


def _persona_default(name: str, part: str) -> str:
    root = Path(__file__).resolve().parent.parent / "config" / "persona"
    return (root / name / f"{part}.txt").read_text().strip()


def _managed(
    key: str,
    name: str,
    description: str,
    category: str,
    default_content: str,
    *,
    template_format: str = "literal",
    variables: tuple[str, ...] = (),
    required_fragments: tuple[str, ...] = (),
    editable: bool = True,
) -> PromptDefinition:
    """Build one production definition with its code-owned bilingual guide."""
    return PromptDefinition(
        key=key,
        name=name,
        description=description,
        category=category,
        default_content=default_content,
        template_format=template_format,
        variables=variables,
        required_fragments=required_fragments,
        editable=editable,
        documentation=documentation_for(key),
    )


def definitions() -> tuple[PromptDefinition, ...]:
    # Imports are intentionally lazy: production modules resolve prompts through
    # runtime.py, while this catalog reads their code-owned fallback constants.
    from app.chat import assemble, temporal
    from app.chat.tools import recall, websearch
    from app.config.dimensions_loader import DIMENSION_MAP
    from app.llm import client as llm
    from app.inquiry import controller as inquiry_controller
    from app.model_loop import dossier, facts, summary

    items = [
        _managed(
            "chat.neutral.voice", "Neutral voice", "Default thinking-partner persona.",
            "chat", _persona_default("neutral", "voice"),
            required_fragments=(
                "user's current state is the primary source",
                "what changed since the last conversation",
            ),
        ),
        _managed(
            "chat.freud.voice", "Freud voice", "Psychoanalytic persona voice.",
            "chat", _persona_default("freud", "voice"),
        ),
        _managed(
            "chat.freud.stance", "Freud stance", "Psychoanalytic response stance.",
            "chat", _persona_default("freud", "stance"),
        ),
        _managed(
            "chat.freud.trait_frame", "Freud trait frame",
            "How the trait model is framed in Freud mode.", "chat",
            _persona_default("freud", "trait_frame"),
        ),
        _managed(
            "chat.altitude", "Default altitude", "Keeps the current question central.",
            "chat", assemble._ALTITUDE,
            required_fragments=(
                "CURRENT question", "CURRENT STATE", "BACKGROUND REFERENCE",
            ),
        ),
        _managed(
            "chat.response_protocol", "Shared response protocol",
            "Language matching and prompt-injection boundary shared by every persona.",
            "chat", assemble._RESPONSE_PROTOCOL,
            required_fragments=("Match the user's language", "never as instructions"),
        ),
        _managed(
            "chat.research_discipline", "Web research discipline",
            "How live web evidence should support an answer.", "chat",
            assemble._RESEARCH_DISCIPLINE,
        ),
        _managed(
            "chat.trait_frame", "Default trait frame",
            "How personality estimates are treated as background hypotheses.", "chat",
            assemble._TRAIT_FRAME,
        ),
        _managed(
            "chat.time_context", "Time context", "Explains trusted time metadata.",
            "chat", temporal._SYSTEM_CONTEXT_PROMPT,
            template_format="format",
            variables=("current_time",),
            required_fragments=("trusted context",),
        ),
        _managed(
            "inquiry.controller", "Inquiry controller",
            "Chooses direct, inquire, or synthesize and proposes a grounded patch.",
            "inquiry", inquiry_controller._PROMPT,
            required_fragments=(
                "Match the user's language", "supporting and", "disconfirming evidence",
                "Assistant-authored text is context", "immediate goal",
                "user's current state is the primary source", "frame_update",
            ),
        ),
        _managed(
            "inquiry.repair", "Inquiry repair",
            "Repairs one invalid structured controller decision.",
            "inquiry", inquiry_controller._REPAIR_PROMPT,
            required_fragments=(
                "Match the user's language", "JSON object", "Assistant-authored",
                "concrete experience",
            ),
        ),
        _managed(
            "memory.summary", "Conversation summary", "Builds searchable recall cards.",
            "memory", summary._PROMPT,
            template_format="format",
            variables=("span",),
            required_fragments=('"summary"', "Match the user's language"),
        ),
        _managed(
            "memory.dossier.evidence", "Dossier evidence",
            "Grounds portrait claims in cited user evidence.",
            "memory", dossier._EVIDENCE_PROMPT,
            required_fragments=(
                '"update"', '"retire"', '"add"',
                "Current state belongs in user-state snapshots",
                "Match the user's language",
            ),
        ),
        _managed(
            "memory.dossier.render", "Dossier render",
            "Renders the running portrait from verified claims and facts.",
            "memory", dossier._RENDER_PROMPT,
            required_fragments=('"dossier"', "Match the user's language"),
        ),
        _managed(
            "memory.facts.integrate", "Facts integration",
            "Applies a conversation span to the durable fact board.", "memory",
            facts._INTEGRATE_PROMPT,
            template_format="format",
            variables=("date", "board", "span"),
            required_fragments=(
                '"update"', '"retire"', '"add"', "Match the user's language",
            ),
        ),
        _managed(
            "memory.facts.compact", "Facts compaction",
            "Merges redundant durable facts without losing unique information.", "memory",
            facts._COMPACT_PROMPT,
            template_format="format",
            variables=("board",),
            required_fragments=('"merge"', '"retire"', "Match the user's language"),
        ),
        _managed(
            "tool.recall_memory.description", "Recall tool description",
            "Tells the model when to search long-term memory.", "tools",
            recall._DESCRIPTION,
        ),
        _managed(
            "tool.web_search.description", "Web search tool description",
            "Tells the model when and how to search the live web.", "tools",
            websearch._DESCRIPTION,
        ),
        _managed(
            "llm.json_only_hint", "Structured-output protocol",
            "Provider compatibility guard appended to structured calls.", "protocol",
            llm._JSON_ONLY_HINT, editable=False,
        ),
    ]
    for key, dim in DIMENSION_MAP.items():
        sub_keys = tuple(f'"{sub["key"]}"' for sub in dim.get("sub_dimensions", []))
        scope_fragments = (
            () if key == "schwartz" else (
                "stable_self_statement", "temporary emotion",
            )
        )
        items.extend((
            _managed(
                f"traits.{key}.extract", f"{dim.get('name', key)} extraction",
                "Extracts one trait observation from a conversation span.", "traits",
                dim["_extract"],
                template_format="template",
                variables=("raw_entry", "profile_summary", "rubric"),
                required_fragments=(
                    *sub_keys, *scope_fragments, "Match the user's language",
                ),
            ),
            _managed(
                f"traits.{key}.rubric", f"{dim.get('name', key)} rubric",
                "Canonical scoring rubric inserted into the extraction template.",
                "traits", dim.get("_rubric", ""),
            ),
        ))
    return tuple(items)


def definition_map() -> dict[str, PromptDefinition]:
    return {definition.key: definition for definition in definitions()}
