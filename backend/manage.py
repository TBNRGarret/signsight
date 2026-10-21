"""Local administrative commands. Run from the project root."""

import argparse
from getpass import getpass

from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.db.database import SessionLocal, engine, init_db
from backend.app.db.models import User
from backend.app.db.migrations import backup_sqlite_database
from backend.app.schemas.auth import UserRegister
from backend.app.services.auth_service import create_user


def bootstrap_admin(username: str, email: str, password: str, session_factory=None):
    payload = UserRegister(username=username, email=email, password=password)
    with (session_factory if session_factory is not None else SessionLocal)() as db:
        if db.query(User.id).filter(User.role == "admin", User.is_active.is_(True), User.password_hash.isnot(None)).first():
            raise ValueError("An active administrator already exists; bootstrap is only for initial setup")
        return create_user(db, payload, role="admin")


def main():
    parser = argparse.ArgumentParser(description="SignSight database and first-administrator setup")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="Apply versioned database migrations")
    commands.add_parser("backup", help="Back up an existing SQLite database consistently")
    commands.add_parser('expire-signs',help='Run the idempotent expiry job once (for an external scheduler)')
    bootstrap = commands.add_parser("bootstrap-admin", help="Create the first administrator (password prompted securely)")
    bootstrap.add_argument("--username", required=True)
    bootstrap.add_argument("--email", required=True)
    args = parser.parse_args()
    try:
        if args.command == "backup":
            print(f"Database backup saved: {backup_sqlite_database(engine)}")
            return
        init_db(engine)
        if args.command=='expire-signs':
            from backend.app.services.lifecycle_service import expire_due_records
            with SessionLocal() as db: print(f'Expired records: {expire_due_records(db)}')
            return
        if args.command == "migrate":
            print("Database migrations complete.")
            return
        password = getpass("Administrator password (10–128 characters): ")
        if password != getpass("Repeat password: "):
            parser.exit(1, "Passwords do not match.\n")
        user = bootstrap_admin(args.username, args.email, password)
        print(f"Administrator created: {user.username}")
    except ValidationError:
        parser.exit(1, "Invalid account details: check username, email and password length.\n")
    except (HTTPException, ValueError) as exc:
        parser.exit(1, f"Setup failed: {exc.detail if isinstance(exc, HTTPException) else str(exc)}\n")


if __name__ == "__main__":
    main()
