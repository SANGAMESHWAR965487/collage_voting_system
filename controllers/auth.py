import hashlib
import hmac
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session
from werkzeug.security import generate_password_hash

from database.mongo_db import (
    delete_otp,
    get_otp,
    get_user_email,
    increment_otp_attempts,
    is_login_rate_limited,
    is_user_approved,
    record_failed_login,
    register_user,
    reset_login_attempts,
    store_otp,
    user_exists,
    validate_login,
)

auth_controller = Blueprint("auth", __name__)

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME = 120
OTP_LIFETIME_SECONDS = 300
OTP_RESEND_COOLDOWN_SECONDS = 60
MAX_OTP_RESENDS = 3


def sanitize_input(input_str):
    return "" if input_str is None else str(input_str).strip()


def hash_password(password):
    return generate_password_hash(password)


def _otp_digest(rollno, otp):
    message = f"{rollno}:{otp}".encode()
    return hmac.new(current_app.secret_key.encode(), message, hashlib.sha256).hexdigest()


def _send_otp_email(recipient, otp):
    username = os.getenv("MAIL_USERNAME", "").strip()
    mail_password = os.getenv("MAIL_PASSWORD", "")
    sender = os.getenv("MAIL_DEFAULT_SENDER", "").strip() or username
    if not username or not mail_password or not sender:
        return False

    message = EmailMessage()
    message["Subject"] = "Your College Voting System OTP"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "Hello,\n\n"
        "Your OTP for logging into the College Voting System is:\n\n"
        f"{otp}\n\n"
        "This OTP is valid for 5 minutes.\n\n"
        "If you did not request this OTP, please ignore this email.\n\n"
        "Do not share this OTP with anyone."
    )

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as smtp:
        smtp.starttls()
        smtp.login(username, mail_password)
        smtp.send_message(message)
    return True


def _start_otp_login(rollno, mobile, password):
    user = validate_login(rollno, mobile, password)
    if not user or not is_user_approved(rollno):
        return False, "Invalid credentials or account is not approved"
    session.clear()
    recipient = (user.get("email") or "").strip()
    if not recipient:
        return False, "We could not send a verification code. Contact the administrator."
    if not os.getenv("MAIL_USERNAME") or not os.getenv("MAIL_PASSWORD"):
        return False, "Email verification is not configured. Contact the administrator."

    now = datetime.now(timezone.utc)
    previous_record = get_otp(rollno)
    resend_count = 0
    if previous_record and previous_record.get("expires_at", now) > now:
        resend_count = previous_record.get("resend_count", 0)
        seconds_since_last_send = int(
            (now - previous_record.get("sent_at", now)).total_seconds()
        )
        if seconds_since_last_send < OTP_RESEND_COOLDOWN_SECONDS:
            session["pending_rollno"] = rollno
            return False, (
                f"Please wait {OTP_RESEND_COOLDOWN_SECONDS - seconds_since_last_send} "
                "seconds before requesting another code."
            )
        if resend_count >= MAX_OTP_RESENDS:
            session["pending_rollno"] = rollno
            return False, "The resend limit has been reached. Please log in again."
        resend_count += 1

    otp = f"{secrets.randbelow(900000) + 100000:06d}"
    store_otp(
        rollno,
        _otp_digest(rollno, otp),
        now + timedelta(seconds=OTP_LIFETIME_SECONDS),
        sent_at=now,
        resend_count=resend_count,
    )
    try:
        if not _send_otp_email(recipient, otp):
            delete_otp(rollno)
            return False, "Email verification is not configured. Contact the administrator."
    except (OSError, smtplib.SMTPException, ValueError):
        delete_otp(rollno)
        current_app.logger.error("OTP email delivery failed")
        return False, "Could not send the verification email. Please try again later."

    session["pending_rollno"] = rollno
    return True, "A verification code has been sent to the email registered to your account."


@auth_controller.route("/")
def home():
    return render_template("login.html")


@auth_controller.route("/send_otp", methods=["POST"])
def send_otp():
    data = request.get_json(silent=True) or {}
    rollno = sanitize_input(data.get("rollno", request.form.get("rollno", "")))
    mobile = sanitize_input(data.get("mobile", request.form.get("mobile", "")))
    password = data.get("password", request.form.get("password", ""))
    if is_login_rate_limited(rollno, MAX_LOGIN_ATTEMPTS):
        return jsonify({"success": False, "message": "Too many attempts. Try again later."}), 429

    success, message = _start_otp_login(rollno, mobile, password)
    if success:
        reset_login_attempts(rollno)
    else:
        record_failed_login(rollno, LOCKOUT_TIME)
    return jsonify({"success": success, "message": message}), (200 if success else 401)


