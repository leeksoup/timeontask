from datetime import date
import json
import os
from pathlib import Path

import pytest

from timeontask import TimeOnTask, load_dotenv


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
        if (
            q.startswith("alter table tasks add column")
            or q.startswith("alter table weekly_goals add column")
            or q.startswith("alter table projects add column")
            or q.startswith("alter table project_templates add column")
        ):
            return
        if q.startswith("insert into projects"):
            self.db["projects"].append(
                {
                    "id": len(self.db["projects"]) + 1,
                    "name": params[0],
                    "is_archived": 0,
                    "archived_on": None,
                }
            )
            return
        if q.startswith("insert into tasks"):
            due_date = params[2] if len(params) > 2 else None
            priority = params[3] if len(params) > 3 else None
            template_id = None
            source_meeting_id = None
            occurrence_date = None
            completed_on = None
            if "source_meeting_id" in q:
                source_meeting_id = params[4] if len(params) > 4 else None
            elif "occurrence_date" in q:
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
                    "source_meeting_id": source_meeting_id,
                    "occurrence_date": occurrence_date,
                    "completed_on": completed_on,
                    "is_archived": 0,
                    "archived_on": None,
                    "is_completed": 0,
                }
            )
            self.lastrowid = len(self.db["tasks"])
            return
        if q.startswith("update projects set name = %s where id = %s"):
            for project in self.db["projects"]:
                if project["id"] == params[1]:
                    project["name"] = params[0]
            return
        if q.startswith("update projects set is_archived = 1, archived_on = %s where id = %s"):
            for project in self.db["projects"]:
                if project["id"] == params[1]:
                    project["is_archived"] = 1
                    project["archived_on"] = params[0]
            return
        if q.startswith("update projects set is_archived = 0, archived_on = null where id = %s"):
            for project in self.db["projects"]:
                if project["id"] == params[0]:
                    project["is_archived"] = 0
                    project["archived_on"] = None
            return
        if q.startswith("insert ignore into weekly_goals"):
            row = {
                "id": len(self.db["weekly_goals"]) + 1,
                "week_start": params[0],
                "task_id": params[1],
                "review_outcome": None,
                "review_note": None,
                "carried_to_week_start": None,
            }
            if not any(existing["week_start"] == row["week_start"] and existing["task_id"] == row["task_id"] for existing in self.db["weekly_goals"]):
                self.db["weekly_goals"].append(row)
            return
        if q.startswith("insert into project_templates"):
            self.db["project_templates"].append(
                {"id": len(self.db["project_templates"]) + 1, "name": params[0], "is_archived": 0}
            )
            self.lastrowid = len(self.db["project_templates"])
            return
        if q.startswith("insert into project_template_tasks"):
            self.db["project_template_tasks"].append(
                {
                    "id": len(self.db["project_template_tasks"]) + 1,
                    "template_id": params[0],
                    "title": params[1],
                    "due_offset_days": params[2],
                    "priority": params[3],
                    "position": params[4],
                }
            )
            self.lastrowid = len(self.db["project_template_tasks"])
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
        if q.startswith("update task_templates set project_id = %s, title = %s, due_date = %s, priority = %s where id = %s"):
            for template in self.db["task_templates"]:
                if template["id"] == params[4]:
                    template["project_id"] = params[0]
                    template["title"] = params[1]
                    template["due_date"] = params[2]
                    template["priority"] = params[3]
            return
        if q.startswith("update task_recurrence_rules set freq = %s, interval_n = %s, starts_on = %s, ends_on = %s where id = %s"):
            for rule in self.db["task_recurrence_rules"]:
                if rule["id"] == params[4]:
                    rule["freq"] = params[0]
                    rule["interval_n"] = params[1]
                    rule["starts_on"] = params[2]
                    rule["ends_on"] = params[3]
            return
        if q.startswith("delete from task_recurrence_weekdays where rule_id = %s"):
            self.db["task_recurrence_weekdays"] = [r for r in self.db["task_recurrence_weekdays"] if r["rule_id"] != params[0]]
            return
        if q.startswith("delete from task_recurrence_month_days where rule_id = %s"):
            self.db["task_recurrence_month_days"] = [r for r in self.db["task_recurrence_month_days"] if r["rule_id"] != params[0]]
            return
        if q.startswith("delete from task_recurrence_year_days where rule_id = %s"):
            self.db["task_recurrence_year_days"] = [r for r in self.db["task_recurrence_year_days"] if r["rule_id"] != params[0]]
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
        if q.startswith("select coalesce(max(position), 0) as max_position from subtasks where task_id"):
            task_id = params[0]
            positions = [s["position"] for s in self.db["subtasks"] if s["task_id"] == task_id]
            self.results = [{"max_position": max(positions) if positions else 0}]
            return
        if q.startswith("insert into subtasks"):
            self.db["subtasks"].append(
                {
                    "id": len(self.db["subtasks"]) + 1,
                    "task_id": params[0],
                    "title": params[1],
                    "is_completed": 0,
                    "position": params[2],
                }
            )
            return
        if q.startswith("insert into meetings"):
            self.db["meetings"].append(
                {
                    "id": len(self.db["meetings"]) + 1,
                    "project_id": params[0],
                    "title": params[1],
                    "weekday": params[2],
                    "start_time": params[3],
                    "duration_minutes": params[4],
                    "is_active": 1,
                }
            )
            return
        if q.startswith("update meetings set project_id = %s, title = %s, weekday = %s, start_time = %s, duration_minutes = %s where id = %s"):
            for meeting in self.db["meetings"]:
                if meeting["id"] == params[5]:
                    meeting["project_id"] = params[0]
                    meeting["title"] = params[1]
                    meeting["weekday"] = params[2]
                    meeting["start_time"] = params[3]
                    meeting["duration_minutes"] = params[4]
            return
        if "select count(*) as open_count" in q:
            today = params[0]
            open_count = 0
            for ds in self.db["daily_selection"]:
                if ds["day_date"] == today:
                    task = next(t for t in self.db["tasks"] if t["id"] == ds["task_id"])
                    project = next(p for p in self.db["projects"] if p["id"] == task["project_id"])
                    if task["is_completed"] == 0 and task["is_archived"] == 0 and project["is_archived"] == 0:
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
                if task["id"] == params[1]:
                    task["is_completed"] = 1
                    task["completed_on"] = params[0]
            return
        if q.startswith("update tasks set is_archived = 1, archived_on = %s where id = %s"):
            for task in self.db["tasks"]:
                if task["id"] == params[1]:
                    task["is_archived"] = 1
                    task["archived_on"] = params[0]
            return
        if q.startswith("update tasks set is_archived = 0, archived_on = null where id = %s"):
            for task in self.db["tasks"]:
                if task["id"] == params[0]:
                    task["is_archived"] = 0
                    task["archived_on"] = None
            return
        if q.startswith("update tasks set project_id"):
            for task in self.db["tasks"]:
                if task["id"] == params[6]:
                    task["project_id"] = params[0]
                    task["title"] = params[1]
                    task["due_date"] = params[2]
                    task["priority"] = params[3]
                    task["is_completed"] = params[4]
                    task["completed_on"] = params[5]
            return
        if q.startswith("update subtasks set is_completed"):
            for subtask in self.db["subtasks"]:
                if subtask["id"] == params[1]:
                    subtask["is_completed"] = params[0]
            return
        if q.startswith("update subtasks set position = %s where id = %s"):
            for subtask in self.db["subtasks"]:
                if subtask["id"] == params[1]:
                    subtask["position"] = params[0]
            return
        if q.startswith("update weekly_goals set review_outcome = %s, review_note = %s where id = %s"):
            for goal in self.db["weekly_goals"]:
                if goal["id"] == params[2]:
                    goal["review_outcome"] = params[0]
                    goal["review_note"] = params[1]
            return
        if q.startswith("update weekly_goals set review_outcome = %s, review_note = %s, carried_to_week_start = %s where id = %s"):
            for goal in self.db["weekly_goals"]:
                if goal["id"] == params[3]:
                    goal["review_outcome"] = params[0]
                    goal["review_note"] = params[1]
                    goal["carried_to_week_start"] = params[2]
            return
        if q.startswith("delete from subtasks where id"):
            subtask_id = params[0]
            self.db["subtasks"] = [s for s in self.db["subtasks"] if s["id"] != subtask_id]
            return
        if q.startswith("delete from daily_selection where day_date = %s and task_id = %s"):
            self.db["daily_selection"] = [
                row for row in self.db["daily_selection"] if not (row["day_date"] == params[0] and row["task_id"] == params[1])
            ]
            return
        if "from daily_selection ds join tasks" in q and "where ds.day_date" in q:
            today = params[0]
            out = []
            for ds in sorted(self.db["daily_selection"], key=lambda x: x["id"]):
                if ds["day_date"] == today:
                    task = next(t for t in self.db["tasks"] if t["id"] == ds["task_id"])
                    proj = next(p for p in self.db["projects"] if p["id"] == task["project_id"])
                    if task["is_archived"] == 1 or proj["is_archived"] == 1:
                        continue
                    out.append(
                        {
                            "id": task["id"],
                            "title": task["title"],
                            "due_date": task["due_date"],
                            "priority": task["priority"],
                            "is_completed": task["is_completed"],
                            "project_id": task["project_id"],
                            "occurrence_date": task.get("occurrence_date"),
                            "project_name": proj["name"],
                        }
                    )
            self.results = out
            return
        if q.startswith("select id, name, is_archived, archived_on from projects where id = %s"):
            project_id = params[0]
            project = next((p for p in self.db["projects"] if p["id"] == project_id), None)
            self.results = [project] if project else []
            return
        if q.startswith("select id, name, is_archived, archived_on from projects where is_archived = 0 order by name"):
            out = [p for p in self.db["projects"] if p["is_archived"] == 0]
            out.sort(key=lambda p: p["name"])
            self.results = out
            return
        if q.startswith("select id, name, is_archived, archived_on from projects order by is_archived, name"):
            out = list(self.db["projects"])
            out.sort(key=lambda p: (p["is_archived"], p["name"]))
            self.results = out
            return
        if "where t.is_completed = 1 and t.completed_on >= %s and t.completed_on <= %s" in q:
            start_iso, end_iso = params
            out = []
            for task in self.db["tasks"]:
                if task["is_completed"] != 1 or not task["completed_on"]:
                    continue
                if not (start_iso <= task["completed_on"] <= end_iso):
                    continue
                proj = next(p for p in self.db["projects"] if p["id"] == task["project_id"])
                out.append(
                    {
                        "id": task["id"],
                        "title": task["title"],
                        "project_id": task["project_id"],
                        "due_date": task["due_date"],
                        "priority": task["priority"],
                        "completed_on": task["completed_on"],
                        "occurrence_date": task.get("occurrence_date"),
                        "project_name": proj["name"],
                    }
                )
            out.sort(key=lambda row: (row["completed_on"], row["id"]), reverse=True)
            self.results = out
            return
        if q.startswith("select t.is_completed from weekly_goals wg join tasks"):
            week = params[0]
            out = []
            for wg in self.db["weekly_goals"]:
                if wg["week_start"] == week:
                    task = next(t for t in self.db["tasks"] if t["id"] == wg["task_id"])
                    out.append({"is_completed": task["is_completed"]})
            self.results = out
            return
        if q.startswith("select id, week_start, task_id from weekly_goals where id"):
            goal_id = params[0]
            goal = next((g for g in self.db["weekly_goals"] if g["id"] == goal_id), None)
            self.results = [goal] if goal else []
            return
        if q.startswith("select id, name, is_archived from project_templates where is_archived = 0 order by name"):
            out = [tpl for tpl in self.db["project_templates"] if tpl["is_archived"] == 0]
            out.sort(key=lambda tpl: tpl["name"])
            self.results = out
            return
        if q.startswith("select id, template_id, title, due_offset_days, priority, position from project_template_tasks where template_id = %s"):
            template_id = params[0]
            out = [task for task in self.db["project_template_tasks"] if task["template_id"] == template_id]
            out.sort(key=lambda task: (task["position"], task["id"]))
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
                        "rule_id": rule["id"],
                        "title": template["title"],
                        "project_id": template["project_id"],
                        "due_date": template["due_date"],
                        "priority": template["priority"],
                        "project_name": project["name"],
                        "freq": rule["freq"],
                        "interval_n": rule["interval_n"],
                        "starts_on": rule["starts_on"],
                        "ends_on": rule["ends_on"],
                    }
                )
            self.results = out
            return
        if "from task_templates t join task_recurrence_rules r on r.template_id = t.id where t.id = %s and t.is_active = 1" in q:
            template_id = params[0]
            template = next((t for t in self.db["task_templates"] if t["id"] == template_id and t["is_active"] == 1), None)
            if not template:
                self.results = []
                return
            rule = next((r for r in self.db["task_recurrence_rules"] if r["template_id"] == template_id), None)
            if not rule:
                self.results = []
                return
            self.results = [
                {
                    "id": template["id"],
                    "title": template["title"],
                    "project_id": template["project_id"],
                    "due_date": template["due_date"],
                    "priority": template["priority"],
                    "rule_id": rule["id"],
                    "freq": rule["freq"],
                    "interval_n": rule["interval_n"],
                    "starts_on": rule["starts_on"],
                    "ends_on": rule["ends_on"],
                }
            ]
            return
        if "from meetings m left join projects p on p.id = m.project_id" in q and "where m.is_active = 1 and m.weekday = %s" in q:
            weekday = params[0]
            out = []
            for meeting in self.db["meetings"]:
                if meeting["is_active"] != 1 or meeting["weekday"] != weekday:
                    continue
                project_name = None
                if meeting["project_id"] is not None:
                    project = next((p for p in self.db["projects"] if p["id"] == meeting["project_id"]), None)
                    project_name = project["name"] if project else None
                out.append({**meeting, "project_name": project_name})
            out.sort(key=lambda m: (m["start_time"], m["id"]))
            self.results = out
            return
        if "from meetings m left join projects p on p.id = m.project_id" in q and "where m.is_active = 1" in q:
            out = []
            for meeting in self.db["meetings"]:
                if meeting["is_active"] != 1:
                    continue
                project_name = None
                if meeting["project_id"] is not None:
                    project = next((p for p in self.db["projects"] if p["id"] == meeting["project_id"]), None)
                    project_name = project["name"] if project else None
                out.append({**meeting, "project_name": project_name})
            out.sort(key=lambda m: (m["weekday"], m["start_time"], m["id"]))
            self.results = out
            return
        if "from meetings m left join projects p on p.id = m.project_id" in q and "where m.id = %s" in q:
            meeting_id = params[0]
            meeting = next((m for m in self.db["meetings"] if m["id"] == meeting_id), None)
            if meeting is None:
                self.results = []
                return
            project_name = None
            if meeting["project_id"] is not None:
                project = next((p for p in self.db["projects"] if p["id"] == meeting["project_id"]), None)
                project_name = project["name"] if project else None
            self.results = [{**meeting, "project_name": project_name}]
            return

        if "select wg.id, wg.week_start, wg.review_outcome, wg.review_note, wg.carried_to_week_start," in q:
            week = params[0]
            out = []
            for wg in self.db["weekly_goals"]:
                if wg["week_start"] == week:
                    task = next(t for t in self.db["tasks"] if t["id"] == wg["task_id"])
                    project = next(p for p in self.db["projects"] if p["id"] == task["project_id"])
                    out.append(
                        {
                            "id": wg["id"],
                            "week_start": wg["week_start"],
                            "review_outcome": wg["review_outcome"],
                            "review_note": wg["review_note"],
                            "carried_to_week_start": wg["carried_to_week_start"],
                            "task_id": task["id"],
                            "title": task["title"],
                            "is_completed": task["is_completed"],
                            "project_name": project["name"],
                        }
                    )
            out.sort(key=lambda row: row["id"])
            self.results = out
            return
        if q.startswith("select id, title, project_id, due_date, priority, is_completed, completed_on, is_archived, archived_on, occurrence_date from tasks where id"):
            task_id = params[0]
            task = next((t for t in self.db["tasks"] if t["id"] == task_id), None)
            self.results = [task] if task else []
            return
        if q.startswith("select id, task_id, title, is_completed, position from subtasks where task_id"):
            task_id = params[0]
            out = [s for s in self.db["subtasks"] if s["task_id"] == task_id]
            out.sort(key=lambda s: (s["position"], s["id"]))
            self.results = out
            return
        if "from tasks t join projects p on p.id = t.project_id" in q:
            out = []
            for task in self.db["tasks"]:
                proj = next(p for p in self.db["projects"] if p["id"] == task["project_id"])
                if "where t.is_archived = 0 and p.is_archived = 0" in q and (task["is_archived"] == 1 or proj["is_archived"] == 1):
                    continue
                if "where t.is_completed = 0 and t.is_archived = 0 and p.is_archived = 0" in q and (
                    task["is_completed"] == 1 or task["is_archived"] == 1 or proj["is_archived"] == 1
                ):
                    continue
                if "where t.is_completed = 0 order by" in q and "t.is_archived = 0" not in q and task["is_completed"] == 1:
                    continue
                out.append(
                    {
                        "id": task["id"],
                        "title": task["title"],
                        "project_id": task["project_id"],
                        "due_date": task["due_date"],
                        "priority": task["priority"],
                        "is_completed": task["is_completed"],
                        "is_archived": task["is_archived"],
                        "archived_on": task["archived_on"],
                        "occurrence_date": task.get("occurrence_date"),
                        "project_name": proj["name"],
                    }
                )

            if "order by p.name, t.title, t.id" in q:
                out.sort(key=lambda t: (t["project_name"], t["title"], t["id"]))
            else:
                out.sort(key=lambda t: t["id"])
            self.results = out
            return
        if q.startswith("select * from "):
            table_name = q.split("select * from ", 1)[1]
            self.results = list(self.db[table_name])
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
            "project_templates": [],
            "project_template_tasks": [],
            "task_recurrence_rules": [],
            "task_recurrence_weekdays": [],
            "task_recurrence_month_days": [],
            "task_recurrence_year_days": [],
            "subtasks": [],
            "meetings": [],
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


