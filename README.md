# Time on Task (Python CLI with MariaDB/MySQL)

A task tracking app in Python that enforces your workflow:

- Every task belongs to a project.
- Weekly goals are selected from project tasks.
- Each day starts by selecting two tasks.
- You cannot add more tasks to today until selected tasks are finished.
- End-of-day summary shows what is complete.
- Week review shows progress on weekly goals.

## Setup

1. Install dependency:

```bash
pip install mysql-connector-python
```

2. Create a database (example):

```sql
CREATE DATABASE timeontask;
```

3. Configure connection with environment variables (defaults shown):

- `MYSQL_HOST` (default: `127.0.0.1`)
- `MYSQL_PORT` (default: `3306`)
- `MYSQL_USER` (default: `root`)
- `MYSQL_PASSWORD` (default: empty)
- `MYSQL_DATABASE` (default: `timeontask`)

## Usage

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
pytest
```
