from functools import lru_cache
from pathlib import Path

from app import config

_DIR = Path(__file__).resolve().parent.parent / "config" / "persona"


@lru_cache(maxsize=None)
def _read(name: str) -> str:
    path = _DIR / f"{name}.txt"
    if not path.exists():
        path = _DIR / "neutral.txt"
    return path.read_text().strip()


def load() -> str:
    return _read(config.persona_name())
