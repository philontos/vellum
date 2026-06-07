from pathlib import Path

from app import config

_DIR = Path(__file__).resolve().parent.parent / "config" / "persona"


def load() -> str:
    name = config.persona_name()
    path = _DIR / f"{name}.txt"
    if not path.exists():
        path = _DIR / "neutral.txt"
    return path.read_text().strip()
