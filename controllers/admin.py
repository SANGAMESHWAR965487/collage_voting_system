from flask import Blueprint, redirect, render_template, request, session

from database.mongo_db import (
    approve_user_by_rollno,
    clear_all_candidates,
    delete_user,
    get_all_users,
    get_pending_users,
    get_setting,
    update_setting,
)

admin_controller = Blueprint("admin", __name__)


@admin_controller.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/")
    return render_template(
        "admin.html",
        results_released=get_setting("results_released"),
        voting_open=get_setting("voting_open"),
        pending_users=get_pending_users(),
        all_users=get_all_users(),
    )


@admin_controller.route("/approve_user", methods=["POST"])
def approve_user():
    if not session.get("admin"):
        return redirect("/")
    approve_user_by_rollno(request.form.get("rollno"))
    return redirect("/admin")


@admin_controller.route("/reject_user", methods=["POST"])
def reject_user():
    if not session.get("admin"):
        return redirect("/")
    delete_user(request.form.get("rollno"))
    return redirect("/admin")


@admin_controller.route("/registered_students")
def registered_students():
    if not session.get("admin"):
        return redirect("/")
    return render_template("registered_students.html", users=get_all_users())


@admin_controller.route("/release_results", methods=["POST"])
def release_results():
    if not session.get("admin"):
        return redirect("/")

    action = request.form.get("action")
    message = "Unknown action"
    if action == "release":
        update_setting("results_released", "true")
        message = "Results Released Successfully"
    elif action == "hide":
        update_setting("results_released", "false")
        message = "Results Hidden Successfully"
    elif action == "open_voting":
        update_setting("voting_open", "true")
        message = "Voting Opened Successfully"
    elif action == "close_voting":
        update_setting("voting_open", "false")
        message = "Voting Closed Successfully"
    elif action == "clear_candidates":
        clear_all_candidates()
        message = "All Candidates Cleared Successfully"

    return render_template(
        "admin.html",
        message=message,
        results_released=get_setting("results_released"),
        voting_open=get_setting("voting_open"),
    )
