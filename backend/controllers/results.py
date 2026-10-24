from flask import Blueprint, render_template, session

from database.mongo_db import get_results, get_setting

results_controller = Blueprint("results", __name__)


@results_controller.route("/results")
def results():
    if get_setting("results_released") != "true" and not session.get("admin"):
        return render_template("results.html", results_not_released=True)

    return render_template(
        "results.html",
        president=get_results("President"),
        vice=get_results("Vice President"),
        secretary=get_results("Secretary"),
        treasury=get_results("Treasury"),
    )


@results_controller.route("/student_results")
def student_results():
    if get_setting("results_released") != "true":
        return render_template("student_results.html", results_released=False)

    return render_template(
        "student_results.html",
        results_released=True,
        president=get_results("President"),
        vice=get_results("Vice President"),
        secretary=get_results("Secretary"),
        treasury=get_results("Treasury"),
    )
