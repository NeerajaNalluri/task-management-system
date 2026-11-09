"""User management (admin only, scope users:manage).

GET    /api/users          list users (with task counts)
POST   /api/users          create a user
PUT    /api/users/<id>     edit username / email / role / reset password
DELETE /api/users/<id>     delete a user (their tasks become unassigned)
"""

import re

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func

from decorators import scope_required
from extensions import db
from models import Task, User

users_bp = Blueprint("users", __name__, url_prefix="/api/users")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,80}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLES = ("admin", "user")


def _error(message, status=400):
    return jsonify(error="validation_error", message=message), status


def _validate(data, user=None):
    """Validate fields for create (user=None) or update. Returns (clean, error_response)."""
    creating = user is None
    clean = {}

    if creating or "username" in data:
        username = str(data.get("username") or "").strip()
        if not USERNAME_RE.match(username):
            return None, _error("Username must be 3-80 characters: letters, numbers, . _ -")
        existing = User.query.filter(func.lower(User.username) == username.lower()).first()
        if existing and existing is not user:
            return None, _error("That username is already taken.", 409)
        clean["username"] = username

    if creating or "email" in data:
        email = str(data.get("email") or "").strip().lower()
        if not EMAIL_RE.match(email) or len(email) > 120:
            return None, _error("Please enter a valid email address.")
        existing = User.query.filter(func.lower(User.email) == email).first()
        if existing and existing is not user:
            return None, _error("That email is already in use.", 409)
        clean["email"] = email

    if creating or "role" in data:
        role = data.get("role", "user")
        if role not in ROLES:
            return None, _error("Role must be 'admin' or 'user'.")
        clean["role"] = role

    password = data.get("password")
    if creating or password:
        if not password or len(password) < 8:
            return None, _error("Password must be at least 8 characters.")
        clean["password"] = password

    return clean, None


def _admin_count():
    return User.query.filter_by(role="admin").count()


@users_bp.get("")
@scope_required("users:manage")
def list_users():
    counts = dict(
        db.session.query(Task.assigned_to, func.count(Task.id)).group_by(Task.assigned_to).all()
    )
    users = User.query.order_by(User.username).all()
    return jsonify([
        {
            **u.to_dict(),
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "task_count": counts.get(u.id, 0),
        }
        for u in users
    ]), 200


@users_bp.post("")
@scope_required("users:manage")
def create_user():
    clean, error = _validate(request.get_json(silent=True) or {})
    if error:
        return error
    password = clean.pop("password")
    user = User(**clean)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@users_bp.put("/<int:user_id>")
@scope_required("users:manage")
def update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="not_found", message="User not found."), 404

    clean, error = _validate(request.get_json(silent=True) or {}, user=user)
    if error:
        return error

    me = int(get_jwt_identity())
    if user.role == "admin" and clean.get("role") == "user":
        if user.id == me:
            return _error("You can't remove your own admin role.")
        if _admin_count() <= 1:
            return _error("There must be at least one admin.")

    password = clean.pop("password", None)
    for field, value in clean.items():
        setattr(user, field, value)
    if password:
        user.set_password(password)
    db.session.commit()
    return jsonify(user.to_dict()), 200


@users_bp.delete("/<int:user_id>")
@scope_required("users:manage")
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="not_found", message="User not found."), 404
    if user.id == int(get_jwt_identity()):
        return _error("You can't delete your own account.")
    if user.role == "admin" and _admin_count() <= 1:
        return _error("There must be at least one admin.")

    # Unassign their tasks explicitly (the database also does this via ON DELETE SET NULL)
    Task.query.filter_by(assigned_to=user.id).update({"assigned_to": None})
    Task.query.filter_by(created_by=user.id).update({"created_by": None})
    db.session.delete(user)
    db.session.commit()
    return jsonify(message="User deleted."), 200
