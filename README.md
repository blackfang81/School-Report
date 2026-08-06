# Class Reporting and Teacher Salary System

## Stack
- Django + Django REST Framework + JWT
- PostgreSQL

## Setup

```bash
cd "School_Report"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create the database:

```sql
CREATE DATABASE School_Report;
```

Update `.env` with your PostgreSQL credentials, then:

```bash
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Open: http://127.0.0.1:8000/

## Sample users

| Username | Password | Role |
|----------|----------|------|
| teacher1 | pass12345 | Teacher |
| officer1 | pass12345 | Education Officer |
| finance1 | pass12345 | Finance Officer |

## API

JWT login:

```http
POST /api/auth/login/
{"username": "teacher1", "password": "pass12345"}
```

## DBeaver connection
- Host: `localhost`
- Port: `5432`
- Database: `School_Report`
- Username / Password: same as `.env`
