# Class Reporting and Teacher Salary System

This project is a simplified educational management system developed as the final project of a Python Bootcamp. It is designed to manage schools, academic terms, classes, and teacher-related operations through a role-based architecture.

The system includes three main roles: Teacher, Education Officer, and Finance Officer. Teachers will be able to submit class session reports, education officers will review and manage academic data, and finance officers will calculate monthly teacher payments based on approved reports.

All dates in the system use the Gregorian calendar (ISO `YYYY-MM-DD` format).

## Phase 1 Status
**Completed**

## Phase 2 Status
**Completed**

### Implemented in Phase 1

* Role-based authentication (JWT)
* Three system roles:

  * `teacher`
  * `education_officer`
  * `finance_officer`
* Teacher profile information:

  * full name
  * phone number
  * emergency contact
* Base models:

  * `School`
  * `Term`
  * `Classroom`
* Permission checks between roles
* Management command for creating users (`create_user`)
* Management command for resetting passwords (`reset_password`)
* Initial database setup with sample users (`seed_data`)
* Login/role check endpoints (`/api/auth/me/`, `/api/auth/role/`)
* Tests for models, auth, and role access boundaries

### Phase 1 optional items (done)

* Admin path for creating users: Django admin panel + staff-only API (`POST /api/auth/users/`)
* API documentation with drf-spectacular: Swagger UI at `/api/docs/`, schema at `/api/schema/`
* Soft delete on domain models (records are flagged `is_deleted` instead of being removed) — includes education, session reports, and term base rates

## Phase 2 Status
**Completed**

### Implemented in Phase 2

* School management (create / edit / list / soft delete) by the Education Officer — `/api/schools/`
* Term management with start date, end date, and regular/summer flag — `/api/terms/`
  * End date must be after start date
  * Terms can never overlap each other (validated at both API and model level)
* Class management per school and term — `/api/classes/`
  * Session duration restricted to exactly 60, 90, or 120 minutes
  * Class dates must stay inside the parent term's date range
* Teacher-class assignments with explicit date ranges — `/api/teacher-assignments/`
  * A class can have multiple teachers over its lifetime (sequential, non-overlapping ranges)
  * Overlapping assignment ranges on the same class are rejected
  * Missing end date implicitly falls back to the class end date
  * Only users with the `teacher` role can be assigned
* Teachers only see their own classes and assignments (current, past, and future) — never other teachers' classes
* Invalid input (bad date order, invalid duration, overlaps) returns a structured `error_code` / `error_message` response

### Phase 2 optional items (done)

* Filtering and search on class list: by school, term, teacher, class type, session duration, and name search (`/api/classes/?school=1&term=2&teacher=3&search=...`)
* Class detail includes a `current_teacher` summary (active assignment for today, or the nearest upcoming/most recent one) without a separate request

## Tech Stack

* Python 3
* Django + Django REST Framework
* JWT authentication (djangorestframework-simplejwt)
* PostgreSQL (SQLite is used automatically when running tests)
* drf-spectacular (OpenAPI docs)

## Create database

```sql
CREATE DATABASE School_Report;
```

## DBeaver connection
- Host: `localhost`
- Port: `5432`
- Database: `School_Report`
- Username / Password: same as `.env`

## Setup

```bash
git clone <repo-url>
cd <repo-name>

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Update `.env` with your PostgreSQL credentials, then:

```bash
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```
Open: http://127.0.0.1:8000/

API docs (Swagger): http://127.0.0.1:8000/api/docs/

Full API documentation (Persian): [docs/API.md](docs/API.md)

## Sample users

| Username | Password | Role |
|----------|----------|------|
| teacher1 | pass12345 | Teacher |
| officer1 | pass12345 | Education Officer |
| finance1 | pass12345 | Finance Officer |
| admin1   | pass12345 | Education Officer + Django admin (staff) |

## API

JWT login:

```http
POST /api/auth/login/
{"username": "teacher1", "password": "pass12345"}
```

Send the access token as `Authorization: Bearer <token>` on every request.

Main endpoints:

| Endpoint | Who | Description |
|----------|-----|-------------|
| `POST /api/auth/login/` | everyone | JWT login |
| `GET /api/auth/me/` | authenticated | Current user profile |
| `GET /api/auth/role/` | authenticated | Login/role check |
| `POST /api/auth/users/` | staff only | Create a user via API |
| `/api/schools/` | Education Officer (write), all (read) | School CRUD |
| `/api/terms/` | Education Officer (write), all (read) | Term CRUD |
| `/api/classes/` | Education Officer (write); teachers see only their own | Class CRUD + filters |
| `/api/teacher-assignments/` | Education Officer (write); teachers see only their own | Teacher-class assignments |

## Create Users CMD

```bash
python manage.py create_user \
  --username=<username> \
  --password=<password> \
  --role=teacher|education_officer|finance_officer \
  --first-name=<name> \
  --last-name=<name> \
  --phone=0912xxxxxxx \
  --emergency-phone=0912xxxxxxx \
  [--staff]
```

Reset a password:

```bash
python manage.py reset_password --username=<username> --password=<newpass>
```

## Run Tests

```bash
python manage.py test            # everything (138 tests)
python manage.py test accounts   # single app
python manage.py test education
python manage.py test reports
python manage.py test finance
python manage.py test config
python manage.py test frontend
```

Tests run against a local SQLite database automatically, so no PostgreSQL setup is needed for testing.

## Project Structure

```text
accounts/    # users, roles, auth, management commands
education/   # schools, terms, classes, teacher assignments
reports/     # session reports (Phase 3)
finance/     # base rates and salary calculation (Phase 4)
frontend/    # simple demo UI (not graded, API is the deliverable)
config/      # settings, shared mixins, error handling
manage.py
```

## Known Limitations / Shortcuts

* Login is username/password only .
* Salary records are recalculated monthly and hard-deleted when no longer applicable.


## Later Phases

* Session reporting workflow and report approval/rejection (Phase 3) — scaffolding already in `reports/`
* Payroll calculation (Phase 4) — scaffolding already in `finance/`
