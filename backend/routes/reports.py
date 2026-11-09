"""Reports (admin only, scope reports:read).

GET /api/reports/summary   totals, breakdowns by priority and by assignee, overdue list
"""

from datetime import date, timedelta

from flask import Blueprint, jsonify
from sqlalchemy import func

from decorators import scope_required
from extensions import db
from models import Task, User

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@reports_bp.get("/summary")
@scope_required("reports:read")
def summary():
    today = date.today()
    week_end = today + timedelta(days=7)
    open_task = Task.status != "done"

    # --- Totals ---
    by_status = dict(db.session.query(Task.status, func.count(Task.id)).group_by(Task.status).all())
    total = sum(by_status.values())
    overdue_q = Task.query.filter(open_task, Task.due_date < today)
    totals = {
        "total": total,
        "todo": by_status.get("todo", 0),
        "in_progress": by_status.get("in_progress", 0),
        "done": by_status.get("done", 0),
        "overdue": overdue_q.count(),
        "due_this_week": Task.query.filter(open_task, Task.due_date >= today, Task.due_date <= week_end).count(),
        "unassigned": Task.query.filter(Task.assigned_to.is_(None)).count(),
        "completion_rate": round(by_status.get("done", 0) * 100 / total) if total else 0,
    }

    # --- Priority x status ---
    rows = db.session.query(Task.priority, Task.status, func.count(Task.id)).group_by(Task.priority, Task.status).all()
    by_priority = {p: {"priority": p, "todo": 0, "in_progress": 0, "done": 0} for p in Task.PRIORITIES}
    for priority, status, n in rows:
        by_priority[priority][status] = n

    # --- Per category ---
    rows = db.session.query(Task.category, Task.status, func.count(Task.id)).group_by(Task.category, Task.status).all()
    by_category = {c: {"category": c, "todo": 0, "in_progress": 0, "done": 0} for c in Task.CATEGORIES}
    for category, status, n in rows:
        by_category[category][status] = n

    # --- Per assignee ---
    rows = (
        db.session.query(User.username, Task.status, func.count(Task.id))
        .select_from(Task)
        .outerjoin(User, User.id == Task.assigned_to)
        .group_by(User.username, Task.status)
        .all()
    )
    overdue_by_user = dict(
        db.session.query(User.username, func.count(Task.id))
        .select_from(Task)
        .outerjoin(User, User.id == Task.assigned_to)
        .filter(open_task, Task.due_date < today)
        .group_by(User.username)
        .all()
    )
    people = {}
    for username, status, n in rows:
        name = username or "Unassigned"
        person = people.setdefault(name, {"username": name, "todo": 0, "in_progress": 0, "done": 0, "total": 0})
        person[status] += n
        person["total"] += n
    for username, n in overdue_by_user.items():
        people[username or "Unassigned"]["overdue"] = n
    by_assignee = sorted(people.values(), key=lambda p: (-p["total"], p["username"]))
    for p in by_assignee:
        p.setdefault("overdue", 0)

    overdue = [t.to_dict() for t in overdue_q.order_by(Task.due_date).all()]

    return jsonify(
        totals=totals,
        by_priority=list(by_priority.values()),
        by_category=list(by_category.values()),
        by_assignee=by_assignee,
        overdue=overdue,
        generated_at=today.isoformat(),
    ), 200
