"""Move the encrypted db between devices over git (e.g. a private GitHub repo).

    VELLUM_SYNC_REMOTE=git@github.com:you/vellum-data.git python -m app.sync push
    VELLUM_SYNC_REMOTE=...                                  python -m app.sync pull
    python -m app.sync status

Model: the data dir IS a git repo whose only tracked file is the encrypted
vellum.db; the remote holds the single canonical copy. Treat it as a baton —
one active device at a time. `pull` refuses to clobber un-pushed local changes,
so you can't silently lose work by editing on two devices.

Only vellum.db is synced; observability.db (traces/evals) stays per-device.
The key is NEVER stored here — it lives outside the data dir and is supplied via
VELLUM_DB_KEY, so the git remote only ever sees ciphertext.
"""
import os
import subprocess
import sys
from pathlib import Path

from app.config import data_dir, db_path
from app.store import crypto

SYNCED = ["vellum.db"]
BRANCH = "main"


class SyncConflict(Exception):
    """Local and remote diverged — the user must reconcile (pull/push) by hand."""


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
    # Track only the synced dbs; ignore everything else (vectors/, observability.db, ...)
    want = "*\n!.gitignore\n" + "".join(f"!{n}\n" for n in SYNCED)
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
    p = db_path()
    if not (p.parent / (p.name + "-wal")).exists():
        return
    try:
        conn = crypto.sqlite_module().connect(str(p))
        crypto.apply_key(conn)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except Exception:
        pass


def commit_local() -> bool:
    """Stage + commit the synced db(s) locally. Returns True if a commit was made."""
    repo = data_dir()
    _ensure_repo(repo)
    _git(repo, "add", ".gitignore")
    for n in SYNCED:
        if (repo / n).exists():
            _git(repo, "add", n)
    if _git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0:
        return False
    _git(repo, "commit", "-m", "vellum sync snapshot")
    return True


def push() -> None:
    _remote()  # validate before doing any work
    _checkpoint()
    repo = data_dir()
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
    repo = data_dir()
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
    repo = data_dir()
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
