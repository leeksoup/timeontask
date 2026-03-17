from datetime import date
from pathlib import Path

import pytest

from timeontask import TimeOnTask


class FakeCursor:
    def __init__(self, db, dictionary=False):
        self.db = db
        self.dictionary = dictionary
        self.results = []
        self.lastrowid = None

    def execute(self, query, params=None):
        q = " ".join(query.strip().split()).lower()
        params = params or ()

        if q.startswith("create table"):
            return
        if q.startswith("alter table tasks add column"):
            return
        if q.startswith("insert into projects"):
            self.db["projects"].append({"id": len(self.db["projects"]) + 1, "name": params[0]})
            return
        if q.startswith("insert into tasks"):
            due_date = params[2] if len(params) > 2 else None
            priority = params[3] if len(params) > 3 else None
            template_id = params[4] if len(params) > 4 else None
            occurrence_date = params[5] if len(params) > 5 else None
            self.db["tasks"].append(
                {
                    "id": len(self.db["tasks"]) + 1,
                    "project_id": params[0],
                    "title": params[1],
                    "due_date": due_date,
                    "priority": priority,
                    "template_id": template_id,
                    "occurrence_date": occurrence_date,
                    "is_completed": 0,
                }
            )
            return
        if q.startswith("insert ignore into weekly_goals"):
            row = {"week_start": params[0], "task_id": params[1]}
            if row not in self.db["weekly_goals"]:
                self.db["weekly_goals"].append(row)
            return
        if q.startswith("insert into task_templates"):
            self.db["task_templates"].append(
                {
                    "id": len(self.db["task_templates"]) + 1,
                    "project_id": params[0],
                    "title": params[1],
                    "due_date": params[2],
                    "priority": params[3],
                    "is_active": 1,
                }
            )
            self.lastrowid = len(self.db["task_templates"])
            return
        if q.startswith("insert into task_recurrence_rules"):
            self.db["task_recurrence_rules"].append(
                {
                    "id": len(self.db["task_recurrence_rules"]) + 1,
                    "template_id": params[0],
                    "freq": params[1],
                    "interval_n": params[2],
                    "starts_on": params[3],
                    "ends_on": params[4],
                }
            )
            self.lastrowid = len(self.db["task_recurrence_rules"])
            return
        if q.startswith("insert ignore into task_recurrence_weekdays"):
            row = {"rule_id": params[0], "weekday": params[1]}
            if row not in self.db["task_recurrence_weekdays"]:
                self.db["task_recurrence_weekdays"].append(row)
            return
        if q.startswith("insert ignore into task_recurrence_month_days"):
            row = {"rule_id": params[0], "day_of_month": params[1]}
            if row not in self.db["task_recurrence_month_days"]:
                self.db["task_recurrence_month_days"].append(row)
            return
        if q.startswith("insert ignore into task_recurrence_year_days"):
            row = {"rule_id": params[0], "month_num": params[1], "day_of_month": params[2]}
            if row not in self.db["task_recurrence_year_days"]:
                self.db["task_recurrence_year_days"].append(row)
            return
        if "select count(*) as open_count" in q:
            today = params[0]
            open_count = 0
            for ds in self.db["daily_selection"]:
                if ds["day_date"] == today:
                    task = next(t for t in self.db["tasks"] if t["id"] == ds["task_id"])
                    if task["is_completed"] == 0:
                        open_count += 1
            self.results = [{"open_count": open_count}]
            return
        if q.startswith("insert ignore into daily_selection"):
            row = {"day_date": params[0], "task_id": params[1], "id": len(self.db["daily_selection"]) + 1}
            if not any(r["day_date"] == row["day_date"] and r["task_id"] == row["task_id"] for r in self.db["daily_selection"]):
                self.db["daily_selection"].append(row)
            return
        if q.startswith("update tasks set is_completed"):
            for task in self.db["tasks"]:
                if task["id"] == params[0]:
                    task["is_completed"] = 1
            return
        if q.startswith("update tasks set project_id"):
            for task in self.db["tasks"]:
                if task["id"] == params[5]:
                    task["project_id"] = params[0]
                    task["title"] = params[1]
                    task["due_date"] = params[2]
                    task["priority"] = params[3]
                    task["is_completed"] = params[4]
            return
        if "from daily_selection ds join tasks" in q and "where ds.day_date" in q:
            today = params[0]
            out = []
            for ds in sorted(self.db["daily_selection"], key=lambda x: x["id"]):
                if ds["day_date"] == today:
                    task = next(t for t in self.db["tasks"] if t["id"] == ds["task_id"])
                    proj = next(p for p in self.db["projects"] if p["id"] == task["project_id"])
                    out.append(
                        {
                            "id": task["id"],
                            "title": task["title"],
                            "due_date": task["due_date"],
                            "priority": task["priority"],
                            "is_completed": task["is_completed"],
                            "project_name": proj["name"],
                        }
                    )
            self.results = out
            return
        if "from weekly_goals wg join tasks" in q:
            week = params[0]
            out = []
            for wg in self.db["weekly_goals"]:
                if wg["week_start"] == week:
                    task = next(t for t in self.db["tasks"] if t["id"] == wg["task_id"])
                    out.append({"is_completed": task["is_completed"]})
            self.results = out
            return
        if "from task_recurrence_rules r join task_templates t" in q:
            out = []
            for rule in self.db["task_recurrence_rules"]:
                template = next(t for t in self.db["task_templates"] if t["id"] == rule["template_id"])
                if template["is_active"] == 1:
                    out.append(
                        {
                            "id": rule["id"],
                            "template_id": rule["template_id"],
                            "freq": rule["freq"],
                            "interval_n": rule["interval_n"],
                            "starts_on": rule["starts_on"],
                            "ends_on": rule["ends_on"],
                            "project_id": template["project_id"],
                            "title": template["title"],
                            "due_date": template["due_date"],
                            "priority": template["priority"],
                        }
                    )
            self.results = out
            return
        if q.startswith("select weekday from task_recurrence_weekdays where rule_id"):
            rule_id = params[0]
            self.results = [r for r in self.db["task_recurrence_weekdays"] if r["rule_id"] == rule_id]
            return
        if q.startswith("select day_of_month from task_recurrence_month_days where rule_id"):
            rule_id = params[0]
            self.results = [r for r in self.db["task_recurrence_month_days"] if r["rule_id"] == rule_id]
            return
        if q.startswith("select month_num, day_of_month from task_recurrence_year_days where rule_id"):
            rule_id = params[0]
            self.results = [r for r in self.db["task_recurrence_year_days"] if r["rule_id"] == rule_id]
            return
        if q.startswith("select id from tasks where template_id"):
            template_id, occurrence_date = params
            match = next(
                (t for t in self.db["tasks"] if t.get("template_id") == template_id and t.get("occurrence_date") == occurrence_date),
                None,
            )
            self.results = [{"id": match["id"]}] if match else []
            return
        if "from task_templates t join task_recurrence_rules r" in q:
            out = []
            for template in self.db["task_templates"]:
                if template["is_active"] != 1:
                    continue
                rule = next(r for r in self.db["task_recurrence_rules"] if r["template_id"] == template["id"])
                project = next(p for p in self.db["projects"] if p["id"] == template["project_id"])
                out.append(
                    {
                        "id": template["id"],
                        "title": template["title"],
                        "project_id": template["project_id"],
                        "project_name": project["name"],
                        "freq": rule["freq"],
                        "interval_n": rule["interval_n"],
                        "starts_on": rule["starts_on"],
                        "ends_on": rule["ends_on"],
                    }
                )
            self.results = out
            return
        if q.startswith("select id, title, project_id, due_date, priority, is_completed from tasks where id"):
            task_id = params[0]
            task = next((t for t in self.db["tasks"] if t["id"] == task_id), None)
            self.results = [task] if task else []
            return
        if "from tasks t join projects p on p.id = t.project_id" in q:
            out = []
            for task in self.db["tasks"]:
                proj = next(p for p in self.db["projects"] if p["id"] == task["project_id"])
                out.append(
                    {
                        "id": task["id"],
                        "title": task["title"],
                        "project_id": task["project_id"],
                        "due_date": task["due_date"],
                        "priority": task["priority"],
                        "is_completed": task["is_completed"],
                        "project_name": proj["name"],
                    }
                )

            if "order by p.name, t.title, t.id" in q:
                out.sort(key=lambda t: (t["project_name"], t["title"], t["id"]))
            else:
                out.sort(key=lambda t: t["id"])
            self.results = out
            return
        raise AssertionError(f"Unhandled query: {query}")

    def fetchone(self):
        return self.results[0] if self.results else None

    def fetchall(self):
        return self.results

    def close(self):
        return


