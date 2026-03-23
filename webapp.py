from __future__ import annotations

from datetime import date
import os

from flask import Flask, flash, redirect, render_template, request, session, url_for

from timeontask import TimeOnTask

app = Flask(__name__)
app.config["SECRET_KEY"] = "timeontask-dev"


def bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def week_start_iso() -> str:
    return TimeOnTask.week_start(date.today())


def weekday_name(value: int) -> str:
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return names[value] if 0 <= value < len(names) else str(value)


def review_bucket(goal: dict[str, object]) -> str:
    if bool(goal["is_completed"]):
        return "completed"
    if goal["review_outcome"] == "deferred":
        return "deferred"
    if goal["review_outcome"] == "blocked":
        return "blocked"
    if goal["review_outcome"] == "carried_forward":
        return "carried_forward"
    return "unreviewed"


def is_overdue(due_date: object, *, today_iso: str | None = None) -> bool:
    if not due_date:
        return False
    compare_to = today_iso or date.today().isoformat()
    return str(due_date) < compare_to


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

        projects = tracker.list_projects(include_archived=True)
        active_projects = [project for project in projects if not project["is_archived"]]
        archived_projects = [project for project in projects if project["is_archived"]]
        return render_template(
            "projects.html",
            projects=active_projects,
            archived_projects=archived_projects,
        )
    finally:
        tracker.close()


