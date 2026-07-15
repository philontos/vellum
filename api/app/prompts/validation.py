"""Static publication gates for editable Prompt templates."""
from string import Formatter, Template

from app.prompts.catalog import PromptDefinition


MAX_CONTENT_CHARS = 200_000


def _format_variables(content: str) -> tuple[set[str], list[str]]:
    found: set[str] = set()
    errors: list[str] = []
    try:
        for _literal, field, spec, conversion in Formatter().parse(content):
            if field is not None:
                # Only exact named fields are supported. Attribute/index traversal
                # can pass a shallow name check yet fail later during a model job.
                found.add(field)
                if spec and "format specifications are not supported" not in errors:
                    errors.append("format specifications are not supported")
                if (
                    conversion is not None
                    and "format conversions are not supported" not in errors
                ):
                    errors.append("format conversions are not supported")
    except ValueError as exc:
        return set(), [f"invalid format template: {exc}"]
    return found, errors


def _template_variables(content: str) -> tuple[set[str], list[str]]:
    template = Template(content)
    if not template.is_valid():
        return set(), ["invalid $variable template"]
    return set(template.get_identifiers()), []


def validate(definition: PromptDefinition, content: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(content, str) or not content.strip():
        errors.append("content must not be empty")
        return errors
    if len(content) > MAX_CONTENT_CHARS:
        errors.append(f"content exceeds {MAX_CONTENT_CHARS} characters")

    variables: set[str] = set()
    if definition.template_format == "format":
        variables, parse_errors = _format_variables(content)
        errors.extend(parse_errors)
    elif definition.template_format == "template":
        variables, parse_errors = _template_variables(content)
        errors.extend(parse_errors)

    expected = set(definition.variables)
    missing = expected - variables
    unknown = variables - expected
    if missing:
        errors.append("missing variables: " + ", ".join(sorted(missing)))
    if unknown:
        errors.append("unknown variables: " + ", ".join(sorted(unknown)))
    for fragment in definition.required_fragments:
        if fragment not in content:
            errors.append(f"missing required contract: {fragment}")
    return errors
