"""Create the database (if missing), tables, starter accounts, tasks and OAuth clients.

Run:  python seed.py                      (safe to run again; skips what exists)
      python seed.py --reset-cli-secret   (generate a new secret for the taskforge-cli client)
"""

import secrets
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app import app
from config import Config
from extensions import db
from models import OAuthClient, Task, User
from oauth import SCOPES

WEB_CLIENT_ID = "taskforge-web"
CLI_CLIENT_ID = "taskforge-cli"

DEFAULT_USERS = [
    {"username": "admin", "email": "admin@taskmanager.local", "password": "Admin@123", "role": "admin"},
    {"username": "user", "email": "user@taskmanager.local", "password": "User@123", "role": "user"},
]


def connection_help(error):
    print("\nCould not connect to PostgreSQL. Check the DB_* values in backend/.env")
    print("  - DB_PASSWORD must be your real postgres password")
    print("  - PostgreSQL must be running on DB_HOST:DB_PORT")
    print(f"\nDetails: {getattr(error, 'orig', error)}")
    sys.exit(1)


def ensure_database_exists():
    """Connect to the default 'postgres' database and create DB_NAME if it's missing."""
    server_url = Config.SQLALCHEMY_DATABASE_URI.set(database="postgres")
    engine = create_engine(server_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": Config.DB_NAME}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{Config.DB_NAME}"'))
                print(f"Created database '{Config.DB_NAME}'.")
    except OperationalError as e:
        connection_help(e)
    finally:
        engine.dispose()


def run_migrations():
    """Apply every .sql file in database/migrations, in name order.

    create_all() only creates NEW tables; it never adds columns to existing ones.
    Migrations handle those changes. Each file is written so running it twice is harmless.
    """
    folder = Path(__file__).parent / "database" / "migrations"
    for path in sorted(folder.glob("*.sql")):
        with db.engine.begin() as conn:
            conn.exec_driver_sql(path.read_text(encoding="utf-8"))
        print(f"Applied migration {path.name}")


ensure_database_exists()

with app.app_context():
    try:
        db.create_all()
        run_migrations()
    except OperationalError as e:
        connection_help(e)

    for info in DEFAULT_USERS:
        if User.query.filter_by(username=info["username"]).first():
            print(f"'{info['username']}' already exists, skipping.")
            continue
        user = User(username=info["username"], email=info["email"], role=info["role"])
        user.set_password(info["password"])
        db.session.add(user)
        print(f"Created {info['role']}: {info['username']} / {info['password']}")
    db.session.commit()

    # Starter tasks - only added when the tasks table is empty
    if Task.query.count() == 0:
        admin = User.query.filter_by(username="admin").first()
        user = User.query.filter_by(username="user").first()
        today = date.today()
        starter = [
            ("Design login screens", "Admin and user portals", "done", "high", "design", -3, user),
            ("Set up PostgreSQL schema", "Users, tasks and token tables", "done", "high", "development", -1, admin),
            ("Build task CRUD API", "Create, read, update, delete endpoints", "in_progress", "high", "development", 2, admin),
            ("Task list UI", "Table with filters and search", "in_progress", "medium", "design", 4, user),
            ("Write API documentation", "Endpoints and token flow", "todo", "low", "documentation", 9, user),
            ("QA test pass", "Login, logout, permissions", "todo", "medium", "testing", 12, user),
        ]
        for title, desc, status, priority, category, days, assignee in starter:
            db.session.add(Task(
                title=title, description=desc, status=status, priority=priority, category=category,
                due_date=today + timedelta(days=days),
                assigned_to=assignee.id if assignee else None,
                created_by=admin.id if admin else None,
            ))
        db.session.commit()
        print(f"Added {len(starter)} starter tasks.")
    else:
        print("Tasks already exist, skipping starter tasks.")

    # OAuth clients
    all_scopes = " ".join(SCOPES)
    if not OAuthClient.query.filter_by(client_id=WEB_CLIENT_ID).first():
        db.session.add(OAuthClient(
            client_id=WEB_CLIENT_ID, name="Task Manager web app (browser)",
            allowed_scopes=all_scopes, grant_types="password refresh_token",
        ))  # public client: no secret, because browser code can't hide one
        print(f"Created public OAuth client '{WEB_CLIENT_ID}'.")

    cli = OAuthClient.query.filter_by(client_id=CLI_CLIENT_ID).first()
    if not cli or "--reset-cli-secret" in sys.argv:
        secret = secrets.token_urlsafe(32)
        if not cli:
            cli = OAuthClient(
                client_id=CLI_CLIENT_ID, name="Scripts / Postman",
                allowed_scopes=all_scopes, grant_types="password refresh_token",
            )
            db.session.add(cli)
        cli.set_secret(secret)
        print(f"Confidential OAuth client '{CLI_CLIENT_ID}' secret (shown once, save it): {secret}")
    db.session.commit()

    print("Done.")
