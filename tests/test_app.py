from datetime import date

import pytest

from app import TimeOnTask


class FakeCursor:
    def __init__(self, db, dictionary=False):
        self.db = db
        self.dictionary = dictionary
        self.results = []

    def execute(self, query, params=None):
        q = " ".join(query.strip().split()).lower()
        params = params or ()

        if q.startswith("create table"):
            return
        if q.startswith("insert into projects"):
            self.db["projects"].append({"id": len(self.db["projects"]) + 1, "name": params[0]})
            return
        if q.startswith("insert into tasks"):
            self.db["tasks"].append(
                {
                    "id": len(self.db["tasks"]) + 1,
                    "project_id": params[0],
                    "title": params[1],
                    "is_completed": 0,
                }
            )
            return
        if q.startswith("insert ignore into weekly_goals"):
            row = {"week_start": params[0], "task_id": params[1]}
            if row not in self.db["weekly_goals"]:
                self.db["weekly_goals"].append(row)
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
        raise AssertionError(f"Unhandled query: {query}")

    def fetchone(self):
        return self.results[0] if self.results else None

    def fetchall(self):
        return self.results

    def close(self):
        return


class FakeConnection:
    def __init__(self):
        self.db = {"projects": [], "tasks": [], "weekly_goals": [], "daily_selection": []}

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
