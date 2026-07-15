"""Localized, code-owned usage guides for the managed Prompt catalog."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptGuide:
    usage: str
    runtime: str
    editing_guidance: tuple[str, ...]


@dataclass(frozen=True)
class PromptDocumentation:
    en: PromptGuide
    zh: PromptGuide


def _guide(raw: tuple[str, str, tuple[str, ...]]) -> PromptGuide:
    return PromptGuide(
        usage=raw[0],
        runtime=raw[1],
        editing_guidance=raw[2],
    )


def documentation_for(key: str) -> PromptDocumentation:
    # Kept in separate language files so detailed prose does not bury the catalog
    # or duplicate UI translations. Missing entries fail during catalog loading.
    from app.prompts.documentation_en import GUIDES as EN_GUIDES
    from app.prompts.documentation_zh import GUIDES as ZH_GUIDES

    return PromptDocumentation(en=_guide(EN_GUIDES[key]), zh=_guide(ZH_GUIDES[key]))
