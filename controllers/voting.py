import os
import secrets

from flask import Blueprint, current_app, redirect, render_template, request, session
from werkzeug.utils import secure_filename

from database.mongo_db import (
    add_candidate,
    cast_ballot,
    get_candidates_by_position,
    get_setting,
    get_user_by_rollno,
    has_voted,
    is_user_approved,
    is_valid_candidate,
)

voting_controller = Blueprint("voting", __name__)
ALLOWED_POSITIONS = {"President", "Vice President", "Secretary", "Treasury"}
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _candidates_for_vote():
    return {
        "president": get_candidates_by_position("President"),
        "vice_president": get_candidates_by_position("Vice President"),
        "secretary": get_candidates_by_position("Secretary"),
        "treasury": get_candidates_by_position("Treasury"),
    }


@voting_controller.route("/vote")
def vote():
    rollno = session.get("rollno")
    if not rollno:
        return redirect("/")

    user = get_user_by_rollno(rollno)
    if not user or not is_user_approved(rollno):
        session.clear()
        return redirect("/")

    voting_open = get_setting("voting_open")
    if voting_open is None:
        voting_open = "false"
    return render_template(
        "vote.html",
        **_candidates_for_vote(),
        user=user,
        voting_open=voting_open,
    )


@voting_controller.route("/add_candidate", methods=["POST"])
def add_candidate_route():
    if not session.get("admin"):
        return redirect("/")

    name = request.form.get("candidate_name", "").strip()
    symbol = request.form.get("candidate_symbol", "").strip()
    position = request.form.get("position", "").strip()
    if not name or not symbol or position not in ALLOWED_POSITIONS:
        return render_template("admin.html", message="Invalid candidate details")

    image_filename = None
    if "candidate_image" in request.files:
        file = request.files["candidate_image"]
        safe_upload_name = secure_filename(file.filename or "")
        if file and safe_upload_name and allowed_file(safe_upload_name):
            extension = safe_upload_name.rsplit(".", 1)[1].lower()
            image_filename = f"{secrets.token_hex(12)}.{extension}"
            file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], image_filename))

    if add_candidate(name, symbol, position, image_filename):
        message = "Candidate Added Successfully"
    else:
        message = "Symbol already used in this position"
    return render_template("admin.html", message=message)


@voting_controller.route("/submit_vote", methods=["POST"])
def submit_vote():
    rollno = session.get("rollno")
    if not rollno:
        return redirect("/")

    user = get_user_by_rollno(rollno)
    if not user or not is_user_approved(rollno):
        session.clear()
        return redirect("/")
    if get_setting("voting_open") != "true":
        return redirect("/vote")

    if has_voted(rollno):
        return render_template(
            "vote.html",
            message="Your Vote Been Casted",
            msg_color="red",
            **_candidates_for_vote(),
        )

    choices = {
        "President": request.form.get("president"),
        "Vice President": request.form.get("vice_president"),
        "Secretary": request.form.get("secretary"),
        "Treasury": request.form.get("treasury"),
    }
    if any(
        not is_valid_candidate(position, candidate)
        for position, candidate in choices.items()
    ):
        return render_template(
            "vote.html",
            message="Please select a valid candidate for every position.",
            msg_color="red",
            **_candidates_for_vote(),
            user=user,
            voting_open="true",
        )

    if not cast_ballot(rollno, choices):
        return redirect("/vote")

    blockchain = current_app.extensions["blockchain"]
    ballot_id = secrets.token_hex(16)
    for position, candidate in choices.items():
        blockchain.new_transaction(position, candidate, ballot_id)
    if len(blockchain.pending_transactions) >= 5:
        blockchain.mine_pending_transactions("auto")
        blockchain.save()
        current_app.logger.info("Auto-mined blockchain block after five votes")

    blockchain.save()
    voting_open = get_setting("voting_open")
    if voting_open is None:
        voting_open = "false"
    return render_template(
        "vote.html",
        message="Vote cast successfully! Recorded on blockchain.",
        msg_color="green",
        **_candidates_for_vote(),
        voting_open=voting_open,
    )
