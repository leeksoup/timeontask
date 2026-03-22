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
            CREATE TABLE IF NOT EXISTS meetings (
              id INT PRIMARY KEY AUTO_INCREMENT,
              project_id INT NULL,
              title VARCHAR(255) NOT NULL,
              weekday TINYINT NOT NULL,
              start_time TIME NOT NULL,
              duration_minutes INT NOT NULL,
              is_active TINYINT(1) NOT NULL DEFAULT 1,
              FOREIGN KEY (project_id) REFERENCES projects(id)
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
              template_id INT NULL,
              source_meeting_id INT NULL,
              occurrence_date DATE NULL,
              is_completed TINYINT(1) NOT NULL DEFAULT 0,
              FOREIGN KEY (project_id) REFERENCES projects(id),
              FOREIGN KEY (source_meeting_id) REFERENCES meetings(id)
            ) ENGINE=InnoDB
            """
        )
        cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS due_date DATE NULL")
        cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS priority TINYINT NULL")
        cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS template_id INT NULL")
        cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS source_meeting_id INT NULL")
        cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS occurrence_date DATE NULL")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS subtasks (
              id INT PRIMARY KEY AUTO_INCREMENT,
              task_id INT NOT NULL,
              title VARCHAR(255) NOT NULL,
              is_completed TINYINT(1) NOT NULL DEFAULT 0,
              position INT NOT NULL,
              FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            ) ENGINE=InnoDB
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS task_templates (
              id INT PRIMARY KEY AUTO_INCREMENT,
              project_id INT NOT NULL,
              title VARCHAR(255) NOT NULL,
              due_date DATE NULL,
              priority TINYINT NULL,
              is_active TINYINT(1) NOT NULL DEFAULT 1,
              FOREIGN KEY (project_id) REFERENCES projects(id)
            ) ENGINE=InnoDB
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS task_recurrence_rules (
              id INT PRIMARY KEY AUTO_INCREMENT,
              template_id INT NOT NULL,
              freq VARCHAR(16) NOT NULL,
              interval_n INT NOT NULL DEFAULT 1,
              starts_on DATE NOT NULL,
              ends_on DATE NULL,
              FOREIGN KEY (template_id) REFERENCES task_templates(id)
            ) ENGINE=InnoDB
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS task_recurrence_weekdays (
              id INT PRIMARY KEY AUTO_INCREMENT,
              rule_id INT NOT NULL,
              weekday TINYINT NOT NULL,
              UNIQUE KEY uniq_rule_weekday (rule_id, weekday),
              FOREIGN KEY (rule_id) REFERENCES task_recurrence_rules(id)
            ) ENGINE=InnoDB
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS task_recurrence_month_days (
              id INT PRIMARY KEY AUTO_INCREMENT,
              rule_id INT NOT NULL,
              day_of_month TINYINT NOT NULL,
              UNIQUE KEY uniq_rule_month_day (rule_id, day_of_month),
              FOREIGN KEY (rule_id) REFERENCES task_recurrence_rules(id)
            ) ENGINE=InnoDB
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS task_recurrence_year_days (
              id INT PRIMARY KEY AUTO_INCREMENT,
              rule_id INT NOT NULL,
              month_num TINYINT NOT NULL,
              day_of_month TINYINT NOT NULL,
              UNIQUE KEY uniq_rule_year_day (rule_id, month_num, day_of_month),
              FOREIGN KEY (rule_id) REFERENCES task_recurrence_rules(id)
            ) ENGINE=InnoDB
            """
        )
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

    @staticmethod
    def _parse_csv_ints(value: str | None, minimum: int, maximum: int) -> list[int]:
        if not value:
            return []
        items: list[int] = []
        for token in value.split(","):
            clean = token.strip()
            if not clean:
                continue
            try:
                parsed = int(clean)
            except ValueError as exc:
                raise ValueError("Expected comma-separated numbers.") from exc
            if parsed < minimum or parsed > maximum:
                raise ValueError(f"Values must be between {minimum} and {maximum}.")
            items.append(parsed)
        return sorted(set(items))

    @staticmethod
    def _parse_year_dates(value: str | None) -> list[tuple[int, int]]:
        if not value:
            return []
        out: list[tuple[int, int]] = []
        for token in value.split(","):
            clean = token.strip()
            if not clean:
                continue
            try:
                month_part, day_part = clean.split("-", 1)
                month_num = int(month_part)
                day_num = int(day_part)
            except ValueError as exc:
                raise ValueError("Yearly dates must be MM-DD, comma-separated.") from exc
            if month_num < 1 or month_num > 12 or day_num < 1 or day_num > 31:
                raise ValueError("Yearly MM-DD values are out of range.")
            out.append((month_num, day_num))
        return sorted(set(out))

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

    def add_recurring_template(
        self,
        project_id: int,
        title: str,
        freq: str,
        interval_n: int = 1,
        starts_on: str | None = None,
        ends_on: str | None = None,
        weekdays_csv: str | None = None,
        month_days_csv: str | None = None,
        year_dates_csv: str | None = None,
        due_date: str | None = None,
        priority: str | int | None = None,
    ) -> int:
        freq_clean = freq.strip().upper()
        if freq_clean not in {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}:
            raise ValueError("Frequency must be daily, weekly, monthly, or yearly.")
        if interval_n < 1:
            raise ValueError("Interval must be at least 1.")

        starts_on_iso = self._normalize_due_date(starts_on) or date.today().isoformat()
        ends_on_iso = self._normalize_due_date(ends_on)
        due_date_iso = self._normalize_due_date(due_date)
        priority_val = self._normalize_priority(priority)
        weekdays = self._parse_csv_ints(weekdays_csv, 0, 6)
        month_days = self._parse_csv_ints(month_days_csv, 1, 31)
        year_dates = self._parse_year_dates(year_dates_csv)

        cur = self.conn.cursor()
        try:
            cur.execute(
                "INSERT INTO task_templates (project_id, title, due_date, priority, is_active) VALUES (%s, %s, %s, %s, 1)",
                (project_id, title.strip(), due_date_iso, priority_val),
            )
            template_id = cur.lastrowid
            cur.execute(
                "INSERT INTO task_recurrence_rules (template_id, freq, interval_n, starts_on, ends_on) VALUES (%s, %s, %s, %s, %s)",
                (template_id, freq_clean, interval_n, starts_on_iso, ends_on_iso),
            )
            rule_id = cur.lastrowid

            for weekday in weekdays:
                cur.execute(
                    "INSERT IGNORE INTO task_recurrence_weekdays (rule_id, weekday) VALUES (%s, %s)",
                    (rule_id, weekday),
                )
            for day_of_month in month_days:
                cur.execute(
                    "INSERT IGNORE INTO task_recurrence_month_days (rule_id, day_of_month) VALUES (%s, %s)",
                    (rule_id, day_of_month),
                )
            for month_num, day_of_month in year_dates:
                cur.execute(
                    "INSERT IGNORE INTO task_recurrence_year_days (rule_id, month_num, day_of_month) VALUES (%s, %s, %s)",
                    (rule_id, month_num, day_of_month),
                )
        finally:
            cur.close()

        self.conn.commit()
        return template_id

    def _rule_matches_date(
        self,
        rule: dict[str, Any],
        target_date: date,
        weekdays: list[int],
        month_days: list[int],
        year_dates: list[tuple[int, int]],
    ) -> bool:
        starts_on = date.fromisoformat(str(rule["starts_on"]))
        if target_date < starts_on:
            return False

        ends_on_raw = rule.get("ends_on")
        if ends_on_raw:
            ends_on = date.fromisoformat(str(ends_on_raw))
            if target_date > ends_on:
                return False

        interval_n = int(rule.get("interval_n") or 1)
        freq = str(rule["freq"]).upper()
        if freq == "DAILY":
            return (target_date - starts_on).days % interval_n == 0

        if freq == "WEEKLY":
            week_delta = (target_date - starts_on).days // 7
            if week_delta < 0 or week_delta % interval_n != 0:
                return False
            active_weekdays = weekdays or [starts_on.weekday()]
            return target_date.weekday() in active_weekdays

        if freq == "MONTHLY":
            months_delta = (target_date.year - starts_on.year) * 12 + (target_date.month - starts_on.month)
            if months_delta < 0 or months_delta % interval_n != 0:
                return False
            active_days = month_days or [starts_on.day]
            return target_date.day in active_days

        if freq == "YEARLY":
            years_delta = target_date.year - starts_on.year
            if years_delta < 0 or years_delta % interval_n != 0:
                return False
            active_dates = year_dates or [(starts_on.month, starts_on.day)]
            return (target_date.month, target_date.day) in active_dates

        return False

    def generate_recurring_tasks(self, day: date | None = None, horizon_days: int = 0) -> int:
        start_day = day or date.today()
        end_day = start_day + timedelta(days=max(0, horizon_days))

        created = 0
        cur = self.conn.cursor(dictionary=True)
        try:
            cur.execute(
                """
                SELECT r.id, r.template_id, r.freq, r.interval_n, r.starts_on, r.ends_on,
                       t.project_id, t.title, t.due_date, t.priority
                FROM task_recurrence_rules r
                JOIN task_templates t ON t.id = r.template_id
                WHERE t.is_active = 1
                ORDER BY r.id
                """
            )
            rules = cur.fetchall()

            for rule in rules:
                cur.execute("SELECT weekday FROM task_recurrence_weekdays WHERE rule_id = %s", (rule["id"],))
                weekdays = [row["weekday"] for row in cur.fetchall()]

                cur.execute(
                    "SELECT day_of_month FROM task_recurrence_month_days WHERE rule_id = %s",
                    (rule["id"],),
                )
                month_days = [row["day_of_month"] for row in cur.fetchall()]

                cur.execute(
                    "SELECT month_num, day_of_month FROM task_recurrence_year_days WHERE rule_id = %s",
                    (rule["id"],),
                )
                year_dates = [(row["month_num"], row["day_of_month"]) for row in cur.fetchall()]

                current = start_day
                while current <= end_day:
                    if self._rule_matches_date(rule, current, weekdays, month_days, year_dates):
                        occurrence = current.isoformat()
                        cur.execute(
                            "SELECT id FROM tasks WHERE template_id = %s AND occurrence_date = %s",
                            (rule["template_id"], occurrence),
                        )
                        exists = cur.fetchone()
                        if not exists:
                            cur.execute(
                                """
                                INSERT INTO tasks
                                  (project_id, title, due_date, priority, template_id, occurrence_date, is_completed)
                                VALUES (%s, %s, %s, %s, %s, %s, 0)
                                """,
                                (
                                    rule["project_id"],
                                    rule["title"],
                                    rule.get("due_date"),
                                    rule.get("priority"),
                                    rule["template_id"],
                                    occurrence,
                                ),
                            )
                            created += 1
                    current += timedelta(days=1)
        finally:
            cur.close()

        self.conn.commit()
        return created

    def list_recurring_templates(self) -> list[dict[str, Any]]:
        cur = self.conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT t.id, t.title, t.project_id, p.name AS project_name, r.freq, r.interval_n, r.starts_on, r.ends_on
            FROM task_templates t
            JOIN task_recurrence_rules r ON r.template_id = t.id
            JOIN projects p ON p.id = t.project_id
            WHERE t.is_active = 1
            ORDER BY t.id
            """
        )
        rows = cur.fetchall()
        cur.close()
        return rows

    def add_meeting(
        self,
        title: str,
        weekday: int,
        start_time: str,
        duration_minutes: int,
        project_id: int | None = None,
    ) -> None:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Meeting title is required.")
        if weekday < 0 or weekday > 6:
            raise ValueError("Weekday must be between 0 (Mon) and 6 (Sun).")
        if duration_minutes < 1:
            raise ValueError("Duration must be at least 1 minute.")
        try:
            parts = start_time.strip().split(":")
            if len(parts) != 2:
                raise ValueError
            hh = int(parts[0])
            mm = int(parts[1])
            if hh < 0 or hh > 23 or mm < 0 or mm > 59:
                raise ValueError
            start_time_clean = f"{hh:02d}:{mm:02d}:00"
        except ValueError as exc:
            raise ValueError("Start time must be HH:MM (24-hour).") from exc

        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO meetings (project_id, title, weekday, start_time, duration_minutes, is_active)
            VALUES (%s, %s, %s, %s, %s, 1)
            """,
            (project_id, clean_title, weekday, start_time_clean, duration_minutes),
        )
        cur.close()
        self.conn.commit()

    def get_meeting(self, meeting_id: int) -> dict[str, Any] | None:
        cur = self.conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT m.id, m.project_id, m.title, m.weekday, m.start_time, m.duration_minutes, m.is_active,
                   p.name AS project_name
            FROM meetings m
            LEFT JOIN projects p ON p.id = m.project_id
            WHERE m.id = %s
            """,
            (meeting_id,),
        )
        row = cur.fetchone()
        cur.close()
        return row

    def create_task_from_meeting(
        self,
        meeting_id: int,
        project_id: int | None = None,
        title: str | None = None,
        due_date: str | None = None,
        priority: str | int | None = None,
    ) -> int:
        meeting = self.get_meeting(meeting_id)
        if meeting is None or int(meeting["is_active"]) != 1:
            raise ValueError("Meeting not found.")

        resolved_project_id = project_id if project_id is not None else meeting["project_id"]
        if resolved_project_id is None:
            raise ValueError("Choose a project for this follow-up task.")

        task_title = (title or f"Follow up: {meeting['title']}").strip()
        if not task_title:
            raise ValueError("Task title is required.")

        due_date_iso = self._normalize_due_date(due_date)
        priority_val = self._normalize_priority(priority)

        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO tasks (project_id, title, due_date, priority, template_id, source_meeting_id, occurrence_date, is_completed)
            VALUES (%s, %s, %s, %s, NULL, %s, NULL, 0)
            """,
            (resolved_project_id, task_title, due_date_iso, priority_val, meeting_id),
        )
        task_id = cur.lastrowid
        cur.close()
        self.conn.commit()
        return task_id

    def list_meetings(self) -> list[dict[str, Any]]:
        cur = self.conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT m.id, m.project_id, m.title, m.weekday, m.start_time, m.duration_minutes, m.is_active,
                   p.name AS project_name
            FROM meetings m
            LEFT JOIN projects p ON p.id = m.project_id
            WHERE m.is_active = 1
            ORDER BY m.weekday, m.start_time, m.id
            """
        )
        rows = cur.fetchall()
        cur.close()
        return rows

    def list_today_meetings(self, day: date | None = None) -> list[dict[str, Any]]:
        target = day or date.today()
        cur = self.conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT m.id, m.project_id, m.title, m.weekday, m.start_time, m.duration_minutes, m.is_active,
                   p.name AS project_name
            FROM meetings m
            LEFT JOIN projects p ON p.id = m.project_id
            WHERE m.is_active = 1 AND m.weekday = %s
            ORDER BY m.start_time, m.id
            """,
            (target.weekday(),),
        )
        rows = cur.fetchall()
        cur.close()
        return rows

    def add_subtask(self, task_id: int, title: str) -> None:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Subtask title is required.")

        cur = self.conn.cursor(dictionary=True)
        cur.execute("SELECT COALESCE(MAX(position), 0) AS max_position FROM subtasks WHERE task_id = %s", (task_id,))
        max_position = cur.fetchone()["max_position"]
        cur.execute(
            "INSERT INTO subtasks (task_id, title, is_completed, position) VALUES (%s, %s, 0, %s)",
            (task_id, clean_title, int(max_position) + 1),
        )
        cur.close()
        self.conn.commit()

    def list_subtasks(self, task_id: int) -> list[dict[str, Any]]:
        cur = self.conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, task_id, title, is_completed, position FROM subtasks WHERE task_id = %s ORDER BY position, id",
            (task_id,),
        )
        rows = cur.fetchall()
        cur.close()
        return rows

    def set_subtask_completed(self, subtask_id: int, is_completed: bool) -> None:
        cur = self.conn.cursor()
        cur.execute("UPDATE subtasks SET is_completed = %s WHERE id = %s", (int(is_completed), subtask_id))
        cur.close()
        self.conn.commit()

    def delete_subtask(self, subtask_id: int) -> None:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM subtasks WHERE id = %s", (subtask_id,))
        cur.close()
        self.conn.commit()

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
