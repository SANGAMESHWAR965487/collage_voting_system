import os
import secrets

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from pymongo.errors import PyMongoError

load_dotenv()

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BACKEND_DIR, "..", "frontend"))
FRONTEND_STATIC_DIR = os.path.join(FRONTEND_DIR, "static")

from blockchain import Blockchain
from controllers.admin import admin_controller
from controllers.api import api
from controllers.auth import (
    MAX_LOGIN_ATTEMPTS,
    MAX_OTP_RESENDS,
    OTP_LIFETIME_SECONDS,
    OTP_RESEND_COOLDOWN_SECONDS,
    _otp_digest,
    _send_otp_email,
    _start_otp_login,
    hash_password,
    sanitize_input,
    auth_controller,
)
from controllers.blockchain import blockchain_controller
from controllers.results import results_controller
from controllers.voting import ALLOWED_POSITIONS, allowed_file, voting_controller
from database.mongo_db import MongoConnectionError

IS_PRODUCTION = os.getenv("FLASK_ENV", "development").lower() == "production"
ADMIN_ID = os.getenv("ADMIN_ID", "")
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
UPLOAD_FOLDER = os.path.join(BACKEND_DIR, "uploads", "candidates")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
LOCKOUT_TIME = 120


def create_app(test_config=None):
    load_dotenv()
    is_production = os.getenv("FLASK_ENV", "development").lower() == "production"
    frontend_origins = {
        origin.strip().rstrip("/")
        for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
        if origin.strip()
    }
    secret_key = os.getenv("SECRET_KEY")
    if is_production and not secret_key:
        raise RuntimeError("SECRET_KEY must be configured in production")

    application = Flask(
        __name__,
        template_folder=os.path.join(FRONTEND_DIR, "templates"),
        static_folder=FRONTEND_STATIC_DIR,
    )
    application.secret_key = secret_key or secrets.token_hex(32)
    application.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=is_production,
        SESSION_COOKIE_SAMESITE="None" if is_production else "Lax",
        UPLOAD_FOLDER=UPLOAD_FOLDER,
        FRONTEND_ORIGINS=frontend_origins,
        ADMIN_ID=ADMIN_ID,
        ADMIN_PHONE=ADMIN_PHONE,
        ADMIN_PASSWORD=ADMIN_PASSWORD,
    )
    if test_config:
        application.config.update(test_config)
    application.extensions["blockchain"] = Blockchain.load()
    os.makedirs(application.config["UPLOAD_FOLDER"], exist_ok=True)

    @application.errorhandler(MongoConnectionError)
    def mongo_connection_error(error):
        application.logger.error("MongoDB connection failed")
        if request.path.startswith("/api/"):
            return jsonify({
                "success": False,
                "message": "The database service is temporarily unavailable.",
            }), 503
        return render_template(
            "login.html",
            message="The service is temporarily unavailable. Please try again later.",
        ), 503

    @application.errorhandler(PyMongoError)
    def mongo_operation_error(error):
        application.logger.error("MongoDB operation failed")
        if request.path.startswith("/api/"):
            return jsonify({
                "success": False,
                "message": "The database service is temporarily unavailable.",
            }), 503
        return render_template(
            "login.html",
            message="The service is temporarily unavailable. Please try again later.",
        ), 503

    application.register_blueprint(auth_controller)
    application.register_blueprint(api)
    application.register_blueprint(admin_controller)
    application.register_blueprint(results_controller)
    application.register_blueprint(voting_controller)
    application.register_blueprint(blockchain_controller)

    @application.before_request
    def validate_api_origin():
        if not request.path.startswith("/api/"):
            return None
        origin = request.headers.get("Origin", "").rstrip("/")
        if request.method == "OPTIONS":
            if origin in application.config["FRONTEND_ORIGINS"]:
                return "", 204
            return jsonify({"success": False, "message": "Origin is not allowed."}), 403
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if not origin or origin not in application.config["FRONTEND_ORIGINS"]:
                return jsonify({"success": False, "message": "Origin is not allowed."}), 403
        return None

    @application.after_request
    def add_api_cors_headers(response):
        origin = request.headers.get("Origin", "").rstrip("/")
        if (
            request.path.startswith("/api/")
            and origin
            and origin in application.config["FRONTEND_ORIGINS"]
        ):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers.add("Vary", "Origin")
        return response

    return application


app = create_app()
blockchain = app.extensions["blockchain"]

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
