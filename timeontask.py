from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Iterable


@dataclass
class GoalProgress:
    total: int
    completed: int


def create_mysql_connection() -> Any:
    import mysql.connector

    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "timeontask"),
        autocommit=False,
    )


class TimeOnTask:
    def __init__(self, connection_factory: Callable[[], Any] = create_mysql_connection):
        self.conn = connection_factory()
        self._init_db()

    def close(self) -> None:
        self.conn.close()

    def _init_db(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
              id INT PRIMARY KEY AUTO_INCREMENT,
              name VARCHAR(255) NOT NULL UNIQUE
            ) ENGINE=InnoDB
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
              id INT PRIMARY KEY AUTO_INCREMENT,
              project_id INT NOT NULL,
              title VARCHAR(255) NOT NULL,
              due_date DATE NULL,
              priority TINYINT NULL,
              is_completed TINYINT(1) NOT NULL DEFAULT 0,
              FOREIGN KEY (project_id) REFERENCES projects(id)
            ) ENGINE=InnoDB
            """
        )
        cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS due_date DATE NULL")
        cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS priority TINYINT NULL")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS weekly_goals (
              id INT PRIMARY KEY AUTO_INCREMENT,
              week_start DATE NOT NULL,
              task_id INT NOT NULL,
              UNIQUE KEY uniq_week_task (week_start, task_id),
              FOREIGN KEY (task_id) REFERENCES tasks(id)
            ) ENGINE=InnoDB
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_selection (
              id INT PRIMARY KEY AUTO_INCREMENT,
              day_date DATE NOT NULL,
              task_id INT NOT NULL,
              UNIQUE KEY uniq_day_task (day_date, task_id),
              FOREIGN KEY (task_id) REFERENCES tasks(id)
            ) ENGINE=InnoDB
            """
        )
        cur.close()
        self.conn.commit()

    @staticmethod
    def _normalize_due_date(due_date: str | None) -> str | None:
        if due_date is None:
            return None
        clean = due_date.strip()
        if not clean:
            return None
        try:
            return date.fromisoformat(clean).isoformat()
        except ValueError as exc:
            raise ValueError("Due date must be YYYY-MM-DD.") from exc

    @staticmethod
    def _normalize_priority(priority: str | int | None) -> int | None:
        if priority is None:
            return None
        if isinstance(priority, str):
            clean = priority.strip()
            if not clean:
                return None
            try:
                parsed = int(clean)
            except ValueError as exc:
                raise ValueError("Priority must be 1, 2, or 3.") from exc
        else:
            parsed = int(priority)

        if parsed not in {1, 2, 3}:
            raise ValueError("Priority must be 1, 2, or 3.")
        return parsed

    @staticmethod
    def week_start(day: date | None = None) -> str:
        today = day or date.today()
        return (today - timedelta(days=today.weekday())).isoformat()

    def add_project(self, name: str) -> None:
        cur = self.conn.cursor()
        cur.execute("INSERT INTO projects (name) VALUES (%s)", (name.strip(),))
        cur.close()
        self.conn.commit()

    def add_task(
        self,
        project_id: int,
        title: str,
        due_date: str | None = None,
        priority: str | int | None = None,
    ) -> None:
        due_date_iso = self._normalize_due_date(due_date)
        priority_val = self._normalize_priority(priority)

        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO tasks (project_id, title, due_date, priority, is_completed) VALUES (%s, %s, %s, %s, 0)",
            (project_id, title.strip(), due_date_iso, priority_val),
        )
        cur.close()
        self.conn.commit()

    def add_task_batch(
        self,
        project_id: int,
        base_title: str,
        count: int,
        due_date: str | None = None,
        priority: str | int | None = None,
    ) -> int:
        clean_title = base_title.strip()
        if not clean_title:
            raise ValueError("Base title is required.")
        if count < 1:
            raise ValueError("Count must be at least 1.")
        due_date_iso = self._normalize_due_date(due_date)
        priority_val = self._normalize_priority(priority)

        cur = self.conn.cursor()
        try:
            for idx in range(1, count + 1):
                cur.execute(
                    "INSERT INTO tasks (project_id, title, due_date, priority, is_completed) VALUES (%s, %s, %s, %s, 0)",
                    (project_id, f"{clean_title} {idx}", due_date_iso, priority_val),
                )
        finally:
            cur.close()
        self.conn.commit()
        return count

    def set_week_goal(self, task_id: int, day: date | None = None) -> None:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT IGNORE INTO weekly_goals (week_start, task_id) VALUES (%s, %s)",
            (self.week_start(day), task_id),
        )
        cur.close()
        self.conn.commit()

    def select_today_task(self, task_id: int, day: date | None = None) -> None:
        today = (day or date.today()).isoformat()
        cur = self.conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT COUNT(*) AS open_count
            FROM daily_selection ds
            JOIN tasks t ON t.id = ds.task_id
            WHERE ds.day_date = %s AND t.is_completed = 0
            """,
            (today,),
        )
        open_count = cur.fetchone()["open_count"]

        if open_count >= 2:
            cur.close()
            raise ValueError("Cannot add more than two active tasks. Finish selected tasks first.")

        cur.execute(
            "INSERT IGNORE INTO daily_selection (day_date, task_id) VALUES (%s, %s)",
            (today, task_id),
        )
        cur.close()
        self.conn.commit()

    def complete_task(self, task_id: int) -> None:
        cur = self.conn.cursor()
        cur.execute("UPDATE tasks SET is_completed = 1 WHERE id = %s", (task_id,))
        cur.close()
        self.conn.commit()

    def list_today(self, day: date | None = None) -> list[dict[str, Any]]:
        today = (day or date.today()).isoformat()
        cur = self.conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT t.id, t.title, t.due_date, t.priority, t.is_completed, p.name AS project_name
            FROM daily_selection ds
            JOIN tasks t ON t.id = ds.task_id
            JOIN projects p ON p.id = t.project_id
            WHERE ds.day_date = %s
            ORDER BY ds.id
            """,
            (today,),
        )
        rows = cur.fetchall()
        cur.close()
        return rows

    def end_of_day(self, day: date | None = None) -> GoalProgress:
        rows = self.list_today(day)
        done = sum(1 for r in rows if r["is_completed"])
        return GoalProgress(total=len(rows), completed=done)

    def week_review(self, day: date | None = None) -> GoalProgress:
        cur = self.conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT t.is_completed
            FROM weekly_goals wg
            JOIN tasks t ON t.id = wg.task_id
            WHERE wg.week_start = %s
            """,
            (self.week_start(day),),
        )
        rows = cur.fetchall()
        cur.close()
        done = sum(1 for r in rows if r["is_completed"])
        return GoalProgress(total=len(rows), completed=done)

    def list_projects(self) -> list[dict[str, Any]]:
        cur = self.conn.cursor(dictionary=True)
        cur.execute("SELECT id, name FROM projects ORDER BY name")
        rows = cur.fetchall()
        cur.close()
        return rows


    def list_incomplete_tasks(self) -> list[dict[str, Any]]:
        cur = self.conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT t.id, t.title, t.project_id, t.due_date, t.priority, p.name AS project_name
            FROM tasks t
            JOIN projects p ON p.id = t.project_id
            WHERE t.is_completed = 0
            ORDER BY t.id
            """
        )
        rows = cur.fetchall()
        cur.close()
        return rows

    def list_week_goals(self, day: date | None = None) -> list[dict[str, Any]]:
        cur = self.conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT wg.id, wg.week_start, t.id AS task_id, t.title, t.is_completed, p.name AS project_name
            FROM weekly_goals wg
            JOIN tasks t ON t.id = wg.task_id
            JOIN projects p ON p.id = t.project_id
            WHERE wg.week_start = %s
            ORDER BY wg.id
            """,
            (self.week_start(day),),
        )
        rows = cur.fetchall()
        cur.close()
        return rows

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        cur = self.conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, title, project_id, due_date, priority, is_completed FROM tasks WHERE id = %s",
            (task_id,),
        )
        row = cur.fetchone()
        cur.close()
        return row

    def update_task(
        self,
        task_id: int,
        project_id: int,
        title: str,
        is_completed: bool,
        due_date: str | None = None,
        priority: str | int | None = None,
    ) -> None:
        due_date_iso = self._normalize_due_date(due_date)
        priority_val = self._normalize_priority(priority)

        cur = self.conn.cursor()
        cur.execute(
            "UPDATE tasks SET project_id = %s, title = %s, due_date = %s, priority = %s, is_completed = %s WHERE id = %s",
            (project_id, title.strip(), due_date_iso, priority_val, int(is_completed), task_id),
        )
        cur.close()
        self.conn.commit()

    def list_tasks(self, sort_by: str = "created") -> list[dict[str, Any]]:
        order_clause = "t.id"
        if sort_by == "project":
            order_clause = "p.name, t.title, t.id"

        cur = self.conn.cursor(dictionary=True)
        cur.execute(
            f"""
            SELECT t.id, t.title, t.project_id, t.due_date, t.priority, t.is_completed, p.name AS project_name
            FROM tasks t
            JOIN projects p ON p.id = t.project_id
            ORDER BY {order_clause}
            """
        )
        rows = cur.fetchall()
        cur.close()
        return rows


def print_rows(rows: Iterable[dict[str, Any]]) -> None:
    for row in rows:
        print(row)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Time on Task CLI (MariaDB/MySQL)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add-project")
    p.add_argument("name")

    t = sub.add_parser("add-task")
    t.add_argument("project_id", type=int)
    t.add_argument("title")
    t.add_argument("--due-date")
    t.add_argument("--priority", type=int, choices=[1, 2, 3])

    g = sub.add_parser("set-goal")
    g.add_argument("task_id", type=int)

    s = sub.add_parser("select-today")
    s.add_argument("task_id", type=int)

    c = sub.add_parser("complete")
    c.add_argument("task_id", type=int)

    sub.add_parser("today")
    sub.add_parser("end-of-day")
    sub.add_parser("week-review")
    sub.add_parser("projects")
    sub.add_parser("tasks")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    app = TimeOnTask()

    try:
        if args.command == "add-project":
            app.add_project(args.name)
            print("Project added")
        elif args.command == "add-task":
            app.add_task(args.project_id, args.title, due_date=args.due_date, priority=args.priority)
            print("Task added")
        elif args.command == "set-goal":
            app.set_week_goal(args.task_id)
            print("Goal set")
        elif args.command == "select-today":
            app.select_today_task(args.task_id)
            print("Task selected")
        elif args.command == "complete":
            app.complete_task(args.task_id)
            print("Task completed")
        elif args.command == "today":
            print_rows(app.list_today())
        elif args.command == "end-of-day":
            p = app.end_of_day()
            print(f"Completed today: {p.completed}/{p.total}")
        elif args.command == "week-review":
            p = app.week_review()
            print(f"Week goal progress: {p.completed}/{p.total}")
        elif args.command == "projects":
            print_rows(app.list_projects())
        elif args.command == "tasks":
            print_rows(app.list_tasks())
    finally:
        app.close()


if __name__ == "__main__":
    main()