@pytest.fixture()
def client(monkeypatch):
    webapp = pytest.importorskip("webapp")
    shared = FakeConnection()

    class FakeTracker(TimeOnTask):
        def __init__(self):
            super().__init__(connection_factory=lambda: shared)

        def close(self):
            return

    monkeypatch.setattr(webapp, "TimeOnTask", FakeTracker)
    webapp.app.config["TESTING"] = True
    with webapp.app.test_client() as client:
        yield client


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


def test_duplicate_detection_finds_open_task_in_same_project(tracker: TimeOnTask):
    tracker.add_project("Project A")
    tracker.add_task(1, "Status report")

    duplicates = tracker.find_duplicate_incomplete_tasks(1, " status report ")

    assert len(duplicates) == 1
    assert duplicates[0].task_id == 1


def test_projects_can_be_renamed_archived_and_restored(tracker: TimeOnTask):
    tracker.add_project("Projct A")

    tracker.rename_project(1, "Project A")
    tracker.archive_project(1, day=date(2026, 3, 23))

    active = tracker.list_projects()
    all_projects = tracker.list_projects(include_archived=True)
    assert active == []
    assert all_projects[0]["name"] == "Project A"
    assert all_projects[0]["is_archived"] == 1
    assert all_projects[0]["archived_on"] == "2026-03-23"

    tracker.restore_project(1)
    restored = tracker.list_projects()
    assert restored[0]["name"] == "Project A"
    assert restored[0]["is_archived"] == 0


