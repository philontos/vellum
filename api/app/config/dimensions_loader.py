"""Discover dimension configs under config/dimensions/<key>/. Each dir has a
config.py (DIMENSION dict), an extract.spt prompt template, and an optional
rubric.md. Loaded once at import into DIMENSION_MAP."""
import importlib
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "dimensions"


def load_dimensions() -> dict:
    dims: dict = {}
    for sub in sorted(_DIR.iterdir()):
        if not sub.is_dir() or sub.name.startswith("_") or sub.name.startswith("."):
            continue
        mod = importlib.import_module(f"app.config.dimensions.{sub.name}.config")
        d = dict(mod.DIMENSION)
        if not d.get("enabled", True):
            continue
        d["_extract"] = (sub / d["prompt_template"]).read_text()
        rubric = sub / "rubric.md"
        d["_rubric"] = rubric.read_text() if rubric.exists() else ""
        dims[d["key"]] = d
    return dims


DIMENSION_MAP = load_dimensions()


def dimension_meta(key: str) -> dict | None:
    """Frontend-facing display metadata for one dimension: its name, whether its
    sub-dimensions sort by score, and each sub-dimension's label (+ `poles` when
    bipolar). None for an unknown/disabled dimension."""
    d = DIMENSION_MAP.get(key)
    if not d:
        return None
    subs = []
    for s in d.get("sub_dimensions", []):
        sub = {"key": s["key"], "name": s["name"]}
        if s.get("poles"):
            sub["poles"] = list(s["poles"])
        subs.append(sub)
    return {
        "name": d.get("name", key),
        "label": d.get("summary_label", key),
        "sort_by_score": bool(d.get("sort_by_score", False)),
        "sub_dimensions": subs,
    }
