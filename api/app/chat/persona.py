"""Personas are prompt-side *modes*, not a single voice. Each lives in its own
folder under config/persona/<name>/:

  voice.txt        — required; who the assistant is for this mode
  stance.txt       — optional; overrides the default altitude framing (assemble.py)
  trait_frame.txt  — optional; overrides how the personality read is framed (assemble.py)

The data pipeline (dossier, facts, traits, recall) is shared across modes — only
the prompt-side voice + stance swap. The mode is chosen per chat turn (web sends
it) and falls back to VELLUM_PERSONA, then to `neutral`."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app import config

_DIR = Path(__file__).resolve().parent.parent / "config" / "persona"
_DEFAULT = "neutral"


@dataclass(frozen=True)
class Persona:
    name: str
    voice: str
    stance: str | None        # when set, replaces the default altitude framing for this mode
    trait_frame: str | None    # when set, replaces the default personality-read framing


def _read(path: Path) -> str | None:
    return path.read_text().strip() if path.exists() else None


@lru_cache(maxsize=None)
def _load(name: str) -> Persona:
    voice = _read(_DIR / name / "voice.txt")
    if voice is None:                       # unknown/empty mode → fall back to default
        if name != _DEFAULT:
            return _load(_DEFAULT)
        raise FileNotFoundError(f"persona '{name}' has no voice.txt")
    return Persona(name=name, voice=voice,
                   stance=_read(_DIR / name / "stance.txt"),
                   trait_frame=_read(_DIR / name / "trait_frame.txt"))


def available() -> set[str]:
    """Mode names with a voice.txt — the whitelist the chat route validates against."""
    if not _DIR.exists():
        return set()
    return {p.name for p in _DIR.iterdir() if (p / "voice.txt").exists()}


def load(name: str | None = None) -> Persona:
    return _load(name or config.persona_name())
