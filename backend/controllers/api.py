import hmac
import secrets
import smtplib
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request, session

from controllers.auth import (
    LOCKOUT_TIME,
    MAX_LOGIN_ATTEMPTS,
    MAX_OTP_RESENDS,
    OTP_LIFETIME_SECONDS,
    OTP_RESEND_COOLDOWN_SECONDS,
    _otp_digest,
    _send_otp_email,
    _start_otp_login,
    hash_password,
    sanitize_input,
)
from database.mongo_db import (
    add_candidate,
    approve_user_by_rollno,
    cast_ballot,
    clear_all_candidates,
    delete_otp,
    delete_user,
    get_all_users,
    get_candidates_by_position,
    get_otp,
    get_pending_users,
    get_results,
    get_setting,
    get_user_by_rollno,
    get_user_email,
    has_voted,
    increment_otp_attempts,
    is_login_rate_limited,
    is_user_approved,
    is_valid_candidate,
    record_failed_login,
    register_user,
    reset_login_attempts,
    store_otp,
    update_setting,
    user_exists,
)

api = Blueprint("api", __name__, url_prefix="/api")
POSITIONS = ("President", "Vice President", "Secretary", "Treasury")


def _error(message, status=400):
    return jsonify({"success": False, "message": message}), status


def _student():
    rollno = session.get("rollno")
    if not rollno:
        return None
    user = get_user_by_rollno(rollno)
    if not user or not is_user_approved(rollno):
        session.clear()
        return None
    return user


def _plain_candidate(candidate):
    candidate = dict(candidate)
    candidate.pop("_id", None)
    return candidate


@api.get("/session")
def session_state():
    user = _student() if session.get("rollno") else None
    return jsonify({
        "authenticated": bool(user or session.get("admin")),
        "admin": bool(session.get("admin")),
        "pending_otp": bool(session.get("pending_rollno")),
        "user": user,
    })


@api.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    name = sanitize_input(data.get("name"))
    rollno = sanitize_input(data.get("rollno"))
    mobile = sanitize_input(data.get("mobile"))
    email = sanitize_input(data.get("email"))
    password = data.get("password", "")
    if len(name) < 2 or len(rollno) < 3 or len(password) < 8:
        return _error("Name, roll number, or password is invalid.")
    if user_exists(rollno) or not register_user(
        name, rollno, mobile, email, hash_password(password), approved=False
    ):
        return _error("User already registered.", 409)
    return jsonify({
        "success": True,
        "message": "Registration successful! Please wait for admin approval.",
    }), 201


@api.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    rollno = sanitize_input(data.get("rollno"))
    mobile = sanitize_input(data.get("mobile"))
    password = data.get("password", "")
    if is_login_rate_limited(rollno, MAX_LOGIN_ATTEMPTS):
        return _error("Too many attempts. Please try again later.", 429)

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
        return jsonify({"success": True, "admin": True})

    success, message = _start_otp_login(rollno, mobile, password)
    if success:
        reset_login_attempts(rollno)
        return jsonify({"success": True, "message": message, "pending_otp": True})
    record_failed_login(rollno, LOCKOUT_TIME)
    return _error(message, 401)


@api.post("/verify-otp")
def verify_otp():
    data = request.get_json(silent=True) or {}
    rollno = session.get("pending_rollno")
    otp = sanitize_input(data.get("otp"))
    record = get_otp(rollno) if rollno else None
    now = datetime.now(timezone.utc)
    if not record or record.get(
        "expires_at", datetime.min.replace(tzinfo=timezone.utc)
    ) <= now:
        if rollno:
            delete_otp(rollno)
        session.pop("pending_rollno", None)
        return _error("OTP expired or not requested.", 400)
    if record.get("attempts", 0) >= MAX_LOGIN_ATTEMPTS:
        delete_otp(rollno)
        session.pop("pending_rollno", None)
        return _error("Too many incorrect OTP attempts. Please log in again.", 429)
    if len(otp) != 6 or not otp.isdigit() or not hmac.compare_digest(
        record["otp_hash"], _otp_digest(rollno, otp)
    ):
        increment_otp_attempts(rollno)
        if record.get("attempts", 0) + 1 >= MAX_LOGIN_ATTEMPTS:
            delete_otp(rollno)
            session.pop("pending_rollno", None)
            return _error("Too many incorrect OTP attempts. Please log in again.", 429)
        return _error("Invalid OTP.", 401)

    delete_otp(rollno)
    reset_login_attempts(rollno)
    session.clear()
    session["rollno"] = rollno
    return jsonify({"success": True, "message": "OTP verified."})


