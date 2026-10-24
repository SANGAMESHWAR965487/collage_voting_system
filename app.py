import os
import secrets

from dotenv import load_dotenv
from flask import Flask, render_template
from pymongo.errors import PyMongoError

load_dotenv()

from blockchain import Blockchain
from controllers.admin import admin_controller
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
UPLOAD_FOLDER = "static/uploads/candidates"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
LOCKOUT_TIME = 120


def create_app(test_config=None):
    load_dotenv()
    is_production = os.getenv("FLASK_ENV", "development").lower() == "production"
    secret_key = os.getenv("SECRET_KEY")
    if is_production and not secret_key:
        raise RuntimeError("SECRET_KEY must be configured in production")

    application = Flask(__name__)
    application.secret_key = secret_key or secrets.token_hex(32)
    application.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=is_production,
        UPLOAD_FOLDER=UPLOAD_FOLDER,
        ADMIN_ID=ADMIN_ID,
        ADMIN_PHONE=ADMIN_PHONE,
        ADMIN_PASSWORD=ADMIN_PASSWORD,
    )
    if test_config:
        application.config.update(test_config)
    application.extensions["blockchain"] = Blockchain.load()
    os.makedirs(application.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs("static/uploads/users", exist_ok=True)

    @application.errorhandler(MongoConnectionError)
    def mongo_connection_error(error):
        application.logger.error("MongoDB connection failed")
        return render_template(
            "login.html",
            message="The service is temporarily unavailable. Please try again later.",
        ), 503

    @application.errorhandler(PyMongoError)
    def mongo_operation_error(error):
        application.logger.error("MongoDB operation failed")
        return render_template(
            "login.html",
            message="The service is temporarily unavailable. Please try again later.",
        ), 503

    application.register_blueprint(auth_controller)
    application.register_blueprint(admin_controller)
    application.register_blueprint(results_controller)
    application.register_blueprint(voting_controller)
    application.register_blueprint(blockchain_controller)
    return application


app = create_app()
blockchain = app.extensions["blockchain"]

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
