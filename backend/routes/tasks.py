"""Task endpoints.

Permissions come from the OAuth "scope" inside the access token:

    GET    /api/tasks          tasks:read    (admin, user)
    GET    /api/tasks/<id>     tasks:read    (admin, user)
    POST   /api/tasks          tasks:write   (admin)
    PUT    /api/tasks/<id>     tasks:write   (admin)
    DELETE /api/tasks/<id>     tasks:write   (admin)
"""

from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from decorators import scope_required
from extensions import db
from models import Task, User

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api")


def _validate(data, partial=False):
    """Check incoming task data. Returns (clean_fields, error_message)."""
    clean = {}

    if "title" in data or not partial:
        title = str(data.get("title") or "").strip()
        if not title:
            return None, "Title is required."
        if len(title) > 200:
            return None, "Title must be 200 characters or fewer."
        clean["title"] = title

    if "description" in data:
        clean["description"] = str(data.get("description") or "").strip()

    if "status" in data:
        if data["status"] not in Task.STATUSES:
            return None, f"Status must be one of: {', '.join(Task.STATUSES)}."
        clean["status"] = data["status"]

    if "priority" in data:
        if data["priority"] not in Task.PRIORITIES:
            return None, f"Priority must be one of: {', '.join(Task.PRIORITIES)}."
        clean["priority"] = data["priority"]

    if "category" in data:
        if data["category"] not in Task.CATEGORIES:
            return None, f"Category must be one of: {', '.join(Task.CATEGORIES)}."
        clean["category"] = data["category"]

    if "due_date" in data:
        value = data.get("due_date")
        if value:
            try:
                clean["due_date"] = date.fromisoformat(value)
            except (TypeError, ValueError):
                return None, "Due date must be in YYYY-MM-DD format."
        else:
            clean["due_date"] = None

    if "assigned_to" in data:
        value = data.get("assigned_to")
        if value in (None, ""):
            clean["assigned_to"] = None
        else:
            try:
                user_id = int(value)
            except (TypeError, ValueError):
                return None, "assigned_to must be a user id."
            if not db.session.get(User, user_id):
                return None, "Assigned user does not exist."
            clean["assigned_to"] = user_id

    return clean, None


# ---------------- READ (admin + user) ----------------

@tasks_bp.get("/tasks")
@scope_required("tasks:read")
def list_tasks():
    query = Task.query
    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)
    category = request.args.get("category")
    if category:
        query = query.filter_by(category=category)
    tasks = query.order_by(Task.due_date.is_(None), Task.due_date, Task.id).all()
    return jsonify([t.to_dict() for t in tasks]), 200


@tasks_bp.get("/tasks/<int:task_id>")
@scope_required("tasks:read")
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify(error="not_found", message="Task not found."), 404
    return jsonify(task.to_dict()), 200


# ---------------- WRITE / EDIT / DELETE (admin only) ----------------

@tasks_bp.post("/tasks")
@scope_required("tasks:write")
def create_task():
    clean, error = _validate(request.get_json(silent=True) or {})
    if error:
        return jsonify(error="validation_error", message=error), 400

    task = Task(**clean, created_by=int(get_jwt_identity()))
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@tasks_bp.put("/tasks/<int:task_id>")
@scope_required("tasks:write")
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify(error="not_found", message="Task not found."), 404

    clean, error = _validate(request.get_json(silent=True) or {}, partial=True)
    if error:
        return jsonify(error="validation_error", message=error), 400

    for field, value in clean.items():
        setattr(task, field, value)
    db.session.commit()
    return jsonify(task.to_dict()), 200


@tasks_bp.delete("/tasks/<int:task_id>")
@scope_required("tasks:write")
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify(error="not_found", message="Task not found."), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify(message="Task deleted."), 200
