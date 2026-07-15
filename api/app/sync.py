"""Move the encrypted db between devices over git (e.g. a private GitHub repo).

    VELLUM_SYNC_REMOTE=git@github.com:you/vellum-data.git python -m app.sync push
    VELLUM_SYNC_REMOTE=...                                  python -m app.sync pull
    python -m app.sync status

Model: the deployment data root IS a git repo. Every mode tracks the shared
prompts.db; legacy mode also tracks vellum.db, while family mode tracks encrypted
auth.db plus each users/<id>/vellum.db. Treat it as a baton — one active device at
a time. `pull` refuses to clobber un-pushed local changes, so you can't silently
lose work by editing on two devices.

Observability DBs (traces/evals) stay per-device. The key is NEVER stored here —
it lives outside the data dir and is supplied via VELLUM_DB_KEY, so an encrypted
deployment's git remote only ever sees ciphertext.
"""
import os
import subprocess
import sys
from pathlib import Path

from app import config
from app.store import crypto

BRANCH = "main"


class SyncConflict(Exception):
    """Local and remote diverged — the user must reconcile (pull/push) by hand."""


def _repo_dir() -> Path:
    return config.base_data_dir() if config.auth_enabled() else config.data_dir()


def _synced_paths() -> list[Path]:
    if not config.auth_enabled():
        return [Path("vellum.db"), Path("prompts.db")]
    root = config.base_data_dir()
    paths = [Path("auth.db"), Path("prompts.db")]
    paths.extend(
        path.relative_to(root)
        for path in sorted((root / "users").glob("*/vellum.db"))
    )
    return paths


def _remote() -> str:
    r = os.getenv("VELLUM_SYNC_REMOTE")
    if not r:
        raise SystemExit(
            "VELLUM_SYNC_REMOTE must be set to a git remote URL "
            "(e.g. git@github.com:you/vellum-data.git)."
        )
    return r


def _git(repo: Path, *args, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=check, capture_output=True, text=True
    )


def _ensure_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        _git(repo, "init", "-b", BRANCH)
        _git(repo, "config", "user.name", os.getenv("VELLUM_DEVICE_ID", "vellum"))
        _git(repo, "config", "user.email", "vellum@local")
    # Track only canonical DBs; observability/traces stay local to the VPS.
    if config.auth_enabled():
        want = (
            "*\n!.gitignore\n!auth.db\n!prompts.db\n"
            "!users/\n!users/*/\n!users/*/vellum.db\n"
        )
    else:
        want = "*\n!.gitignore\n!vellum.db\n!prompts.db\n"
    gi = repo / ".gitignore"
    if (gi.read_text() if gi.exists() else None) != want:
        gi.write_text(want)
    remote = _remote()
    if "origin" in _git(repo, "remote", check=False).stdout.split():
        _git(repo, "remote", "set-url", "origin", remote)
    else:
        _git(repo, "remote", "add", "origin", remote)


def _checkpoint() -> None:
    """Fold a WAL sidecar into the main file so we sync a complete db. No-op in
    the default rollback-journal mode (no -wal file); best-effort if it errors."""
    repo = _repo_dir()
    for relative in _synced_paths():
        p = repo / relative
        if not p.exists() or not (p.parent / (p.name + "-wal")).exists():
            continue
        try:
            conn = crypto.sqlite_module().connect(str(p))
            crypto.apply_key(conn)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        except Exception:
            pass


def commit_local() -> bool:
    """Stage + commit the synced db(s) locally. Returns True if a commit was made."""
    repo = _repo_dir()
    _ensure_repo(repo)
    _git(repo, "add", ".gitignore")
    synced = _synced_paths()
    allowed = {".gitignore", *(str(path) for path in synced)}
    tracked = _git(repo, "ls-files", check=False).stdout.splitlines()
    stale = [path for path in tracked if path not in allowed]
    if stale:
        _git(repo, "rm", "--cached", "--ignore-unmatch", "--", *stale)
    for path in synced:
        if (repo / path).exists():
            _git(repo, "add", str(path))
    if _git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0:
        return False
    _git(repo, "commit", "-m", "vellum sync snapshot")
    return True


def push() -> None:
    _remote()  # validate before doing any work
    _checkpoint()
    repo = _repo_dir()
    made = commit_local()
    _git(repo, "fetch", "origin", BRANCH, check=False)
    res = _git(repo, "push", "origin", BRANCH, check=False)
    if res.returncode != 0:
        blob = res.stderr + res.stdout
        if "non-fast-forward" in blob or "rejected" in blob or "fetch first" in blob:
            raise SyncConflict("remote has changes you don't have — run `pull` first.")
        raise SystemExit(f"git push failed:\n{res.stderr}")
    print("pushed." if made else "nothing new to push.")


def pull() -> None:
    _remote()
    repo = _repo_dir()
    _ensure_repo(repo)
    _git(repo, "fetch", "origin", BRANCH, check=False)
    if _git(repo, "rev-parse", "--verify", f"origin/{BRANCH}", check=False).returncode != 0:
        print("remote is empty — nothing to pull.")
        return
    if _git(repo, "rev-parse", "--verify", "HEAD", check=False).returncode == 0:
        ahead = _git(repo, "rev-list", "--count", f"origin/{BRANCH}..HEAD").stdout.strip()
        if ahead != "0":
            raise SyncConflict(
                f"{ahead} un-pushed local change(s) on this device — `push` them "
                "or discard before pulling."
            )
    _git(repo, "reset", "--hard", f"origin/{BRANCH}")
    print("pulled.")


def status() -> dict:
    _remote()
    repo = _repo_dir()
    _ensure_repo(repo)
    _git(repo, "fetch", "origin", BRANCH, check=False)
    has_head = _git(repo, "rev-parse", "--verify", "HEAD", check=False).returncode == 0
    has_remote = (
        _git(repo, "rev-parse", "--verify", f"origin/{BRANCH}", check=False).returncode == 0
    )
    ahead = behind = 0
    if has_head and has_remote:
        ahead = int(_git(repo, "rev-list", "--count", f"origin/{BRANCH}..HEAD").stdout.strip())
        behind = int(_git(repo, "rev-list", "--count", f"HEAD..origin/{BRANCH}").stdout.strip())
    st = {"ahead": ahead, "behind": behind}
    print(f"ahead {ahead}, behind {behind} (remote: {os.getenv('VELLUM_SYNC_REMOTE')})")
    return st


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    cmd = argv[0] if argv else ""
    if cmd == "push":
        push()
    elif cmd == "pull":
        pull()
    elif cmd == "status":
        status()
    else:
        raise SystemExit("usage: python -m app.sync {push|pull|status}")


if __name__ == "__main__":
    main()
