"""Owner-operated account provisioning; there is intentionally no web signup."""
import argparse
import getpass
import sys

from app.auth import accounts, legacy


def _password(from_stdin: bool) -> str:
    if from_stdin:
        value = sys.stdin.readline().rstrip("\r\n")
        if not value:
            raise SystemExit("password stdin was empty")
        return value
    first = getpass.getpass("Password: ")
    second = getpass.getpass("Confirm password: ")
    if first != second:
        raise SystemExit("passwords do not match")
    return first


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.auth.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="provision a family account")
    create.add_argument("--username", required=True)
    create.add_argument("--display-name", required=True)
    create.add_argument("--role", choices=["owner", "member"], default="member")
    create.add_argument(
        "--adopt-legacy", action="store_true",
        help="copy the old root vellum.db/observability.db into this account",
    )
    create.add_argument("--password-stdin", action="store_true")

    commands.add_parser("list", help="list accounts (never prints password hashes)")

    disable = commands.add_parser("disable", help="disable an account and revoke sessions")
    disable.add_argument("username")

    passwd = commands.add_parser("passwd", help="change a password and revoke sessions")
    passwd.add_argument("username")
    passwd.add_argument("--password-stdin", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if args.command == "create":
        user = accounts.create_user(
            args.username,
            args.display_name,
            _password(args.password_stdin),
            role=args.role,
        )
        copied = legacy.adopt(user["id"]) if args.adopt_legacy else []
        suffix = f"; adopted {', '.join(copied)}" if copied else ""
        print(f"created {user['username']} ({user['role']}, id={user['id']}){suffix}")
        return
    if args.command == "list":
        for user in accounts.list_users():
            print(
                f"{user['username']}\t{user['display_name']}\t"
                f"{user['role']}\t{user['status']}\t{user['id']}"
            )
        return

    user = accounts.get_by_username(args.username)
    if user is None:
        raise SystemExit(f"unknown user: {args.username}")
    if args.command == "disable":
        accounts.disable(user["id"])
        print(f"disabled {user['username']}; sessions revoked")
    elif args.command == "passwd":
        accounts.set_password(user["id"], _password(args.password_stdin))
        print(f"updated password for {user['username']}; sessions revoked")


if __name__ == "__main__":
    main()