@app.post("/projects/<int:project_id>/edit")
def edit_project(project_id: int) -> str:
    tracker = TimeOnTask()
    try:
        name = request.form.get("name", "").strip()
        try:
            tracker.rename_project(project_id, name)
            flash("Project updated.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("projects"))
    finally:
        tracker.close()


@app.post("/projects/<int:project_id>/archive")
def archive_project(project_id: int) -> str:
    tracker = TimeOnTask()
    try:
        tracker.archive_project(project_id)
        flash("Project archived.")
        return redirect(url_for("projects"))
    finally:
        tracker.close()


@app.post("/projects/<int:project_id>/restore")
def restore_project(project_id: int) -> str:
    tracker = TimeOnTask()
    try:
        tracker.restore_project(project_id)
        flash("Project restored.")
        return redirect(url_for("projects"))
    finally:
        tracker.close()


@app.route("/projects/<int:project_id>", methods=["GET", "POST"])
def project_dashboard(project_id: int) -> str:
    tracker = TimeOnTask()
    try:
        project = tracker.get_project(project_id)
        if project is None:
            flash("Project not found.")
            return redirect(url_for("projects"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            due_date = request.form.get("due_date", "")
            priority = request.form.get("priority", "")
            if not title:
                flash("Task title is required.")
                return redirect(url_for("project_dashboard", project_id=project_id))
            try:
                tracker.add_task(project_id, title, due_date=due_date, priority=priority)
                session["last_project_id"] = project_id
                flash("Task created.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("project_dashboard", project_id=project_id))

        tasks = [task for task in tracker.list_tasks(sort_by="created", include_archived=True) if task["project_id"] == project_id]
        meetings = [meeting for meeting in tracker.list_meetings() if meeting["project_id"] == project_id]
        goals = [goal for goal in tracker.list_week_goals() if goal["project_name"] == project["name"]]
        active_tasks = [task for task in tasks if not task["is_archived"]]
        archived_tasks = [task for task in tasks if task["is_archived"]]
        today_iso = date.today().isoformat()
        for task in active_tasks:
            task["is_overdue"] = not bool(task["is_completed"]) and is_overdue(task.get("due_date"), today_iso=today_iso)

        return render_template(
            "project_dashboard.html",
            project=project,
            active_tasks=active_tasks,
            archived_tasks=archived_tasks,
            meetings=meetings,
            goals=goals,
        )
    finally:
        tracker.close()


@app.route("/tasks", methods=["GET", "POST"])
def tasks() -> str:
    tracker = TimeOnTask()
    try:
        sort = request.values.get("sort", session.get("tasks_sort", "created"))
        if sort not in {"created", "project"}:
            sort = "created"
        session["tasks_sort"] = sort
        tracker.generate_recurring_tasks()

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            project_id = request.form.get("project_id", "").strip()
            due_date = request.form.get("due_date", "")
            priority = request.form.get("priority", "")
            if title and project_id:
                try:
                    project_id_int = int(project_id)
                    duplicates = tracker.find_duplicate_incomplete_tasks(project_id_int, title)
                    tracker.add_task(project_id_int, title, due_date=due_date, priority=priority)
                    session["last_project_id"] = project_id_int
                    flash("Task created.")
                    if duplicates:
                        flash(
                            "Possible duplicate: open task(s) with the same title already exist in this project."
                        )
                except ValueError as exc:
                    flash(str(exc))
            else:
                flash("Task title and project are required.")
            return redirect(url_for("tasks", sort=sort))

        projects = tracker.list_projects()
        last_project_id = session.get("last_project_id")
        valid_ids = {p["id"] for p in projects}
        if last_project_id not in valid_ids:
            last_project_id = projects[0]["id"] if projects else None
        tasks = tracker.list_tasks(sort_by=sort)
        archived_tasks = tracker.list_tasks(sort_by=sort, include_archived=True)
        archived_tasks = [task for task in archived_tasks if task["is_archived"]]
        today_iso = date.today().isoformat()
        for task in tasks:
            task["is_overdue"] = not bool(task["is_completed"]) and is_overdue(task.get("due_date"), today_iso=today_iso)
        for task in archived_tasks:
            task["is_overdue"] = False

        return render_template(
            "tasks.html",
            tasks=tasks,
            archived_tasks=archived_tasks,
            projects=projects,
            last_project_id=last_project_id,
            recurring_templates=tracker.list_recurring_templates(),
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
        due_date = request.form.get("due_date", "")
        priority = request.form.get("priority", "")

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

        try:
            created = tracker.add_task_batch(
                project_id_int,
                base_title,
                count_int,
                due_date=due_date,
                priority=priority,
            )
            session["last_project_id"] = project_id_int
            flash(f"Created {created} tasks.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("tasks", sort=sort))
    finally:
        tracker.close()


@app.post("/tasks/recurring")
def add_recurring_task_template() -> str:
    tracker = TimeOnTask()
    try:
        sort = request.form.get("sort", session.get("tasks_sort", "created"))
        if sort not in {"created", "project"}:
            sort = "created"

        title = request.form.get("title", "").strip()
        project_id = request.form.get("project_id", "").strip()
        freq = request.form.get("freq", "").strip()
        interval_n = request.form.get("interval_n", "1").strip()
        starts_on = request.form.get("starts_on", "")
        ends_on = request.form.get("ends_on", "")
        weekdays = request.form.get("weekdays", "")
        month_days = request.form.get("month_days", "")
        year_dates = request.form.get("year_dates", "")
        due_date = request.form.get("due_date", "")
        priority = request.form.get("priority", "")

        if not title or not project_id or not freq:
            flash("Recurring template needs title, project, and frequency.")
            return redirect(url_for("tasks", sort=sort))

        try:
            project_id_int = int(project_id)
            interval_n_int = int(interval_n)
        except ValueError:
            flash("Project and interval must be valid numbers.")
            return redirect(url_for("tasks", sort=sort))

        try:
            tracker.add_recurring_template(
                project_id_int,
                title,
                freq=freq,
                interval_n=interval_n_int,
                starts_on=starts_on,
                ends_on=ends_on,
                weekdays_csv=weekdays,
                month_days_csv=month_days,
                year_dates_csv=year_dates,
                due_date=due_date,
                priority=priority,
            )
            tracker.generate_recurring_tasks()
            flash("Recurring template created.")
        except ValueError as exc:
            flash(str(exc))

        return redirect(url_for("tasks", sort=sort))
    finally:
        tracker.close()


@app.post("/tasks/<int:task_id>/subtasks")
def add_subtask(task_id: int) -> str:
    tracker = TimeOnTask()
    try:
        sort = request.form.get("sort", session.get("tasks_sort", "created"))
        if sort not in {"created", "project"}:
            sort = "created"

        title = request.form.get("title", "").strip()
        if not title:
            flash("Subtask title is required.")
            return redirect(url_for("edit_task", task_id=task_id, sort=sort))

        try:
            tracker.add_subtask(task_id, title)
            flash("Subtask added.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("edit_task", task_id=task_id, sort=sort))
    finally:
        tracker.close()


@app.post("/subtasks/<int:subtask_id>/toggle")
def toggle_subtask(subtask_id: int) -> str:
    tracker = TimeOnTask()
    try:
        task_id = request.form.get("task_id", "").strip()
        sort = request.form.get("sort", session.get("tasks_sort", "created"))
        if sort not in {"created", "project"}:
            sort = "created"

        is_completed = request.form.get("is_completed") == "1"
        tracker.set_subtask_completed(subtask_id, is_completed)
        flash("Subtask updated.")

        if task_id:
            return redirect(url_for("edit_task", task_id=int(task_id), sort=sort))
        return redirect(url_for("tasks", sort=sort))
    finally:
        tracker.close()


@app.post("/subtasks/<int:subtask_id>/delete")
def delete_subtask(subtask_id: int) -> str:
    tracker = TimeOnTask()
    try:
        task_id = request.form.get("task_id", "").strip()
        sort = request.form.get("sort", session.get("tasks_sort", "created"))
        if sort not in {"created", "project"}:
            sort = "created"

        tracker.delete_subtask(subtask_id)
        flash("Subtask deleted.")

        if task_id:
            return redirect(url_for("edit_task", task_id=int(task_id), sort=sort))
        return redirect(url_for("tasks", sort=sort))
    finally:
        tracker.close()


@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id: int) -> str:
    tracker = TimeOnTask()
    try:
        sort = request.values.get("sort", session.get("tasks_sort", "created"))
        if sort not in {"created", "project"}:
            sort = "created"
        session["tasks_sort"] = sort

        task = tracker.get_task(task_id)
        if task is None:
            flash("Task not found.")
            return redirect(url_for("tasks", sort=sort))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            project_id = request.form.get("project_id", "").strip()
            due_date = request.form.get("due_date", "")
            priority = request.form.get("priority", "")
            is_completed = request.form.get("is_completed") == "on"

            if title and project_id:
                try:
                    project_id_int = int(project_id)
                    tracker.update_task(
                        task_id,
                        project_id_int,
                        title,
                        is_completed,
                        due_date=due_date,
                        priority=priority,
                    )
                    session["last_project_id"] = project_id_int
                    flash("Task updated.")
                    return redirect(url_for("tasks", sort=sort))
                except ValueError as exc:
                    flash(str(exc))

            flash("Task title and project are required.")

        return render_template(
            "task_edit.html",
            task=task,
            projects=tracker.list_projects(),
            subtasks=tracker.list_subtasks(task_id),
            sort=sort,
        )
    finally:
        tracker.close()


@app.post("/tasks/<int:task_id>/archive")
def archive_task(task_id: int) -> str:
    tracker = TimeOnTask()
    try:
        sort = request.form.get("sort", session.get("tasks_sort", "created"))
        project_id = request.form.get("project_id", "").strip()
        if sort not in {"created", "project"}:
            sort = "created"
        tracker.archive_task(task_id)
        flash("Task archived.")
        if project_id:
            return redirect(url_for("project_dashboard", project_id=int(project_id)))
        return redirect(url_for("tasks", sort=sort))
    finally:
        tracker.close()


@app.post("/tasks/<int:task_id>/restore")
def restore_task(task_id: int) -> str:
    tracker = TimeOnTask()
    try:
        sort = request.form.get("sort", session.get("tasks_sort", "created"))
        project_id = request.form.get("project_id", "").strip()
        if sort not in {"created", "project"}:
            sort = "created"
        tracker.restore_task(task_id)
        flash("Task restored.")
        if project_id:
            return redirect(url_for("project_dashboard", project_id=int(project_id)))
        return redirect(url_for("tasks", sort=sort))
    finally:
        tracker.close()


@app.post("/tasks/<int:task_id>/snooze")
def snooze_task(task_id: int) -> str:
    tracker = TimeOnTask()
    try:
        sort = request.form.get("sort", session.get("tasks_sort", "created"))
        if sort not in {"created", "project"}:
            sort = "created"
        project_id = request.form.get("project_id", "").strip()
        try:
            due_date_iso = tracker.snooze_task_to_next_week(task_id)
            flash(f"Task snoozed to {due_date_iso}.")
        except ValueError as exc:
            flash(str(exc))
        if project_id:
            return redirect(url_for("project_dashboard", project_id=int(project_id)))
        return redirect(request.referrer or url_for("tasks", sort=sort))
    finally:
        tracker.close()


@app.route("/meetings", methods=["GET", "POST"])
def meetings() -> str:
    tracker = TimeOnTask()
    try:
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            weekday = request.form.get("weekday", "").strip()
            start_time = request.form.get("start_time", "").strip()
            duration = request.form.get("duration_minutes", "").strip()
            project_id = request.form.get("project_id", "").strip()

            if not title or not weekday or not start_time or not duration:
                flash("Title, weekday, start time, and duration are required.")
                return redirect(url_for("meetings"))

            try:
                weekday_int = int(weekday)
                duration_int = int(duration)
                project_id_int = int(project_id) if project_id else None
                tracker.add_meeting(
                    title=title,
                    weekday=weekday_int,
                    start_time=start_time,
                    duration_minutes=duration_int,
                    project_id=project_id_int,
                )
                flash("Meeting created.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("meetings"))

        meetings_rows = tracker.list_meetings()
        for row in meetings_rows:
            row["weekday_name"] = weekday_name(int(row["weekday"]))

        return render_template(
            "meetings.html",
            meetings=meetings_rows,
            projects=tracker.list_projects(),
            weekday_choices=[(idx, weekday_name(idx)) for idx in range(7)],
        )
    finally:
        tracker.close()


@app.post("/meetings/<int:meeting_id>/task")
def create_task_from_meeting(meeting_id: int) -> str:
    tracker = TimeOnTask()
    try:
        project_id = request.form.get("project_id", "").strip()
        title = request.form.get("title", "").strip()
        due_date = request.form.get("due_date", "").strip()
        priority = request.form.get("priority", "").strip()
        next_view = request.form.get("next_view", "meetings").strip()

        if next_view not in {"meetings", "today"}:
            next_view = "meetings"

        try:
            project_id_int = int(project_id) if project_id else None
            task_id = tracker.create_task_from_meeting(
                meeting_id,
                project_id=project_id_int,
                title=title or None,
                due_date=due_date or None,
                priority=priority or None,
            )
            task = tracker.get_task(task_id)
            if task is not None:
                session["last_project_id"] = task["project_id"]
            flash("Follow-up task created.")
        except ValueError as exc:
            flash(str(exc))

        return redirect(url_for(next_view))
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
        tracker.generate_recurring_tasks()
        if request.method == "POST":
            task_id = request.form.get("task_id", "").strip()
            if task_id:
                try:
                    tracker.select_today_task(int(task_id))
                    flash("Task added to today.")
                except ValueError as exc:
                    flash(str(exc))
            return redirect(url_for("today"))

        meetings_rows = tracker.list_today_meetings()
        for row in meetings_rows:
            row["weekday_name"] = weekday_name(int(row["weekday"]))
        incomplete = tracker.list_incomplete_tasks(sort_by="project")
        today_rows = tracker.list_today()
        today_iso = date.today().isoformat()
        for row in incomplete:
            row["is_overdue"] = is_overdue(row.get("due_date"), today_iso=today_iso)
        for row in today_rows:
            row["is_overdue"] = not bool(row["is_completed"]) and is_overdue(row.get("due_date"), today_iso=today_iso)

        return render_template(
            "today.html",
            today_rows=today_rows,
            incomplete=incomplete,
            meetings=meetings_rows,
            projects=tracker.list_projects(),
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
        completed_tasks = tracker.list_completed_tasks_for_week()
        today_iso = date.today().isoformat()
        for task in completed_tasks:
            task["was_overdue"] = is_overdue(task.get("due_date"), today_iso=str(task.get("completed_on") or today_iso))
        grouped_goals = {
            "completed": [],
            "deferred": [],
            "blocked": [],
            "carried_forward": [],
            "unreviewed": [],
        }
        for goal in goals:
            grouped_goals[review_bucket(goal)].append(goal)

        return render_template(
            "week_review.html",
            goals=goals,
            grouped_goals=grouped_goals,
            completed_tasks=completed_tasks,
            summary=summary,
            week_start=week_start_iso(),
        )
    finally:
        tracker.close()


@app.post("/weekly-goals/<int:goal_id>/outcome")
def set_week_goal_outcome(goal_id: int) -> str:
    tracker = TimeOnTask()
    try:
        outcome = request.form.get("outcome", "").strip()
        note = request.form.get("note", "").strip()
        try:
            tracker.set_week_goal_outcome(goal_id, outcome, note=note or None)
            flash("Weekly goal updated.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("week_review"))
    finally:
        tracker.close()


@app.post("/weekly-goals/<int:goal_id>/carry-forward")
def carry_week_goal_forward(goal_id: int) -> str:
    tracker = TimeOnTask()
    try:
        note = request.form.get("note", "").strip()
        try:
            tracker.carry_week_goal_forward(goal_id, note=note or None)
            flash("Weekly goal carried forward.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("week_review"))
    finally:
        tracker.close()


if __name__ == "__main__":
    debug_mode = bool_env("FLASK_DEBUG", default=False)
    app.run(
        host=os.getenv("WEBAPP_HOST", "0.0.0.0"),
        port=int(os.getenv("WEBAPP_PORT", "5000")),
        debug=debug_mode,
        use_reloader=debug_mode,
    )
