from __future__ import annotations

from datetime import date

from flask import Flask, flash, redirect, render_template, request, session, url_for

from timeontask import TimeOnTask

app = Flask(__name__)
app.config["SECRET_KEY"] = "timeontask-dev"


def week_start_iso() -> str:
    return TimeOnTask.week_start(date.today())


@app.route("/")
def dashboard() -> str:
    tracker = TimeOnTask()
    try:
        projects = tracker.list_projects()
        tasks = tracker.list_tasks()
        today_rows = tracker.list_today()
        eod = tracker.end_of_day()
        week = tracker.week_review()
        return render_template(
            "dashboard.html",
            projects_count=len(projects),
            tasks_count=len(tasks),
            today_total=eod.total,
            today_done=eod.completed,
            week_total=week.total,
            week_done=week.completed,
            today_rows=today_rows,
        )
    finally:
        tracker.close()


@app.route("/projects", methods=["GET", "POST"])
def projects() -> str:
    tracker = TimeOnTask()
    try:
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if name:
                tracker.add_project(name)
                flash("Project created.")
            else:
                flash("Project name is required.")
            return redirect(url_for("projects"))

        return render_template("projects.html", projects=tracker.list_projects())
    finally:
        tracker.close()


@app.route("/tasks", methods=["GET", "POST"])
def tasks() -> str:
    tracker = TimeOnTask()
    try:
        sort = request.values.get("sort", "created")
        if sort not in {"created", "project"}:
            sort = "created"

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            project_id = request.form.get("project_id", "").strip()
            if title and project_id:
                project_id_int = int(project_id)
                tracker.add_task(project_id_int, title)
                session["last_project_id"] = project_id_int
                flash("Task created.")
            else:
                flash("Task title and project are required.")
            return redirect(url_for("tasks", sort=sort))

        projects = tracker.list_projects()
        last_project_id = session.get("last_project_id")
        valid_ids = {p["id"] for p in projects}
        if last_project_id not in valid_ids:
            last_project_id = projects[0]["id"] if projects else None

        return render_template(
            "tasks.html",
            tasks=tracker.list_tasks(sort_by=sort),
            projects=projects,
            last_project_id=last_project_id,
            sort=sort,
        )
    finally:
        tracker.close()


@app.post("/tasks/bulk")
def bulk_add_tasks() -> str:
    tracker = TimeOnTask()
    try:
        sort = request.form.get("sort", "created")
        if sort not in {"created", "project"}:
            sort = "created"

        base_title = request.form.get("base_title", "").strip()
        project_id = request.form.get("project_id", "").strip()
        count = request.form.get("count", "").strip()

        if not base_title or not project_id or not count:
            flash("Project, base title, and count are required.")
            return redirect(url_for("tasks", sort=sort))

        try:
            project_id_int = int(project_id)
            count_int = int(count)
        except ValueError:
            flash("Count and project must be valid numbers.")
            return redirect(url_for("tasks", sort=sort))

        if count_int < 1:
            flash("Count must be at least 1.")
            return redirect(url_for("tasks", sort=sort))

        created = tracker.add_task_batch(project_id_int, base_title, count_int)
        session["last_project_id"] = project_id_int
        flash(f"Created {created} tasks.")
        return redirect(url_for("tasks", sort=sort))
    finally:
        tracker.close()


@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id: int) -> str:
    tracker = TimeOnTask()
    try:
        task = tracker.get_task(task_id)
        if task is None:
            flash("Task not found.")
            return redirect(url_for("tasks"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            project_id = request.form.get("project_id", "").strip()
            is_completed = request.form.get("is_completed") == "on"

            if title and project_id:
                project_id_int = int(project_id)
                tracker.update_task(task_id, project_id_int, title, is_completed)
                session["last_project_id"] = project_id_int
                flash("Task updated.")
                return redirect(url_for("tasks"))

            flash("Task title and project are required.")

        return render_template(
            "task_edit.html",
            task=task,
            projects=tracker.list_projects(),
        )
    finally:
        tracker.close()


@app.route("/weekly-goals", methods=["GET", "POST"])
def weekly_goals() -> str:
    tracker = TimeOnTask()
    try:
        if request.method == "POST":
            task_id = request.form.get("task_id", "").strip()
            if task_id:
                tracker.set_week_goal(int(task_id))
                flash("Task added to weekly goals.")
            return redirect(url_for("weekly_goals"))

        return render_template(
            "weekly_goals.html",
            goals=tracker.list_week_goals(),
            candidates=tracker.list_incomplete_tasks(),
            week_start=week_start_iso(),
        )
    finally:
        tracker.close()


@app.route("/today", methods=["GET", "POST"])
def today() -> str:
    tracker = TimeOnTask()
    try:
        if request.method == "POST":
            task_id = request.form.get("task_id", "").strip()
            if task_id:
                try:
                    tracker.select_today_task(int(task_id))
                    flash("Task added to today.")
                except ValueError as exc:
                    flash(str(exc))
            return redirect(url_for("today"))

        return render_template(
            "today.html",
            today_rows=tracker.list_today(),
            incomplete=tracker.list_incomplete_tasks(),
        )
    finally:
        tracker.close()


@app.post("/tasks/<int:task_id>/complete")
def complete_task(task_id: int) -> str:
    tracker = TimeOnTask()
    try:
        tracker.complete_task(task_id)
        flash("Task marked complete.")
        return redirect(request.referrer or url_for("today"))
    finally:
        tracker.close()


@app.route("/end-of-day")
def end_of_day() -> str:
    tracker = TimeOnTask()
    try:
        rows = tracker.list_today()
        summary = tracker.end_of_day()
        return render_template("end_of_day.html", rows=rows, summary=summary)
    finally:
        tracker.close()


@app.route("/week-review")
def week_review() -> str:
    tracker = TimeOnTask()
    try:
        goals = tracker.list_week_goals()
        summary = tracker.week_review()
        return render_template("week_review.html", goals=goals, summary=summary, week_start=week_start_iso())
    finally:
        tracker.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
