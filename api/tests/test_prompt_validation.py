from dataclasses import replace

import pytest

from app.prompts.catalog import PromptDefinition, definitions
from app.prompts.validation import validate


def test_every_builtin_prompt_satisfies_its_publication_contract():
    failures = {
        definition.key: validate(definition, definition.default_content)
        for definition in definitions()
        if validate(definition, definition.default_content)
    }

    assert failures == {}


def test_every_builtin_prompt_has_detailed_bilingual_documentation():
    for definition in definitions():
        documentation = definition.documentation
        for language in ("en", "zh"):
            guide = getattr(documentation, language)
            usage_minimum = 80 if language == "en" else 45
            runtime_minimum = 80 if language == "en" else 60
            assert len(guide.usage) >= usage_minimum, (
                definition.key, language, "usage",
            )
            assert len(guide.runtime) >= runtime_minimum, (
                definition.key, language, "runtime",
            )
            assert len(guide.editing_guidance) >= 2, (
                definition.key, language, "editing_guidance",
            )
            assert all(len(item) >= 20 for item in guide.editing_guidance), (
                definition.key, language, "editing_guidance item",
            )


def test_format_templates_require_exact_known_variables():
    definition = PromptDefinition(
        key="test.format",
        name="test",
        description="",
        category="test",
        default_content="{span}",
        template_format="format",
        variables=("span",),
    )

    assert validate(definition, "{span}") == []
    assert "missing variables: span" in validate(definition, "plain text")
    nested_errors = validate(definition, "{span.__class__}")
    assert "missing variables: span" in nested_errors
    assert "unknown variables: span.__class__" in nested_errors
    assert validate(definition, "{span") == [
        "invalid format template: expected '}' before end of string",
        "missing variables: span",
    ]


def test_dollar_templates_reject_missing_unknown_and_malformed_placeholders():
    definition = PromptDefinition(
        key="test.template",
        name="test",
        description="",
        category="test",
        default_content="$entry",
        template_format="template",
        variables=("entry",),
    )

    assert validate(definition, "$entry") == []
    assert "unknown variables: other" in validate(definition, "$entry $other")
    assert validate(definition, "$") == [
        "invalid $variable template",
        "missing variables: entry",
    ]


def test_required_output_and_language_contracts_are_hard_publish_gates():
    summary = next(item for item in definitions() if item.key == "memory.summary")
    stripped = summary.default_content.replace('"summary"', '"digest"').replace(
        "Match the user's language", "Always answer in English",
    )

    errors = validate(replace(summary), stripped)

    assert "missing required contract: \"summary\"" in errors
    assert "missing required contract: Match the user's language" in errors


@pytest.mark.parametrize(
    ("content", "expected_error"),
    [
        ("{span:{other}}", "format specifications are not supported"),
        ("{span:d}", "format specifications are not supported"),
        ("{span!z}", "format conversions are not supported"),
    ],
)
def test_format_templates_reject_runtime_only_conversion_and_specs(
    content, expected_error,
):
    definition = PromptDefinition(
        key="test.format",
        name="test",
        description="",
        category="test",
        default_content="{span}",
        template_format="format",
        variables=("span",),
    )

    assert expected_error in validate(definition, content)