class FakeConnection:
    def __init__(self):
        self.db = {
            "projects": [],
            "tasks": [],
            "weekly_goals": [],
            "daily_selection": [],
            "task_templates": [],
            "task_recurrence_rules": [],
            "task_recurrence_weekdays": [],
            "task_recurrence_month_days": [],
            "task_recurrence_year_days": [],
        }

    def cursor(self, dictionary=False):
        return FakeCursor(self.db, dictionary=dictionary)

    def commit(self):
        return

    def close(self):
        return


@pytest.fixture()
def tracker():
    app = TimeOnTask(connection_factory=FakeConnection)
    yield app
    app.close()


def test_projects_tasks_weekly_goals(tracker: TimeOnTask):
    tracker.add_project("Project A")
    tracker.add_task(1, "Task 1")
    tracker.set_week_goal(1, day=date(2026, 3, 9))

    review = tracker.week_review(day=date(2026, 3, 9))
    assert review.total == 1
    assert review.completed == 0


def test_today_limit_and_completion_unlocks_new_task(tracker: TimeOnTask):
    tracker.add_project("P")
    tracker.add_task(1, "T1")
    tracker.add_task(1, "T2")
    tracker.add_task(1, "T3")

    d = date(2026, 3, 10)
    tracker.select_today_task(1, d)
    tracker.select_today_task(2, d)

    with pytest.raises(ValueError):
        tracker.select_today_task(3, d)

    tracker.complete_task(1)
    tracker.select_today_task(3, d)

    progress = tracker.end_of_day(d)
    assert progress.total == 3
    assert progress.completed == 1


