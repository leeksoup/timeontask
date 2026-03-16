# Time on Task (Python + MariaDB/MySQL)

A task tracking app that enforces your workflow:

- Every task belongs to a project.
- Weekly goals are selected from project tasks.
- Each day starts by selecting two tasks.
- You cannot add more tasks to today until selected tasks are finished.
- End-of-day summary shows what is complete.
- Week review shows progress on weekly goals.

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

### Tasks UI highlights

- Create one task at a time with a project selector that defaults to your last-used project.
- Edit existing tasks from the Tasks page (title, project, and completion status).
- Bulk create numbered tasks from a base title (example: `Record item` + `12` creates `Record item 1..12`).

## CLI usage

```bash
python timeontask.py add-project "Client Work"
python timeontask.py add-task 1 "Draft proposal"
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
