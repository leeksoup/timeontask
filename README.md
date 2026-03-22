# Time on Task (Python + MariaDB/MySQL)

A task tracking app that enforces your workflow:

- Every task belongs to a project.
- Weekly goals are selected from project tasks.
- Each day starts by selecting two tasks.
- You cannot add more tasks to today until selected tasks are finished.
- End-of-day summary shows what is complete.
- Week review shows progress on weekly goals.

## Product semantics (Milestone 0 decisions)

These baseline decisions keep implementation and testing consistent as we add more features.

- **Planning remains parent-task based.**
  - Weekly goals target parent tasks.
  - Daily selection (and the max-two-active rule) counts parent tasks only.
- **Priority scale:**
  - `1 = High`
  - `2 = Medium`
  - `3 = Low`
- **Subtask completion policy (MVP):**
  - Parent task completion stays **manual**.
  - Completing all subtasks does **not** auto-complete the parent in MVP.
- **Repeating-task defaults** (for upcoming recurrence support):
  - `starts_on` defaults to today if omitted.
  - Monthly recurrences can include multiple dates per month.
  - Yearly recurrences can include multiple dates per year (lower-priority enhancement).

## Setup

1. Install dependencies:

```bash
pip install mysql-connector-python Flask
```

2. Create a database (example):

```sql
CREATE DATABASE timeontask;
```

3. Configure connection environment variables (defaults shown):

- `MYSQL_HOST` (default: `127.0.0.1`)
- `MYSQL_PORT` (default: `3306`)
- `MYSQL_USER` (default: `root`)
- `MYSQL_PASSWORD` (default: empty)
- `MYSQL_DATABASE` (default: `timeontask`)

## Run the web app (recommended)

```bash
python webapp.py
```

Open: http://localhost:5000

### Runtime options

- `FLASK_DEBUG=1` enables debug mode + auto-reloader (best for foreground development).
- Default is production-style single process (`FLASK_DEBUG=0`), which is safer for background runs.
- `WEBAPP_HOST` and `WEBAPP_PORT` can override bind host/port (defaults: `0.0.0.0` / `5000`).

### Tasks UI highlights

- Create one task at a time with a project selector that defaults to your last-used project.
- Sort the task list by created order or by project.
- Optionally set due date and priority when creating/editing tasks.
- Edit existing tasks from the Tasks page (title, project, and completion status).
- Bulk create numbered tasks from a base title (example: `Record item` + `12` creates `Record item 1..12`).
- Define recurring task templates (daily/weekly/monthly/yearly) with optional weekday/month-day/year-date rules.
- Manage subtasks from the task edit screen (add, mark done/open, delete) while weekly goals/today focus remain parent-task based.
- Create recurring weekly meetings from the Meetings page and see today's meetings in the Today view.
- Create follow-up tasks directly from meetings so meeting outcomes flow into the normal task/planning workflow.
- Mark weekly goals as deferred or blocked, and carry unfinished goals forward during week review.

## CLI usage

```bash
python timeontask.py add-project "Client Work"
python timeontask.py add-task 1 "Draft proposal"
python timeontask.py add-task 1 "Follow up" --due-date 2026-03-20 --priority 1
python timeontask.py set-goal 1
python timeontask.py select-today 1
python timeontask.py complete 1
python timeontask.py end-of-day
python timeontask.py week-review
```

## Tests

```bash
pytest -q
```
