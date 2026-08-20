# مستندات کامل API — سیستم گزارش کلاس و حقوق معلم

این سند تمام endpointها، مدل‌ها، سرویس‌ها و قوانین دسترسی پروژه **School-Report** را توضیح می‌دهد.

- **Base URL:** `http://127.0.0.1:8000`
- **احراز هویت:** JWT — هدر `Authorization: Bearer <access_token>`
- **فرمت تاریخ:** میلادی ISO (`YYYY-MM-DD`)
- **Swagger UI:** `/api/docs/`
- **OpenAPI Schema:** `/api/schema/`
- **مستندات کد:** [CODE.md](CODE.md)

---

## فهرست

1. [احراز هویت و کاربران](#1-احراز-هویت-و-کاربران)
2. [آموزش — مدارس، ترم، کلاس، جلسات](#2-آموزش)
3. [گزارش جلسات](#3-گزارش-جلسات)
4. [مالی — نرخ پایه و حقوق](#4-مالی)
5. [ساعت پروژه (تست)](#5-ساعت-پروژه)
6. [Soft Delete](#6-soft-delete)
7. [ساختار خطا](#7-ساختار-خطا)
8. [نقش‌ها و دسترسی](#8-نقشها-و-دسترسی)
9. [Management Commands](#9-management-commands)

---

## 1. احراز هویت و کاربران

### مدل `User`

| فیلد | نوع | توضیح |
|------|-----|-------|
| `username` | string | یکتا |
| `role` | enum | `teacher` \| `education_officer` \| `finance_officer` |
| `first_name`, `last_name` | string | نام |
| `phone`, `emergency_phone` | string | تلفن |
| `is_staff` | bool | Django Admin + API ساخت کاربر |
| `is_active` | bool | غیرفعال‌سازی حساب |

**Propertyها:** `is_teacher`, `is_education_officer`, `is_finance_officer`

---

### Endpoints

| متد | مسیر | دسترسی | توضیح |
|-----|------|--------|-------|
| POST | `/api/auth/login/` | عمومی | دریافت access + refresh token |
| POST | `/api/auth/refresh/` | عمومی | تمدید access token |
| GET/PATCH | `/api/auth/me/` | authenticated | پروفایل |
| POST | `/api/auth/change-password/` | authenticated | تغییر رمز |
| GET | `/api/auth/role/` | authenticated | نقش فعلی |
| GET | `/api/auth/teachers/` | education_officer | لیست معلم‌ها |
| POST | `/api/auth/users/` | staff | ساخت کاربر |

**مثال login:**
```json
POST /api/auth/login/
{"username": "teacher1", "password": "pass12345"}

→ {"access": "...", "refresh": "..."}
```

---

## 2. آموزش

### مدل‌ها

#### `School`
`name`, `level`, `gender`, `email`, `phone`, `fax`, `address`

- **اعتبارسنجی:** شماره `phone` بین مدارس فعال **یکتا** است (ایمیل می‌تواند تکراری باشد).

#### `Term`
`name`, `start_date`, `end_date`, `is_summer`

- شروع = **روز اول ماه**
- پایان = **آخرین روز ماه**
- بازه با ترم‌های دیگر **همپوشانی ندارد**

#### `ClassRoom`
کلاس در مدرسه + ترم — `session_duration`: فقط `60`, `90`, `120`

- فیلد `weekdays` هنگام ایجاد/ویرایش (لیست 0–6، دوشنبه=0)
- جلسات (`ClassSession`) خودکار از `start_date` + `end_date` + روزهای هفته ساخته می‌شوند

**متدهای مهم:**
- `get_weekdays()` — روزهای هفتگی فعال
- `regenerate_sessions()` — بازسازی جلسات (جلسات دارای گزارش حفظ می‌شوند)
- `get_active_teacher(date)` — انتساب فعال در تاریخ
- `get_current_assignment(date)` — برای نمایش UI

#### `ClassRoomWeekday`
روز هفته برگزاری کلاس — `(classroom, weekday)` یکتا

#### `ClassSession`
جلسه زمان‌بندی‌شده — `session_number`, `session_date`

#### `TeacherAssignment`
انتساب معلم — `start_date`, `end_date` (nullable → پایان کلاس)

- همپوشانی انتساب روی یک کلاس ممنوع
- فقط کاربران با نقش `teacher`

**متدها:** `get_effective_end_date()`, `is_active_on(date)`, `clean()`

---

### Endpoints

| متد | مسیر | دسترسی | توضیح |
|-----|------|--------|-------|
| CRUD | `/api/schools/` | officer write | مدارس + soft delete |
| CRUD | `/api/terms/` | officer write | ترم‌ها |
| CRUD | `/api/classes/` | officer write | کلاس‌ها |
| GET | `/api/class-sessions/` | authenticated | جلسات (read-only) |
| CRUD | `/api/teacher-assignments/` | officer write | انتساب معلم |

**فیلتر کلاس:** `school`, `term`, `teacher`, `class_type`, `session_duration`, `search`

**فیلتر ترم:** `name`, `is_summer`, `start_date_from/to`, `end_date_from/to`, search

**محدودیت معلم:** معلم فقط کلاس‌ها و انتساب‌های **خودش** را می‌بیند.

**فیلد اضافی کلاس:** `current_teacher` — خلاصه معلم جاری

**مثال ایجاد کلاس:**
```json
POST /api/classes/
{
  "school": 1,
  "term": 1,
  "name": "Robotic",
  "session_duration": 90,
  "start_date": "2026-09-01",
  "end_date": "2027-03-31",
  "weekdays": [6, 2]
}
```

---

## 3. گزارش جلسات

### مدل `SessionReport`

| فیلد | توضیح |
|------|-------|
| `classroom`, `class_session`, `teacher` | کلاس، جلسه، معلم |
| `session_date`, `session_number` | از `class_session` کپی می‌شود |
| `summary`, `present_count`, `absent_count` | محتوای گزارش |
| `status` | `pending` \| `approved` \| `rejected` |
| `officer_note` | یادداشت مسئول (تأیید/رد) |
| `is_salary_eligible` | واجد حقوق (تأیید ظرف ۴۸ ساعت از نیمه‌شب تاریخ جلسه) |
| `approved_at` | زمان تأیید |

**متدهای استاتیک:**
- `next_session_number(classroom)`
- `teacher_owns_class_on_date(teacher, classroom, date)`
- `validate_class_session_for_teacher(teacher, class_session)`

**متدهای نمونه:**
- `mark_approved()` — تأیید + محاسبه eligibility
- `mark_rejected(note)` — رد + پاک کردن eligibility

---

### Endpoints

| متد | مسیر | دسترسی | توضیح |
|-----|------|--------|-------|
| GET | `/api/reports/` | authenticated | لیست (محدود به نقش) |
| POST | `/api/reports/` | teacher | ثبت گزارش |
| GET/PATCH | `/api/reports/{id}/` | teacher/officer | جزئیات / ویرایش |
| DELETE | `/api/reports/{id}/` | teacher (pending) / officer | soft delete |
| GET | `/api/reports/my-sessions/` | teacher | لیست جلسات + وضعیت |
| POST | `/api/reports/{id}/approve/` | officer | تأیید |
| POST | `/api/reports/{id}/reject/` | officer | رد (دلیل الزامی) |

**فیلتر (مسئول آموزش):** `school`, `term`, `teacher`, `classroom`, `date_from`, `date_to`

**ایجاد گزارش:**
```json
POST /api/reports/
{
  "classroom": 1,
  "class_session": 5,
  "summary": "Session went well",
  "present_count": 12,
  "absent_count": 2
}
```

**قوانین:**
- فقط بعد از **تاریخ جلسه** می‌توان گزارش نوشت
- `present_count + absent_count > 0`
- گزارش `approved` قابل ویرایش نیست
- ویرایش → بازگشت به `pending` و پاک شدن یادداشت officer

**رد گزارش:**
```json
POST /api/reports/{id}/reject/
{"note": "Attendance numbers look wrong"}
```

---

### `GET /api/reports/my-sessions/`

لیست همه جلسات منتسب به معلم با وضعیت:

| `session_status` | معنی |
|------------------|------|
| `upcoming` | تاریخ جلسه نرسیده |
| `ready` | آماده ثبت گزارش |
| `pending` | گزارش ارسال شده، در انتظار تأیید |
| `rejected` | رد شده — قابل ویرایش |
| `approved` | تأیید شده |

فیلدهای مهم: `can_submit`, `can_edit`, `is_salary_eligible`, `officer_note`

---

## 4. مالی

### مدل `TermBaseRate` (soft delete)
نرخ پایه برای جلسات ۹۰ دقیقه‌ای — OneToOne با `Term`

### مدل `SalaryRecord`
| فیلد | توضیح |
|------|-------|
| `teacher`, `amount` | معلم و مبلغ |
| `calculation_date` | تاریخ محاسبه (حالت ۳۰ روزه) |
| `period_start`, `period_end` | بازه حقوق |
| `year`, `month` | برچسب نمایشی / حالت ماه تقویمی |
| `calculated_at` | زمان ثبت |

---

### Endpoints

| متد | مسیر | دسترسی |
|-----|------|--------|
| CRUD | `/api/finance/base-rates/` | finance_officer |
| GET | `/api/finance/salaries/` | finance_officer |
| GET | `/api/finance/salaries/my/` | teacher |
| POST | `/api/finance/salaries/calculate/` | finance_officer |

---

### `POST /api/finance/salaries/calculate/`

**حالت ۱ — با تاریخ محاسبه (پیشنهادی):**
```json
{"calculation_date": "2026-09-15"}
```

**بازه حقوق:** ۳۰ روز قبل از تاریخ محاسبه، تا **روز قبل** از آن تاریخ.

مثال: `2026-09-15` → بازه `2026-08-16` تا `2026-09-14`

**حالت ۲ — ماه تقویمی کامل:**
```json
{"year": 2026, "month": 1}
```

**پاسخ موفق:**
```json
{
  "detail": "Calculation date 2026-09-15: payroll period 2026-08-16 to 2026-09-14. 1 teacher(s) paid.",
  "period_start": "2026-08-16",
  "period_end": "2026-09-14",
  "calculation_date": "2026-09-15",
  "payroll_year": 2026,
  "payroll_month": 9,
  "records": [...],
  "skipped": [
    {
      "teacher_id": 2,
      "teacher_name": "Other Teacher",
      "reason_code": "incomplete_reports",
      "reason": "Not all sessions in this period are approved.",
      "session_count": 4,
      "approved_count": 2,
      "eligible_count": 2
    }
  ]
}
```

---

### قوانین محاسبه حقوق

1. فقط جلسات **داخل بازه** (یا ماه) که معلم به آن منتسب است
2. **همه** جلسات بازه باید گزارش **approved** داشته باشند
3. در فرمول حقوق فقط جلسات با `is_salary_eligible=True` شمرده می‌شوند
4. برای هر ترم:
   - `x` = نرخ پایه
   - `wage = a×x + b×(0.7x) + c×(1.3x)` — a/b/c = تعداد جلسات 90/60/120 دقیقه
   - ترم تابستانی: `× 1.1`
5. جمع نهایی: `ceil`
6. اگر معلم واجد شرایط نباشد → در `skipped` با دلیل

**کدهای `reason_code`:**
| کد | معنی |
|----|------|
| `no_sessions` | جلسه‌ای در بازه نیست |
| `incomplete_reports` | همه جلسات تأیید نشده |
| `no_eligible_sessions` | همه تأیید شده ولی هیچ‌کدام 48h eligible نیست |
| `missing_base_rate` | نرخ پایه ترم تعریف نشده |
| `zero_amount` | مبلغ صفر |

---

## 5. ساعت پروژه

**مسیر:** `/api/dev/clock/` — فقط education_officer، فقط وقتی `PROJECT_CLOCK_ENABLED=True` (پیش‌فرض: DEBUG)

| متد | توضیح |
|-----|-------|
| GET | وضعیت ساعت (real یا override) |
| POST | `{"datetime": "2026-09-20T10:00:00"}` — تنظیم زمان مجازی |
| DELETE | بازگشت به زمان واقعی |

برای تست قانون ۴۸ ساعته و «جلسه آماده گزارش» از این endpoint استفاده کنید.

---

## 6. Soft Delete

**Mixin:** `SoftDeleteModel` — `is_deleted`, `deleted_at`

| Manager | رفتار |
|---------|-------|
| `objects` | فقط زنده |
| `all_objects` | همه |

**متدها:** `delete()` (soft), `hard_delete()`, `restore()`

**مدل‌های soft delete:** School, Term, ClassRoom, TeacherAssignment, ClassRoomWeekday, ClassSession, SessionReport, TermBaseRate

**بدون soft delete:** User (`is_active`), SalaryRecord (حذف هنگام عدم واجدیت)

---

## 7. ساختار خطا

```json
{
  "error_code": "validation_error",
  "error_message": "پیام یا آبجکت فیلدها"
}
```

Handler: `config.exceptions.custom_exception_handler`

---

## 8. نقش‌ها و دسترسی

| نقش | دسترسی |
|-----|--------|
| `teacher` | پروفایل، my-sessions، گزارش خود، کلاس/انتساب خود، حقوق خود |
| `education_officer` | CRUD آموزشی، تأیید/رد گزارش، فیلتر گزارش‌ها، ساعت تست |
| `finance_officer` | نرخ پایه، محاسبه حقوق، مشاهده حقوق |
| `is_staff` | Django Admin + `POST /api/auth/users/` |

---

## 9. Management Commands

```bash
python manage.py create_user --username=X --password=Y --role=teacher
python manage.py reset_password --username=X --password=NEW
python manage.py seed_data
```

---

## توابع کمکی تاریخ

| تابع | توضیح |
|------|-------|
| `calendar_month_range(year, month)` | اول و آخر ماه |
| `payroll_period_for_calculation_date(date)` | بازه ۳۰ روزه |
| `session_salary_deadline(session_date)` | مهلت ۴۸ ساعته |
| `is_salary_eligible(session_date, approved_at)` | eligible بودن تأیید |
| `project_now()` / `project_localdate()` | زمان پروژه (با override) |

---

*آخرین به‌روزرسانی: آگوست ۲۰۲۶ — ۱۵۸ تست*
