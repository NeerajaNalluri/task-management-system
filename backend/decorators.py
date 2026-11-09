from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from extensions import db
from models import User


def scope_required(*required_scopes):
    """Allow the request only if the access token contains ALL the given scopes.

    Usage:
        @scope_required("tasks:read")
        @scope_required("tasks:write")
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()  # valid signature, not expired, not revoked

            if not db.session.get(User, int(get_jwt_identity())):
                return jsonify(error="invalid_token", message="This account no longer exists."), 401

            granted = set(get_jwt().get("scope", "").split())
            missing = set(required_scopes) - granted
            if missing:
                resp = jsonify(
                    error="insufficient_scope",
                    message="You do not have permission for this action.",
                    required_scope=" ".join(sorted(required_scopes)),
                )
                resp.status_code = 403
                resp.headers["WWW-Authenticate"] = (
                    f'Bearer error="insufficient_scope", scope="{" ".join(sorted(required_scopes))}"'
                )
                return resp
            return fn(*args, **kwargs)

        return wrapper

    return decorator
