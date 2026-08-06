# Class Reporting and Teacher Salary System

This project is a simplified educational management system developed as the final project of a Python Bootcamp. It is designed to manage schools, academic terms, classes, and teacher-related operations through a role-based architecture.

The system includes three main roles: Teacher, Education Officer, and Finance Officer. Teachers will be able to submit class session reports, education officers will review and manage academic data, and finance officers will calculate monthly teacher payments based on approved reports.

## Phase 1 Status
**Completed**

## Implemented

* Role-based authentication
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
* Management command for creating users
* Initial database setup with sample users
* Basic tests for models and permissions

## Tech Stack

* Python 3
* Django
* Django REST Framework
* PostgreSQL

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
source venv/bin/activate

pip install -r requirements.txt
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

## Create Users CMD

```bash
python manage.py create_user 
--username=
--password= 
--role=teacher/education_officer/finance_officer 
--first-name= 
--last-name= 
--phone=0912xxxxxxx
--emergency-phone=0912xxxxxxx
```

## Run Tests

```bash
python manage.py test <app_name>
```

## Project Structure

```text
accounts/
education/
finance/
frontend/
reports/
manage.py
```

## Not Implemented Yet

* School and term management APIs
* Class assignment to teachers
* Session reporting workflow
* Report approval/rejection
* Payroll calculation