def test_add_task_batch_creates_numbered_tasks(tracker: TimeOnTask):
    tracker.add_project("Recordings")

    created = tracker.add_task_batch(1, "Record item", 3, due_date="2026-03-31", priority=2)

    assert created == 3
    tasks = tracker.list_tasks()
    assert [task["title"] for task in tasks] == ["Record item 1", "Record item 2", "Record item 3"]
    assert all(task["due_date"] == "2026-03-31" for task in tasks)
    assert all(task["priority"] == 2 for task in tasks)


def test_list_tasks_can_sort_by_project(tracker: TimeOnTask):
    tracker.add_project("Zeta")
    tracker.add_project("Alpha")
    tracker.add_task(1, "Task A")
    tracker.add_task(2, "Task B")

    tasks = tracker.list_tasks(sort_by="project")
    assert [(task["project_name"], task["title"]) for task in tasks] == [
        ("Alpha", "Task B"),
        ("Zeta", "Task A"),
    ]


def test_update_task_changes_project_title_and_status(tracker: TimeOnTask):
    tracker.add_project("Project A")
    tracker.add_project("Project B")
    tracker.add_task(1, "Original")

    tracker.update_task(1, 2, "Updated", True, due_date="2026-04-01", priority=1)

    task = tracker.get_task(1)
    assert task["id"] == 1
    assert task["project_id"] == 2
    assert task["title"] == "Updated"
    assert task["due_date"] == "2026-04-01"
    assert task["priority"] == 1
    assert task["is_completed"] == 1


def test_add_task_validates_due_date_and_priority(tracker: TimeOnTask):
    tracker.add_project("Project A")

    with pytest.raises(ValueError, match="Due date"):
        tracker.add_task(1, "Bad date", due_date="2026/03/31")

    with pytest.raises(ValueError, match="Priority"):
        tracker.add_task(1, "Bad priority", priority=4)


def test_recurring_daily_generation_is_idempotent(tracker: TimeOnTask):
    tracker.add_project("Ops")
    tracker.add_recurring_template(
        1,
        "Check backups",
        freq="daily",
        starts_on="2026-03-10",
        due_date="2026-03-10",
        priority=1,
    )

    created_first = tracker.generate_recurring_tasks(day=date(2026, 3, 10))
    created_second = tracker.generate_recurring_tasks(day=date(2026, 3, 10))

    assert created_first == 1
    assert created_second == 0
    tasks = tracker.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Check backups"


def test_recurring_monthly_supports_multiple_days(tracker: TimeOnTask):
    tracker.add_project("Home")
    tracker.add_recurring_template(
        1,
        "Pay bills",
        freq="monthly",
        starts_on="2026-03-01",
        month_days_csv="1,15",
    )

    created = tracker.generate_recurring_tasks(day=date(2026, 3, 1), horizon_days=20)

    assert created == 2


def test_task_edit_template_exists():
    assert Path("templates/task_edit.html").exists()
