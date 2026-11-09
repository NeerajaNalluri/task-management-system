import os

from flask import Flask, jsonify, send_from_directory

from config import Config
from extensions import db, jwt
from models import TokenBlocklist
from routes.auth import auth_bp
from routes.reports import reports_bp
from routes.tasks import tasks_bp
from routes.users import users_bp

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)

    db.init_app(app)
    jwt.init_app(app)

    # ---- Token checks ----
    @jwt.token_in_blocklist_loader
    def is_token_revoked(_header, payload):
        return db.session.query(TokenBlocklist.id).filter_by(jti=payload["jti"]).scalar() is not None

    @jwt.expired_token_loader
    def expired(_header, _payload):
        return jsonify(error="token_expired", message="Your session has expired."), 401

    @jwt.invalid_token_loader
    def invalid(reason):
        return jsonify(error="invalid_token", message=reason), 401

    @jwt.unauthorized_loader
    def missing(reason):
        return jsonify(error="authorization_required", message=reason), 401

    @jwt.revoked_token_loader
    def revoked(_header, _payload):
        return jsonify(error="token_revoked", message="You have been logged out."), 401

    # ---- API routes ----
    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(reports_bp)

    # ---- Frontend (served by Flask so everything runs on one port) ----
    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<path:filename>")
    def frontend_files(filename):
        return send_from_directory(FRONTEND_DIR, filename)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