def test_tasks_can_be_archived_and_restored(tracker: TimeOnTask):
    tracker.add_project("Project A")
    tracker.add_task(1, "Archive me")

    tracker.archive_task(1, day=date(2026, 3, 23))

    assert tracker.list_tasks() == []
    archived = tracker.list_tasks(include_archived=True)
    assert archived[0]["is_archived"] == 1
    assert archived[0]["archived_on"] == "2026-03-23"

    tracker.restore_task(1)
    restored = tracker.list_tasks()
    assert restored[0]["title"] == "Archive me"
    assert restored[0]["is_archived"] == 0


def test_snooze_task_moves_due_date_to_next_week_and_removes_from_today(tracker: TimeOnTask):
    tracker.add_project("Project A")
    tracker.add_task(1, "Snooze me", due_date="2026-03-23")
    tracker.select_today_task(1, day=date(2026, 3, 23))

    new_due_date = tracker.snooze_task_to_next_week(1, day=date(2026, 3, 23))

    task = tracker.get_task(1)
    today_rows = tracker.list_today(day=date(2026, 3, 23))
    assert new_due_date == "2026-03-30"
    assert task["due_date"] == "2026-03-30"
    assert today_rows == []


def test_subtasks_can_be_reordered(tracker: TimeOnTask):
    tracker.add_project("Project A")
    tracker.add_task(1, "Parent")
    tracker.add_subtask(1, "First")
    tracker.add_subtask(1, "Second")
    tracker.add_subtask(1, "Third")

    subtasks = tracker.list_subtasks(1)
    tracker.reorder_subtasks(1, [subtasks[2]["id"], subtasks[0]["id"], subtasks[1]["id"]])

    reordered = tracker.list_subtasks(1)
    assert [subtask["title"] for subtask in reordered] == ["Third", "First", "Second"]
    assert [subtask["position"] for subtask in reordered] == [1, 2, 3]