@auth_controller.route("/verify_otp", methods=["POST"])
def verify_otp():
    data = request.get_json(silent=True) or request.form
    rollno = session.get("pending_rollno")
    otp = sanitize_input(data.get("otp", ""))
    record = get_otp(rollno) if rollno else None
    if not record or record.get(
        "expires_at", datetime.min.replace(tzinfo=timezone.utc)
    ) <= datetime.now(timezone.utc):
        if rollno:
            delete_otp(rollno)
        session.pop("pending_rollno", None)
        if request.is_json:
            return jsonify({"success": False, "message": "OTP expired or not requested"}), 400
        return render_template("login.html", message="OTP expired. Please log in again.")

    if record.get("attempts", 0) >= MAX_LOGIN_ATTEMPTS:
        delete_otp(rollno)
        session.pop("pending_rollno", None)
        message = "Too many incorrect OTP attempts. Please log in again."
    elif len(otp) == 6 and otp.isdigit() and hmac.compare_digest(
        record["otp_hash"], _otp_digest(rollno, otp)
    ):
        delete_otp(rollno)
        reset_login_attempts(rollno)
        session.clear()
        session["rollno"] = rollno
        if request.is_json:
            return jsonify({"success": True, "message": "OTP verified"})
        return redirect("/vote")
    else:
        increment_otp_attempts(rollno)
        if record.get("attempts", 0) + 1 >= MAX_LOGIN_ATTEMPTS:
            delete_otp(rollno)
            session.pop("pending_rollno", None)
            message = "Too many incorrect OTP attempts. Please log in again."
        else:
            message = "Invalid OTP"

    if request.is_json:
        return jsonify({"success": False, "message": message}), 401
    return render_template("login.html", message=message, otp_pending=True)


@auth_controller.route("/resend_otp", methods=["POST"])
def resend_otp():
    rollno = session.get("pending_rollno")
    record = get_otp(rollno) if rollno else None
    now = datetime.now(timezone.utc)
    if not record or record.get(
        "expires_at", datetime.min.replace(tzinfo=timezone.utc)
    ) <= now:
        if rollno:
            delete_otp(rollno)
        session.pop("pending_rollno", None)
        return render_template(
            "login.html",
            message="Your verification request expired. Please log in again.",
        )

    sent_at = record.get("sent_at", now)
    cooldown_remaining = OTP_RESEND_COOLDOWN_SECONDS - int(
        (now - sent_at).total_seconds()
    )
    if cooldown_remaining > 0:
        return render_template(
            "login.html",
            message=f"Please wait {cooldown_remaining} seconds before requesting another code.",
            otp_pending=True,
        ), 429
    if record.get("resend_count", 0) >= MAX_OTP_RESENDS:
        return render_template(
            "login.html",
            message="The resend limit has been reached. Please log in again.",
            otp_pending=True,
        ), 429

    recipient = (get_user_email(rollno) or "").strip()
    if not recipient:
        delete_otp(rollno)
        session.pop("pending_rollno", None)
        return render_template(
            "login.html",
            message="We could not send a verification code. Contact the administrator.",
        )

    otp = f"{secrets.randbelow(900000) + 100000:06d}"
    resend_count = record.get("resend_count", 0) + 1
    store_otp(
        rollno,
        _otp_digest(rollno, otp),
        now + timedelta(seconds=OTP_LIFETIME_SECONDS),
        sent_at=now,
        resend_count=resend_count,
    )
    try:
        if not _send_otp_email(recipient, otp):
            delete_otp(rollno)
            session.pop("pending_rollno", None)
            return render_template(
                "login.html",
                message="Email verification is not configured. Contact the administrator.",
            )
    except (OSError, smtplib.SMTPException, ValueError):
        delete_otp(rollno)
        session.pop("pending_rollno", None)
        current_app.logger.error("OTP resend email delivery failed")
        return render_template(
            "login.html",
            message="Could not send the verification email. Please log in again.",
        )

    return render_template(
        "login.html",
        message="A new verification code has been sent to the email registered to your account.",
        otp_pending=True,
        success_message=True,
    )


@auth_controller.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = sanitize_input(request.form["name"])
        rollno = sanitize_input(request.form["rollno"])
        mobile = sanitize_input(request.form["mobile"])
        email = sanitize_input(request.form["email"])
        password = request.form["password"]

        if len(name) < 2 or len(rollno) < 3 or len(password) < 8:
            return render_template("register.html", message="Invalid input length")
        if user_exists(rollno):
            return render_template("register.html", message="User already registered")
        if not register_user(
            name, rollno, mobile, email, hash_password(password), approved=False
        ):
            return render_template("register.html", message="User already registered")
        return render_template(
            "register.html",
            message="Registration successful! Please wait for admin approval.",
        )
    return render_template("register.html")


@auth_controller.route("/login", methods=["POST"])
def login():
    rollno = sanitize_input(request.form["rollno"])
    mobile = sanitize_input(request.form.get("mobile", ""))
    password = request.form.get("password", "")
    if is_login_rate_limited(rollno, MAX_LOGIN_ATTEMPTS):
        return render_template(
            "login.html", message="Too many attempts. Please try again later."
        )

    if (
        current_app.config["ADMIN_ID"]
        and current_app.config["ADMIN_PHONE"]
        and current_app.config["ADMIN_PASSWORD"]
        and hmac.compare_digest(rollno.lower(), current_app.config["ADMIN_ID"].lower())
        and hmac.compare_digest(mobile, current_app.config["ADMIN_PHONE"])
        and hmac.compare_digest(password, current_app.config["ADMIN_PASSWORD"])
    ):
        session.clear()
        session["admin"] = True
        reset_login_attempts(rollno)
        return redirect("/admin")

    success, message = _start_otp_login(rollno, mobile, password)
    if not success:
        record_failed_login(rollno, LOCKOUT_TIME)
        return render_template(
            "login.html",
            message=message,
            otp_pending=session.get("pending_rollno") == rollno,
        )
    reset_login_attempts(rollno)
    return render_template(
        "login.html", message=message, otp_pending=True, success_message=True
    )


@auth_controller.route("/logout")
def logout():
    session.clear()
    return redirect("/")
