"""OAuth 2.0 authorization endpoints.

POST /api/auth/token    grant_type=password       -> username + password  => access & refresh token
                        grant_type=refresh_token  -> refresh token        => new access & refresh token
POST /api/auth/revoke   (RFC 7009) revoke an access or refresh token
POST /api/auth/logout   revoke the token in the Authorization header (+ optional refresh_token)
GET  /api/auth/me       who am I, and which scopes my token has

Every /token and /revoke call must identify the client app with client_id
(and client_secret for confidential clients).
"""

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from jwt.exceptions import PyJWTError

from extensions import db
from models import TokenBlocklist, User
from oauth import ROLE_SCOPES, authenticate_client, grant_scopes, oauth_error

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _request_data():
    # OAuth clients normally send form data; JSON is accepted too.
    return request.form if request.form else (request.get_json(silent=True) or {})


def _is_revoked(jti):
    return db.session.query(TokenBlocklist.id).filter_by(jti=jti).scalar() is not None


def _revoke(jti):
    if jti and not _is_revoked(jti):
        db.session.add(TokenBlocklist(jti=jti))


def _issue_tokens(user, client, scopes):
    claims = {
        "role": user.role,
        "username": user.username,
        "scope": " ".join(sorted(scopes)),
        "client_id": client.client_id,
    }
    body = {
        "access_token": create_access_token(identity=str(user.id), additional_claims=claims),
        "token_type": "Bearer",
        "expires_in": int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds()),
        "scope": claims["scope"],
        "user": user.to_dict(),
    }
    if client.allows_grant("refresh_token"):
        body["refresh_token"] = create_refresh_token(identity=str(user.id), additional_claims=claims)

    resp = jsonify(body)
    resp.headers["Cache-Control"] = "no-store"  # required by RFC 6749 for token responses
    resp.headers["Pragma"] = "no-cache"
    return resp


# ---------------- /token ----------------

@auth_bp.post("/token")
def token():
    data = _request_data()

    client, error = authenticate_client(data)
    if error:
        return error

    grant_type = data.get("grant_type")
    if not grant_type:
        return oauth_error("invalid_request", "grant_type is required.")
    if grant_type not in ("password", "refresh_token"):
        return oauth_error("unsupported_grant_type", f"grant_type '{grant_type}' is not supported.")
    if not client.allows_grant(grant_type):
        return oauth_error("unauthorized_client", f"This client may not use grant_type '{grant_type}'.")

    if grant_type == "password":
        return _password_grant(data, client)
    return _refresh_grant(data, client)


def _password_grant(data, client):
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    portal = data.get("portal")  # our extension: which login tab was used ("admin"/"user")

    if not username or not password:
        return oauth_error("invalid_request", "Username and password are required.")

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return oauth_error("invalid_grant", "Invalid username or password.")

    if portal and portal != user.role:
        return oauth_error("invalid_grant", f"This account cannot sign in through the {portal} login.")

    scopes, error = grant_scopes(data.get("scope"), user.role, client)
    if error:
        return oauth_error("invalid_scope", error)

    return _issue_tokens(user, client, scopes)


def _refresh_grant(data, client):
    raw = data.get("refresh_token")
    if not raw:
        return oauth_error("invalid_request", "refresh_token is required.")

    try:
        payload = decode_token(raw)
    except PyJWTError:
        return oauth_error("invalid_grant", "Refresh token is invalid or expired.")
    except Exception:  # flask-jwt-extended raises its own errors for bad tokens
        return oauth_error("invalid_grant", "Refresh token is invalid or expired.")

    if payload.get("type") != "refresh":
        return oauth_error("invalid_grant", "That is not a refresh token.")
    if payload.get("client_id") != client.client_id:
        return oauth_error("invalid_grant", "Refresh token was issued to a different client.")
    if _is_revoked(payload["jti"]):
        return oauth_error("invalid_grant", "Refresh token has been revoked.")

    user = db.session.get(User, int(payload["sub"]))
    if not user:
        return oauth_error("invalid_grant", "User no longer exists.")

    # New scopes may not exceed the original ones, and are re-checked against the
    # user's CURRENT role (so a demoted admin loses write access on next refresh).
    original = set(payload.get("scope", "").split())
    allowed = original & ROLE_SCOPES.get(user.role, set()) & client.scope_set()
    requested = data.get("scope")
    if requested:
        asked = set(requested.split())
        if not asked <= original:
            return oauth_error("invalid_scope", "Cannot request scopes beyond the original grant.")
        allowed &= asked
    if not allowed:
        return oauth_error("invalid_grant", "This account no longer has access.")

    # Refresh token rotation: the old refresh token can't be used again.
    _revoke(payload["jti"])
    db.session.commit()
    return _issue_tokens(user, client, allowed)


# ---------------- /revoke (RFC 7009) ----------------

@auth_bp.post("/revoke")
def revoke():
    data = _request_data()
    client, error = authenticate_client(data)
    if error:
        return error

    raw = data.get("token")
    if not raw:
        return oauth_error("invalid_request", "token is required.")

    try:
        payload = decode_token(raw, allow_expired=True)
        if payload.get("client_id") in (None, client.client_id):
            _revoke(payload["jti"])
            db.session.commit()
    except Exception:
        pass  # RFC 7009: invalid tokens are not an error for the caller
    return jsonify(message="Token revoked."), 200


# ---------------- /logout ----------------

@auth_bp.post("/logout")
@jwt_required(verify_type=False)
def logout():
    _revoke(get_jwt()["jti"])
    raw_refresh = (_request_data() or {}).get("refresh_token")
    if raw_refresh:
        try:
            _revoke(decode_token(raw_refresh, allow_expired=True)["jti"])
        except Exception:
            pass
    db.session.commit()
    return jsonify(message="Logged out."), 200


# ---------------- /me ----------------

@auth_bp.get("/me")
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        return jsonify(error="not_found", message="User no longer exists."), 404
    return jsonify({**user.to_dict(), "scope": get_jwt().get("scope", "")}), 200