def test_project_templates_can_create_projects(tracker: TimeOnTask):
    template_id = tracker.add_project_template(
        "Client Launch",
        [
            {"title": "Kickoff", "due_offset_days": 0, "priority": 1},
            {"title": "Recap", "due_offset_days": 7, "priority": 2},
        ],
    )

    project_id = tracker.create_project_from_template(template_id, "Client A", starts_on="2026-03-24")

    project = tracker.get_project(project_id)
    tasks = [task for task in tracker.list_tasks() if task["project_id"] == project_id]
    assert project is not None
    assert project["name"] == "Client A"
    assert [task["title"] for task in tasks] == ["Kickoff", "Recap"]
    assert [task["due_date"] for task in tasks] == ["2026-03-24", "2026-03-31"]


def test_export_import_and_backup_helpers_round_trip(tracker: TimeOnTask, tmp_path: Path):
    tracker.add_project("Project A")
    tracker.add_task(1, "Task 1")
    export_path = tmp_path / "export.json"
    backup_path = tmp_path / "backup.json"

    tracker.export_to_file(str(export_path))
    payload = json.loads(export_path.read_text())
    assert payload["projects"][0]["name"] == "Project A"

    fresh = TimeOnTask(connection_factory=FakeConnection)
    fresh.import_from_file(str(export_path))
    assert fresh.list_projects()[0]["name"] == "Project A"
    assert fresh.list_tasks()[0]["title"] == "Task 1"
    written_backup = fresh.backup_to_file(str(backup_path))
    assert Path(written_backup).exists()
    fresh.close()


