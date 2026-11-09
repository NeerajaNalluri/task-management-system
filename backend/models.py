from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="user")  # "admin" or "user"
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.CheckConstraint("role IN ('admin', 'user')", name="ck_users_role"),)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "username": self.username, "email": self.email, "role": self.role}


def _now():
    return datetime.now(timezone.utc)


class Task(db.Model):
    __tablename__ = "tasks"

    STATUSES = ("todo", "in_progress", "done")
    PRIORITIES = ("low", "medium", "high")
    CATEGORIES = ("general", "development", "design", "testing", "documentation")

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="", server_default="")
    status = db.Column(db.String(20), nullable=False, default="todo")
    priority = db.Column(db.String(10), nullable=False, default="medium")
    category = db.Column(db.String(20), nullable=False, default="general", server_default="general")
    due_date = db.Column(db.Date, nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_now, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now, server_default=db.func.now())

    assignee = db.relationship("User", foreign_keys=[assigned_to])
    creator = db.relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        db.CheckConstraint("status IN ('todo', 'in_progress', 'done')", name="ck_tasks_status"),
        db.CheckConstraint("priority IN ('low', 'medium', 'high')", name="ck_tasks_priority"),
        db.CheckConstraint(
            "category IN ('general', 'development', 'design', 'testing', 'documentation')",
            name="ck_tasks_category",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "category": self.category,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "assigned_to": self.assigned_to,
            "assignee": self.assignee.username if self.assignee else None,
            "created_by": self.creator.username if self.creator else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class OAuthClient(db.Model):
    """An application allowed to request tokens (OAuth 2.0 "client").

    Public client (no secret)      -> e.g. the browser frontend, which can't keep a secret.
    Confidential client (secret)   -> e.g. a server script or Postman; must send its secret.
    """

    __tablename__ = "oauth_clients"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(80), unique=True, nullable=False)
    client_secret_hash = db.Column(db.String(255), nullable=True)  # NULL = public client
    name = db.Column(db.String(120), nullable=False)
    allowed_scopes = db.Column(db.Text, nullable=False)   # space-separated
    grant_types = db.Column(db.Text, nullable=False)      # space-separated
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @property
    def is_public(self):
        return self.client_secret_hash is None

    def set_secret(self, secret):
        self.client_secret_hash = generate_password_hash(secret)

    def check_secret(self, secret):
        return bool(secret) and check_password_hash(self.client_secret_hash, secret)

    def scope_set(self):
        return set(self.allowed_scopes.split())

    def allows_grant(self, grant_type):
        return grant_type in self.grant_types.split()


class TokenBlocklist(db.Model):
    """Tokens that were revoked at logout. Any token listed here is rejected."""

    __tablename__ = "token_blocklist"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), unique=True, nullable=False, index=True)
    revoked_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
