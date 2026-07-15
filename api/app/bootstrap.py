"""Apply all schemas appropriate to legacy or private-family mode."""
from app import config
from app.data_scope import user_scope
from app.store import crypto, db
from app.prompts import db as prompt_db


def migrate_all() -> None:
    prompt_db.run_migrations()
    if not config.auth_enabled():
        crypto.assert_db_accessible()
        db.run_migrations()
        return

    from app.auth import accounts

    accounts.run_migrations()
    for user in accounts.list_users():
        with user_scope(user["id"]):
            crypto.assert_db_accessible()
            db.run_migrations()


if __name__ == "__main__":
    migrate_all()