def test_load_dotenv_sets_missing_values_only(tmp_path: Path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("MYSQL_HOST=dotenv-host\nCUSTOM_FLAG=yes\n")
    monkeypatch.delenv("CUSTOM_FLAG", raising=False)
    monkeypatch.setenv("MYSQL_HOST", "already-set")

    load_dotenv(str(env_path))

    assert os.environ["MYSQL_HOST"] == "already-set"
    assert os.environ["CUSTOM_FLAG"] == "yes"


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


def test_recurring_template_rejects_end_date_before_start(tracker: TimeOnTask):
    tracker.add_project("Ops")

    with pytest.raises(ValueError, match="End date"):
        tracker.add_recurring_template(1, "Check backups", freq="daily", starts_on="2026-03-10", ends_on="2026-03-09")


def test_recurring_template_rejects_invalid_yearly_calendar_dates(tracker: TimeOnTask):
    tracker.add_project("Ops")

    with pytest.raises(ValueError, match="valid calendar dates"):
        tracker.add_recurring_template(1, "Impossible date", freq="yearly", year_dates_csv="02-30")


def test_task_edit_template_exists():
    assert Path("templates/task_edit.html").exists()


def test_subtasks_can_be_added_toggled_and_deleted(tracker: TimeOnTask):
    tracker.add_project("Project A")
    tracker.add_task(1, "Parent")

    tracker.add_subtask(1, "Child 1")
    tracker.add_subtask(1, "Child 2")

    subtasks = tracker.list_subtasks(1)
    assert [s["title"] for s in subtasks] == ["Child 1", "Child 2"]
    assert [s["position"] for s in subtasks] == [1, 2]

    tracker.set_subtask_completed(subtasks[0]["id"], True)
    subtasks = tracker.list_subtasks(1)
    assert subtasks[0]["is_completed"] == 1

    tracker.delete_subtask(subtasks[1]["id"])
    subtasks = tracker.list_subtasks(1)
    assert len(subtasks) == 1


def test_subtasks_do_not_change_parent_task_planning_semantics(tracker: TimeOnTask):
    tracker.add_project("Project A")
    tracker.add_task(1, "Parent")
    tracker.set_week_goal(1, day=date(2026, 3, 9))
    tracker.select_today_task(1, day=date(2026, 3, 10))

    tracker.add_subtask(1, "Child")
    child = tracker.list_subtasks(1)[0]
    tracker.set_subtask_completed(child["id"], True)

    review = tracker.week_review(day=date(2026, 3, 9))
    today_progress = tracker.end_of_day(day=date(2026, 3, 10))

    assert review.total == 1
    assert review.completed == 0
    assert today_progress.total == 1
    assert today_progress.completed == 0


def test_meetings_can_be_created_and_listed(tracker: TimeOnTask):
    tracker.add_project("Ops")
    tracker.add_meeting("Weekly Sync", weekday=2, start_time="09:30", duration_minutes=45, project_id=1)
    tracker.add_meeting("Planning", weekday=0, start_time="10:00", duration_minutes=30)

    meetings = tracker.list_meetings()
    assert len(meetings) == 2
    assert meetings[0]["weekday"] == 0
    assert meetings[1]["weekday"] == 2
    assert meetings[1]["project_name"] == "Ops"


def test_today_meetings_filter_by_weekday(tracker: TimeOnTask):
    tracker.add_meeting("Monday standup", weekday=0, start_time="08:00", duration_minutes=15)
    tracker.add_meeting("Tuesday standup", weekday=1, start_time="08:00", duration_minutes=15)

    monday = tracker.list_today_meetings(day=date(2026, 3, 9))
    tuesday = tracker.list_today_meetings(day=date(2026, 3, 10))

    assert len(monday) == 1
    assert monday[0]["title"] == "Monday standup"
    assert len(tuesday) == 1
    assert tuesday[0]["title"] == "Tuesday standup"


def test_create_task_from_meeting_uses_meeting_project(tracker: TimeOnTask):
    tracker.add_project("Ops")
    tracker.add_meeting("Weekly Sync", weekday=2, start_time="09:30", duration_minutes=45, project_id=1)

    task_id = tracker.create_task_from_meeting(1)

    task = tracker.get_task(task_id)
    assert task is not None
    assert task["project_id"] == 1
    assert task["title"] == "Follow up: Weekly Sync"


def test_create_task_from_meeting_allows_project_override(tracker: TimeOnTask):
    tracker.add_project("Ops")
    tracker.add_project("Admin")
    tracker.add_meeting("Staff Sync", weekday=2, start_time="09:30", duration_minutes=45)

    task_id = tracker.create_task_from_meeting(1, project_id=2, title="Send recap")

    task = tracker.get_task(task_id)
    assert task is not None
    assert task["project_id"] == 2
    assert task["title"] == "Send recap"


def test_create_task_from_meeting_requires_existing_meeting_and_project_choice(tracker: TimeOnTask):
    tracker.add_meeting("Staff Sync", weekday=2, start_time="09:30", duration_minutes=45)

    with pytest.raises(ValueError, match="project"):
        tracker.create_task_from_meeting(1)

    with pytest.raises(ValueError, match="Meeting not found"):
        tracker.create_task_from_meeting(999, project_id=1)


def test_week_goal_outcome_can_be_marked_deferred_or_blocked(tracker: TimeOnTask):
    tracker.add_project("Project A")
    tracker.add_task(1, "Parent")
    tracker.set_week_goal(1, day=date(2026, 3, 9))

    tracker.set_week_goal_outcome(1, "deferred", note="Priority changed")
    goals = tracker.list_week_goals(day=date(2026, 3, 9))
    assert goals[0]["review_outcome"] == "deferred"
    assert goals[0]["review_note"] == "Priority changed"

    tracker.set_week_goal_outcome(1, "blocked", note="Waiting on client")
    goals = tracker.list_week_goals(day=date(2026, 3, 9))
    assert goals[0]["review_outcome"] == "blocked"
    assert goals[0]["review_note"] == "Waiting on client"


def test_carry_week_goal_forward_creates_next_week_goal_and_preserves_task(tracker: TimeOnTask):
    tracker.add_project("Project A")
    tracker.add_task(1, "Parent")
    tracker.set_week_goal(1, day=date(2026, 3, 9))

    tracker.carry_week_goal_forward(1, day=date(2026, 3, 16), note="Still important")

    current_goals = tracker.list_week_goals(day=date(2026, 3, 9))
    next_goals = tracker.list_week_goals(day=date(2026, 3, 16))
    assert current_goals[0]["review_outcome"] == "carried_forward"
    assert current_goals[0]["review_note"] == "Still important"
    assert current_goals[0]["carried_to_week_start"] == "2026-03-16"
    assert len(next_goals) == 1
    assert next_goals[0]["task_id"] == 1
    assert next_goals[0]["review_outcome"] is None


def test_week_review_summary_breaks_out_goal_statuses(tracker: TimeOnTask):
    tracker.add_project("Project A")
    tracker.add_task(1, "Completed task")
    tracker.add_task(1, "Deferred task")
    tracker.add_task(1, "Blocked task")
    tracker.add_task(1, "Carry task")
    tracker.add_task(1, "Unreviewed task")

    for task_id in range(1, 6):
        tracker.set_week_goal(task_id, day=date(2026, 3, 9))

    tracker.complete_task(1)
    tracker.set_week_goal_outcome(2, "deferred", note="Later")
    tracker.set_week_goal_outcome(3, "blocked", note="Dependency")
    tracker.carry_week_goal_forward(4, day=date(2026, 3, 16), note="Next week")

    summary = tracker.week_review(day=date(2026, 3, 9))
    assert summary.total == 5
    assert summary.completed == 1
    assert summary.deferred == 1
    assert summary.blocked == 1
    assert summary.carried_forward == 1
    assert summary.unreviewed == 1


def test_week_review_includes_tasks_completed_during_week(tracker: TimeOnTask):
    tracker.add_project("Project A")
    tracker.add_task(1, "Finished this week")
    tracker.add_task(1, "Finished later")

    tracker.complete_task(1, day=date(2026, 3, 10))
    tracker.complete_task(2, day=date(2026, 3, 18))

    completed = tracker.list_completed_tasks_for_week(day=date(2026, 3, 9))
    summary = tracker.week_review(day=date(2026, 3, 9))

    assert [task["title"] for task in completed] == ["Finished this week"]
    assert summary.completed_tasks == 1


def test_week_goal_outcome_validation_rejects_unknown_outcomes(tracker: TimeOnTask):
    tracker.add_project("Project A")
    tracker.add_task(1, "Parent")
    tracker.set_week_goal(1, day=date(2026, 3, 9))

    with pytest.raises(ValueError, match="Goal outcome"):
        tracker.set_week_goal_outcome(1, "done")

    with pytest.raises(ValueError, match="Weekly goal not found"):
        tracker.carry_week_goal_forward(999, day=date(2026, 3, 16))


def test_add_meeting_validates_inputs(tracker: TimeOnTask):
    with pytest.raises(ValueError, match="Meeting title"):
        tracker.add_meeting("", weekday=0, start_time="09:00", duration_minutes=30)

    with pytest.raises(ValueError, match="Weekday"):
        tracker.add_meeting("Invalid weekday", weekday=7, start_time="09:00", duration_minutes=30)

    with pytest.raises(ValueError, match="Start time"):
        tracker.add_meeting("Invalid time", weekday=1, start_time="9am", duration_minutes=30)

    with pytest.raises(ValueError, match="Duration"):
        tracker.add_meeting("Invalid duration", weekday=1, start_time="09:00", duration_minutes=0)


def test_meetings_do_not_affect_two_task_today_limit(tracker: TimeOnTask):
    tracker.add_project("Main")
    tracker.add_task(1, "Task 1")
    tracker.add_task(1, "Task 2")
    tracker.add_task(1, "Task 3")
    tracker.add_meeting("Standup", weekday=0, start_time="09:00", duration_minutes=15)

    monday = date(2026, 3, 9)
    tracker.select_today_task(1, monday)
    tracker.select_today_task(2, monday)

    # Meetings shown on Today should not alter task-cap semantics.
    assert len(tracker.list_today_meetings(monday)) == 1
    with pytest.raises(ValueError, match="Cannot add more than two active tasks"):
        tracker.select_today_task(3, monday)


def test_meetings_template_exists():
    assert Path("templates/meetings.html").exists()


def test_week_review_template_exists():
    assert Path("templates/week_review.html").exists()


def test_today_view_groups_picker_by_project_and_marks_overdue(client):
    client.post("/projects", data={"name": "Alpha"})
    client.post("/projects", data={"name": "Beta"})
    client.post("/tasks", data={"title": "Late task", "project_id": "1", "due_date": "2026-03-01", "priority": ""})
    client.post("/tasks", data={"title": "Current task", "project_id": "2", "due_date": "", "priority": ""})
    client.post("/today", data={"task_id": "1"})

    response = client.get("/today")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<optgroup label="Alpha">' in html
    assert '<optgroup label="Beta">' in html
    assert "OVERDUE" in html
    assert "Mark Complete" in html


def test_tasks_view_shows_project_quick_add_and_duplicate_warning(client):
    client.post("/projects", data={"name": "Alpha"})
    client.post("/tasks?sort=project", data={"title": "Status report", "project_id": "1", "due_date": "", "priority": ""})
    duplicate_response = client.post(
        "/tasks?sort=project",
        data={"title": "Status report", "project_id": "1", "due_date": "", "priority": ""},
        follow_redirects=True,
    )

    html = duplicate_response.get_data(as_text=True)

    assert duplicate_response.status_code == 200
    assert "Possible duplicate" in html
    assert "Quick add task for Alpha" in html


def test_week_review_view_lists_completed_tasks(client):
    client.post("/projects", data={"name": "Alpha"})
    client.post("/tasks", data={"title": "Wrap up", "project_id": "1", "due_date": "2026-03-01", "priority": ""})
    client.post("/tasks/1/complete")

    response = client.get("/week-review")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Completed Tasks This Week" in html
    assert "Wrap up" in html


def test_projects_view_supports_rename_archive_and_restore(client):
    client.post("/projects", data={"name": "Projct A"})
    client.post("/projects/1/edit", data={"name": "Project A"})

    renamed = client.get("/projects").get_data(as_text=True)
    assert "Project A" in renamed
    assert "Rename" in renamed

    client.post("/projects/1/archive")
    archived = client.get("/projects").get_data(as_text=True)
    assert "Archived Projects" in archived
    assert "Restore" in archived

    client.post("/projects/1/restore")
    restored = client.get("/projects").get_data(as_text=True)
    assert "Project A" in restored


def test_tasks_view_and_edit_support_archive_and_restore(client):
    client.post("/projects", data={"name": "Alpha"})
    client.post("/tasks", data={"title": "Archive me", "project_id": "1", "due_date": "", "priority": ""})

    edit_page = client.get("/tasks/1/edit").get_data(as_text=True)
    assert "Archive Task" in edit_page

    client.post("/tasks/1/archive", data={"sort": "created"})
    archived_page = client.get("/tasks").get_data(as_text=True)
    assert "Archived Tasks" in archived_page
    assert "Restore" in archived_page

    client.post("/tasks/1/restore", data={"sort": "created"})
    restored_page = client.get("/tasks").get_data(as_text=True)
    assert "Archive me" in restored_page


def test_project_dashboard_and_snooze_flow(client):
    client.post("/projects", data={"name": "Alpha"})
    client.post("/tasks", data={"title": "Plan sprint", "project_id": "1", "due_date": "2026-03-23", "priority": ""})

    dashboard_html = client.get("/projects/1").get_data(as_text=True)
    assert "Project: Alpha" in dashboard_html
    assert "Plan sprint" in dashboard_html

    client.post("/tasks/1/snooze", data={"project_id": "1"}, follow_redirects=True)
    updated_html = client.get("/projects/1").get_data(as_text=True)
    assert "2026-03-30" in updated_html
    assert "Snooze to Next Week" in updated_html


def test_projects_view_can_create_project_from_template(client):
    client.post("/project-templates", data={"name": "Starter", "task_lines": "Task A\nTask B"}, follow_redirects=True)

    projects_page = client.get("/projects").get_data(as_text=True)
    assert "Starter" in projects_page
    assert "Create Project" in projects_page

    response = client.post(
        "/project-templates/1/instantiate",
        data={"project_name": "Template Project", "starts_on": "2026-03-24"},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)
    assert "Project: Template Project" in html
    assert "Task A" in html
    assert "Task B" in html


def test_recurring_tasks_show_in_tasks_today_and_project_dashboard(client):
    client.post("/projects", data={"name": "Alpha"})
    client.post(
        "/tasks/recurring",
        data={
            "title": "Daily recurring",
            "project_id": "1",
            "freq": "DAILY",
            "interval_n": "1",
            "starts_on": "2026-03-01",
            "ends_on": "",
            "weekdays": "",
            "month_days": "",
            "year_dates": "",
            "due_date": "2026-03-25",
            "priority": "2",
            "sort": "project",
        },
        follow_redirects=True,
    )

    tasks_html = client.get("/tasks?sort=project").get_data(as_text=True)
    today_html = client.get("/today").get_data(as_text=True)
    project_html = client.get("/projects/1").get_data(as_text=True)

    assert "Daily recurring" in tasks_html
    assert "Daily recurring" in today_html
    assert "Daily recurring" in project_html


def test_meetings_can_be_edited_from_meetings_page(client):
    client.post("/projects", data={"name": "Alpha"})
    client.post(
        "/meetings",
        data={
            "title": "Weekly Sync",
            "project_id": "1",
            "weekday": "2",
            "start_time": "09:00",
            "duration_minutes": "30",
        },
    )
    response = client.post(
        "/meetings/1/edit",
        data={
            "title": "Team Sync",
            "project_id": "1",
            "weekday": "3",
            "start_time": "10:15",
            "duration_minutes": "45",
        },
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)
    assert "Meeting updated." in html
    assert "Team Sync" in html


def test_recurring_task_template_can_be_edited(client):
    client.post("/projects", data={"name": "Alpha"})
    client.post("/projects", data={"name": "Beta"})
    client.post(
        "/tasks/recurring",
        data={
            "title": "Daily recurring",
            "project_id": "1",
            "freq": "DAILY",
            "interval_n": "1",
            "starts_on": "2026-03-01",
            "ends_on": "",
            "weekdays": "",
            "month_days": "",
            "year_dates": "",
            "due_date": "",
            "priority": "",
            "sort": "project",
        },
        follow_redirects=True,
    )
    response = client.post(
        "/tasks/recurring/1/edit",
        data={
            "title": "Daily recurring updated",
            "project_id": "2",
            "freq": "WEEKLY",
            "interval_n": "1",
            "starts_on": "2026-03-01",
            "ends_on": "",
            "weekdays": "2",
            "month_days": "",
            "year_dates": "",
            "due_date": "",
            "priority": "2",
            "sort": "project",
        },
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)
    assert "Recurring template updated." in html
    assert "Daily recurring updated" in html
    assert "Beta" in html


def test_week_review_uses_clear_completed_labels(client):
    client.post("/projects", data={"name": "Alpha"})
    client.post("/tasks", data={"title": "Plan sprint", "project_id": "1"})
    client.post("/weekly-goals", data={"task_id": "1"})
    html = client.get("/week-review").get_data(as_text=True)
    assert "Completed Goals" in html
    assert "Weekly goals completed." in html
    assert "Completed Tasks This Week" in html
    assert "All tasks completed this week." in html
