import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WAITER = ROOT / "deploy" / "wait-for-health.sh"


def test_health_waiter_retries_until_service_is_ready(tmp_path):
    attempts = tmp_path / "attempts"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    curl = bin_dir / "curl"
    curl.write_text(
        "#!/usr/bin/env bash\n"
        f"attempts={attempts!s}\n"
        'count="$(cat "$attempts" 2>/dev/null || echo 0)"\n'
        'count="$((count + 1))"\n'
        'printf "%s\\n" "$count" > "$attempts"\n'
        '[ "$count" -ge 3 ] || exit 7\n'
        "printf '{\"status\":\"ok\"}\\n'\n"
    )
    curl.chmod(0o755)

    sleep = bin_dir / "sleep"
    sleep.write_text("#!/usr/bin/env bash\nexit 0\n")
    sleep.chmod(0o755)

    result = subprocess.run(
        ["bash", str(WAITER), "http://10.10.0.1:18090/health"],
        check=False,
        capture_output=True,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "VELLUM_HEALTH_ATTEMPTS": "5",
            "VELLUM_HEALTH_INTERVAL": "0",
        },
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == '{"status":"ok"}'
    assert attempts.read_text().strip() == "3"
