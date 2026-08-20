# Class Reporting and Teacher Salary System

A Django REST API for managing partner schools, academic terms, scheduled class sessions, teacher session reports, and salary calculation. Includes a simple demo frontend (vanilla JS) for manual testing.

**Roles:** Teacher · Education Officer · Finance Officer

All dates use the **Gregorian calendar** (`YYYY-MM-DD`).

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/API.md](docs/API.md) | Full API reference (Persian) — endpoints, request/response, business rules |
| [docs/CODE.md](docs/CODE.md) | Internal code reference — models, services, methods, helpers |
| `/api/docs/` | Swagger UI (OpenAPI, auto-generated) |

---

## Features

### Authentication & users
- JWT login (`/api/auth/login/`)
- Role-based permissions (teacher / education_officer / finance_officer)
- Profile, password change, staff user creation
- Management commands: `create_user`, `reset_password`, `seed_data`

### Education (Education Officer)
- Schools — CRUD + soft delete; **phone number unique** per active school
- Terms — CRUD + soft delete; start = 1st of month, end = last day of month, **no overlap**
- Classes — weekly schedule (`weekdays`) auto-generates `ClassSession` records
- Teacher assignments — date ranges, no overlap on same class
- Filters on terms, classes, assignments, reports

### Reports
- Teachers submit reports for **scheduled sessions** (not free-form dates)
- Education officers approve/reject (rejection reason required)
- **48-hour rule:** approval within 48h of session date → `is_salary_eligible=True`
- Report lifecycle: pending → approved/rejected; edit resets to pending
- Soft delete

### Finance
- Term base rate (one rate per term, soft delete)
- Salary calculation:
  - **By calculation date:** last **30 days** before that date (exclusive of calculation day)
  - **By year/month:** full calendar month (API alternative)
- Only eligible sessions count in payment; all sessions in period must be approved
- Formula: 90min = 1× base, 60min = 0.7×, 120min = 1.3×; summer term +10%

### Developer tools
- **Project clock** (`/api/dev/clock/`) — override “now” for testing timelines (DEBUG)
- Structured API errors: `error_code` + `error_message`
- Soft delete on domain models

---

## Tech Stack

- Python 3 · Django 6 · Django REST Framework
- JWT (`djangorestframework-simplejwt`)
- PostgreSQL (SQLite automatically for tests)
- drf-spectacular (OpenAPI)

---

## Setup

### 1. Database

```sql
CREATE DATABASE School_Report;
```

### 2. Environment

Copy/configure `.env`:

```
DB_NAME=School_Report
DB_USER=postgres
DB_PASSWORD=...
DB_HOST=localhost
DB_PORT=5432
```

### 3. Install & run

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

- App UI: http://127.0.0.1:8000/
- Swagger: http://127.0.0.1:8000/api/docs/

---

## Sample users

| Username | Password | Role |
|----------|----------|------|
| teacher1 | pass12345 | Teacher |
| officer1 | pass12345 | Education Officer |
| finance1 | pass12345 | Finance Officer |
| admin1 | pass12345 | Education Officer + Django admin |

---

## API quick reference

Send `Authorization: Bearer <access_token>` on all protected routes.

```http
POST /api/auth/login/
{"username": "teacher1", "password": "pass12345"}
```

| Endpoint | Who | Description |
|----------|-----|-------------|
| `/api/auth/*` | all | Login, profile, password, role check |
| `/api/schools/` | officer write | Schools |
| `/api/terms/` | officer write | Terms |
| `/api/classes/` | officer write | Classes + weekly sessions |
| `/api/class-sessions/` | read | Scheduled sessions |
| `/api/teacher-assignments/` | officer write | Teacher ↔ class |
| `/api/reports/` | teacher/officer | Session reports |
| `/api/reports/my-sessions/` | teacher | Session roster for reporting |
| `/api/reports/{id}/approve/` | officer | Approve report |
| `/api/reports/{id}/reject/` | officer | Reject report |
| `/api/finance/base-rates/` | finance | Term base rates |
| `/api/finance/salaries/` | finance / teacher `my/` | Salary records |
| `/api/finance/salaries/calculate/` | finance | Run payroll |
| `/api/dev/clock/` | officer (DEBUG) | Test timeline |

See [docs/API.md](docs/API.md) for full details.

---

## Tests

**158 tests** — all passing.

```bash
python manage.py test              # full suite
python manage.py test accounts     # 33
python manage.py test config       # 20
python manage.py test education    # 38
python manage.py test reports      # 37
python manage.py test finance      # 27
python manage.py test frontend     # 3
```

Tests use SQLite automatically — no PostgreSQL required.

### Coverage by area

| App | What is tested |
|-----|----------------|
| accounts | User model, JWT, permissions, management commands |
| config | Soft delete, datetime/payroll helpers, project clock, errors |
| education | Term/class/assignment validation, sessions, CRUD API |
| reports | Report lifecycle, 48h rule, approve/reject, my-sessions |
| finance | Salary formula, 30-day period, skipped reasons, API |
| frontend | Index page smoke tests |

---

## Project structure

```text
accounts/     Users, roles, auth, management commands
education/    Schools, terms, classes, sessions, assignments
reports/      Session reports, approval workflow, teacher roster
finance/      Base rates, salary calculation, salary records
frontend/     Demo SPA (index.html + app.js + api.js)
config/       Settings, mixins, datetime utils, project clock, errors
docs/         API.md, CODE.md
manage.py
```

---

## Management commands

```bash
python manage.py create_user \
  --username=teacher2 \
  --password=pass12345 \
  --role=teacher \
  --first-name=Ali \
  --last-name=Ahmadi

python manage.py reset_password --username=teacher1 --password=newpass123

python manage.py seed_data
```

---

## Known limitations

- Login is username/password only (not phone-based).
- Users are deactivated via `is_active=False` (no user soft delete).
- `frontend/` is a demo UI; the graded deliverable is the REST API.
- Salary records for the same teacher + calculation date are overwritten on recalculate.

---

## License / context

Developed as a Python Bootcamp final project.