@api.post("/resend-otp")
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
        return _error("Your verification request expired. Please log in again.", 400)
    cooldown = OTP_RESEND_COOLDOWN_SECONDS - int(
        (now - record.get("sent_at", now)).total_seconds()
    )
    if cooldown > 0:
        return _error(f"Please wait {cooldown} seconds before requesting another code.", 429)
    if record.get("resend_count", 0) >= MAX_OTP_RESENDS:
        return _error("The resend limit has been reached. Please log in again.", 429)
    recipient = (get_user_email(rollno) or "").strip()
    if not recipient:
        delete_otp(rollno)
        session.pop("pending_rollno", None)
        return _error("We could not send a verification code. Contact the administrator.", 400)

    otp = f"{secrets.randbelow(900000) + 100000:06d}"
    store_otp(
        rollno,
        _otp_digest(rollno, otp),
        now + timedelta(seconds=OTP_LIFETIME_SECONDS),
        sent_at=now,
        resend_count=record.get("resend_count", 0) + 1,
    )
    try:
        if not _send_otp_email(recipient, otp):
            delete_otp(rollno)
            return _error("Email verification is not configured.", 503)
    except (OSError, smtplib.SMTPException, ValueError):
        delete_otp(rollno)
        current_app.logger.error("OTP resend email delivery failed")
        return _error("Could not send the verification email. Please try again later.", 503)
    return jsonify({"success": True, "message": "A new verification code has been sent."})


@api.post("/logout")
def logout():
    session.clear()
    return jsonify({"success": True})


@api.get("/vote")
def vote_data():
    user = _student()
    if not user:
        return _error("Please log in.", 401)
    candidates = {
        position: [
            _plain_candidate(candidate)
            for candidate in get_candidates_by_position(position)
        ]
        for position in POSITIONS
    }
    return jsonify({
        "user": user,
        "voting_open": get_setting("voting_open") == "true",
        "has_voted": has_voted(user["rollno"]),
        "candidates": candidates,
    })


@api.post("/vote")
def submit_vote():
    user = _student()
    if not user:
        return _error("Please log in.", 401)
    if get_setting("voting_open") != "true":
        return _error("Voting is currently closed.", 403)
    if has_voted(user["rollno"]):
        return _error("You have already voted.", 409)
    data = request.get_json(silent=True) or {}
    choices = {position: data.get(position) for position in POSITIONS}
    if any(not is_valid_candidate(position, candidate) for position, candidate in choices.items()):
        return _error("Please select a valid candidate for every position.")
    if not cast_ballot(user["rollno"], choices):
        return _error("Your vote could not be recorded. Please try again.", 409)
    blockchain = current_app.extensions["blockchain"]
    ballot_id = secrets.token_hex(16)
    for position, candidate in choices.items():
        blockchain.new_transaction(position, candidate, ballot_id)
    if len(blockchain.pending_transactions) >= 5:
        blockchain.mine_pending_transactions("auto")
    blockchain.save()
    return jsonify({"success": True, "message": "Your vote was recorded successfully."})


@api.get("/results")
def results():
    is_admin = bool(session.get("admin"))
    released = get_setting("results_released") == "true"
    if not released and not is_admin:
        return jsonify({"released": False})
    return jsonify({
        "released": released,
        "results": {position: get_results(position) for position in POSITIONS},
    })


def _require_admin():
    return None if session.get("admin") else (_error("Administrator login required.", 403))


@api.get("/admin")
def admin_data():
    denied = _require_admin()
    if denied:
        return denied
    return jsonify({
        "voting_open": get_setting("voting_open") == "true",
        "results_released": get_setting("results_released") == "true",
        "pending_users": get_pending_users(),
        "users": get_all_users(),
        "candidates": {
            position: [
                _plain_candidate(candidate)
                for candidate in get_candidates_by_position(position)
            ]
            for position in POSITIONS
        },
    })


@api.post("/admin/users/<rollno>/<action>")
def admin_user(rollno, action):
    denied = _require_admin()
    if denied:
        return denied
    if action == "approve":
        approve_user_by_rollno(rollno)
    elif action == "reject":
        delete_user(rollno)
    else:
        return _error("Unknown user action.")
    return jsonify({"success": True})


@api.post("/admin/settings")
def admin_settings():
    denied = _require_admin()
    if denied:
        return denied
    action = (request.get_json(silent=True) or {}).get("action")
    updates = {
        "release": ("results_released", "true"),
        "hide": ("results_released", "false"),
        "open_voting": ("voting_open", "true"),
        "close_voting": ("voting_open", "false"),
    }
    if action == "clear_candidates":
        clear_all_candidates()
    elif action in updates:
        update_setting(*updates[action])
    else:
        return _error("Unknown settings action.")
    return jsonify({"success": True})


@api.post("/admin/candidates")
def admin_candidate():
    denied = _require_admin()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    name = sanitize_input(data.get("name"))
    symbol = sanitize_input(data.get("symbol"))
    position = sanitize_input(data.get("position"))
    if not name or not symbol or position not in POSITIONS:
        return _error("Invalid candidate details.")
    if not add_candidate(name, symbol, position, data.get("image")):
        return _error("Symbol already used in this position.", 409)
    return jsonify({"success": True})


@api.get("/blockchain")
def blockchain_data():
    blockchain = current_app.extensions["blockchain"]
    return jsonify({
        "blocks": blockchain.to_dict()["chain"],
        "pending": blockchain.pending_transactions,
        "valid": blockchain.is_chain_valid(),
    })


@api.post("/blockchain/mine")
def blockchain_mine():
    denied = _require_admin()
    if denied:
        return denied
    blockchain = current_app.extensions["blockchain"]
    blockchain.mine_pending_transactions("admin")
    blockchain.save()
    return jsonify({"success": True})
