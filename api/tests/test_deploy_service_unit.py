import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RENDERER = ROOT / "deploy" / "render-service-unit.sh"


def _render_unit(host: str | None = None) -> str:
    env = {
        **os.environ,
        "VELLUM_REPO": "/srv/vellum",
        "VELLUM_PORT": "18090",
        "VELLUM_RUN_USER": "vellum",
    }
    if host is not None:
        env["VELLUM_HOST"] = host
    else:
        env.pop("VELLUM_HOST", None)

    return subprocess.run(
        ["bash", str(RENDERER)],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    ).stdout


def test_service_unit_defaults_to_loopback():
    unit = _render_unit()

    assert "Environment=VELLUM_HOST=127.0.0.1" in unit
    assert "Environment=VELLUM_PORT=18090" in unit
    assert "--host ${VELLUM_HOST} --port ${VELLUM_PORT}" in unit


def test_service_unit_can_bind_to_wireguard_address():
    unit = _render_unit("10.10.0.1")

    assert "Environment=VELLUM_HOST=10.10.0.1" in unit
    assert "--host ${VELLUM_HOST} --port ${VELLUM_PORT}" in unit


def test_service_unit_rejects_wildcard_bind():
    env = {
        **os.environ,
        "VELLUM_REPO": "/srv/vellum",
        "VELLUM_RUN_USER": "vellum",
        "VELLUM_HOST": "0.0.0.0",
    }

    result = subprocess.run(
        ["bash", str(RENDERER)],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.returncode != 0
    assert "wildcard" in result.stderr.lower()
