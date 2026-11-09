"""OAuth 2.0 building blocks: scopes, client authentication, error responses."""

import base64
from urllib.parse import unquote

from flask import jsonify, request

from models import OAuthClient

# ---- Scopes: what a token is allowed to do ----
SCOPES = {
    "tasks:read": "View tasks",
    "tasks:write": "Create, edit and delete tasks",
    "users:manage": "Add, edit and delete user accounts",
    "reports:read": "View reports",
}

# Which scopes each role may receive
ROLE_SCOPES = {
    "admin": set(SCOPES),
    "user": {"tasks:read"},
}


def grant_scopes(requested, role, client):
    """Scopes to put in the token = what was asked for ∩ what the role allows ∩ what the client allows.

    If nothing was asked for, give everything the role and client allow.
    Returns (scope_set, error_description).
    """
    allowed = ROLE_SCOPES.get(role, set()) & client.scope_set()
    if not requested:
        return allowed, None

    asked = set(requested.split())
    unknown = asked - set(SCOPES)
    if unknown:
        return None, f"Unknown scope: {', '.join(sorted(unknown))}."
    granted = asked & allowed
    if not granted:
        return None, "None of the requested scopes are allowed for this account."
    return granted, None


def oauth_error(error, description, status=400, headers=None):
    """Error body in the format defined by RFC 6749 section 5.2."""
    resp = jsonify(error=error, error_description=description)
    resp.status_code = status
    resp.headers["Cache-Control"] = "no-store"
    for k, v in (headers or {}).items():
        resp.headers[k] = v
    return resp


def _basic_auth_credentials():
    """Read client_id/secret from an 'Authorization: Basic ...' header, if present."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return None, None
    try:
        decoded = base64.b64decode(header[6:]).decode("utf-8")
        client_id, _, secret = decoded.partition(":")
        return unquote(client_id), unquote(secret)
    except (ValueError, UnicodeDecodeError):
        return None, None


def authenticate_client(data):
    """Find and verify the calling client. Returns (client, error_response)."""
    client_id, secret = _basic_auth_credentials()
    if not client_id:
        client_id = data.get("client_id")
        secret = data.get("client_secret")

    if not client_id:
        return None, oauth_error("invalid_client", "client_id is required.", 401)

    client = OAuthClient.query.filter_by(client_id=client_id).first()
    if not client:
        return None, oauth_error("invalid_client", "Unknown client.", 401)

    if not client.is_public and not client.check_secret(secret):
        return None, oauth_error(
            "invalid_client", "Client authentication failed.", 401, {"WWW-Authenticate": 'Basic realm="token"'}
        )
    return client, None
