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
python app.py add-project "Client Work"
python app.py add-task 1 "Draft proposal"
python app.py set-goal 1
python app.py select-today 1
python app.py complete 1
python app.py end-of-day
python app.py week-review
```

## Tests

```bash
pytest
```
