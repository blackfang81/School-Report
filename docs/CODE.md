# مستندات کد — School-Report

راهنمای داخلی پروژه: هر ماژول، کلاس و تابع چه کاری انجام می‌دهد.

برای endpointها → [API.md](API.md)  
برای راه‌اندازی → [README.md](../README.md)

---

## فهرست اپ‌ها

```
config/       تنظیمات مشترک، soft delete، تاریخ، ساعت تست
accounts/     کاربر و احراز هویت
education/    مدارس، ترم، کلاس، جلسات
reports/      گزارش جلسات
finance/      حقوق
frontend/     UI دمو
```

---

## config

### `config/mixins.py`

#### `SoftDeleteQuerySet`
| متد | کار |
|-----|-----|
| `delete()` | soft delete روی queryset |
| `hard_delete()` | حذف فیزیکی |
| `alive()` | فیلتر `is_deleted=False` |
| `dead()` | فیلتر `is_deleted=True` |

#### `SoftDeleteManager`
Manager پیش‌فرض — queryset فقط رکوردهای زنده.

#### `AllObjectsManager`
شامل رکوردهای حذف‌شده.

#### `SoftDeleteModel` (abstract)
| متد | کار |
|-----|-----|
| `delete()` | `is_deleted=True`, `deleted_at=now` |
| `hard_delete()` | حذف از DB |
| `restore()` | بازگردانی |

---

### `config/viewsets.py`

#### `SoftDeleteModelViewSetMixin`
| متد | کار |
|-----|-----|
| `perform_destroy(instance)` | `instance.delete()` (soft) |
| `destroy()` | soft delete + HTTP 204 |

---

### `config/exceptions.py`

#### `custom_exception_handler(exc, context)`
خطاهای DRF را به `{error_code, error_message}` تبدیل می‌کند.

#### `ValidationErrorWithCode`
ValidationError با `default_code` سفارشی.

---

### `config/datetime_utils.py`

| تابع | کار |
|------|-----|
| `calendar_month_range(year, month)` | `(اول ماه, آخر ماه)` |
| `is_first_day_of_month(date)` | روز اول ماه؟ |
| `is_last_day_of_month(date)` | آخرین روز ماه؟ |
| `last_day_of_month(year, month)` | تاریخ آخر ماه |
| `payroll_period_for_calculation_date(date)` | بازه ۳۰ روزه: `(date-30d, date-1d)` |
| `payroll_month_for_calculation_date(date)` | فقط برای API ماه تقویمی — سال/ماه شروع بازه |
| `session_salary_deadline(session_date)` | نیمه‌شب جلسه + ۴۸ ساعت |
| `is_salary_eligible(session_date, approved_at)` | `approved_at <= deadline` |

---

### `config/project_clock.py`

ساعت مجازی برای تست — مقدار در cache ذخیره می‌شود.

| تابع | کار |
|------|-----|
| `is_clock_override_enabled()` | `PROJECT_CLOCK_ENABLED` یا DEBUG |
| `get_override()` | datetime override یا None |
| `set_override(value)` | تنظیم/پاک کردن override |
| `parse_override_value(str)` | parse ISO datetime |
| `project_now()` | override یا `timezone.now()` |
| `project_localdate()` | تاریخ محلی پروژه |

#### `ProjectClockView` (`config/views.py`)
- GET: `{enabled, is_overridden, current_datetime, real_datetime}`
- POST: `{datetime}` — تنظیم
- DELETE: بازگشت به real time

---

## accounts

### `Role` (TextChoices)
`teacher`, `education_officer`, `finance_officer`

### `User` (AbstractUser)
| Property | کار |
|----------|-----|
| `is_teacher` | `role == teacher` |
| `is_education_officer` | ... |
| `is_finance_officer` | ... |

### `accounts/permissions.py`
| کلاس | شرط |
|------|-----|
| `IsTeacher` | `user.is_teacher` |
| `IsEducationOfficer` | ... |
| `IsFinanceOfficer` | ... |
| `IsStaffUser` | `user.is_staff` |

### Views
| View | کار |
|------|-----|
| `CustomTokenObtainPairView` | JWT login |
| `MeView` | GET/PATCH پروفایل |
| `ChangePasswordView` | تغییر رمز |
| `RoleCheckView` | نقش فعلی |
| `TeacherListView` | لیست معلم‌های فعال |
| `AdminCreateUserView` | ساخت کاربر (staff) |

### Management commands
| Command | کار |
|---------|-----|
| `create_user` | ساخت کاربر با نقش |
| `reset_password` | بازنشانی رمز |
| `seed_data` | داده نمونه (idempotent) |

---

## education

### Enums
- `SessionDuration`: 60, 90, 120
- `Weekday`: 0=Monday … 6=Sunday (استاندارد Python)

### `School`
| متد | کار |
|-----|-----|
| `clean()` | یکتایی `phone` بین مدارس فعال |

### `Term`
| متد | کار |
|-----|-----|
| `save()` | همیشه `full_clean()` |
| `clean()` | ترتیب تاریخ، اول/آخر ماه، عدم همپوشانی |

### `ClassRoom`
| متد | کار |
|-----|-----|
| `clean()` | تاریخ داخل بازه ترم |
| `get_weekdays()` | لیست weekdayهای فعال |
| `regenerate_sessions()` | بازسازی `ClassSession` از weekday pattern |
| `get_active_teacher(date)` | انتساب فعال |
| `get_current_assignment(date)` | برای UI — فعال / آینده / آخرین |

**منطق `regenerate_sessions`:**
1. `build_session_plan` → لیست `(number, date)`
2. جلسات بدون گزارش و خارج از plan → soft delete
3. جلسات دارای گزارش → تاریخ تغییر نمی‌کند
4. بقیه → create/update

### `TeacherAssignment`
| متد | کار |
|-----|-----|
| `get_effective_end_date()` | `end_date` یا پایان کلاس |
| `is_active_on(date)` | آیا date داخل بازه است |
| `clean()` | عدم همپوشانی، داخل بازه کلاس |

### `ClassRoomWeekday`
یک رکورد به ازای هر روز هفته کلاس.

### `ClassSession`
| Property | کار |
|----------|-----|
| `has_report` | گزارش فعال دارد؟ |

---

### `education/session_utils.py`

| تابع | کار |
|------|-----|
| `iter_scheduled_session_dates(start, end, weekdays)` | generator تاریخ جلسات |
| `build_session_plan(start, end, weekdays)` | `[(1, date1), (2, date2), ...]` |

---

### `education/session_helpers.py`

| تابع | کار |
|------|-----|
| `ensure_classroom_sessions(classroom)` | اگر جلسه‌ای نیست → `regenerate_sessions()` |

---

### `education/filters.py`
- `TermFilter` — فیلتر/name/search روی ترم
- `ClassRoomFilter` — school, term, teacher, ...
- `TeacherAssignmentFilter`

---

### ViewSets
| ViewSet | کار |
|---------|-----|
| `SchoolViewSet` | CRUD مدارس |
| `TermViewSet` | CRUD ترم |
| `ClassRoomViewSet` | CRUD کلاس + weekdays + regenerate |
| `ClassSessionViewSet` | read-only جلسات |
| `TeacherAssignmentViewSet` | CRUD انتساب |

---

### `education/test_helpers.py` (فقط تست)
| تابع | کار |
|------|-----|
| `create_classroom_with_schedule(...)` | کلاس + weekdays + regenerate_sessions |
| `create_classroom_with_session_dates(...)` | جلسات با تاریخ‌های مشخص (deterministic) |
| `january_2026_dates(count)` | تاریخ‌های پیاپی ژانویه ۲۰۲۶ |

---

## reports

### `ReportStatus`
`pending`, `approved`, `rejected`

### `SessionReport`

**متدهای استاتیک:**
| متد | کار |
|-----|-----|
| `next_session_number(classroom)` | شماره بعدی (بدون soft-deleted) |
| `teacher_owns_class_on_date(...)` | انتساب معلم در تاریخ |
| `validate_class_session_for_teacher(...)` | جلسه معتبر برای ثبت؟ |

**متدهای نمونه:**
| متد | کار |
|-----|-----|
| `mark_approved()` | approved + `is_salary_eligible` از `project_now()` |
| `mark_rejected(note)` | rejected + پاک eligibility |

---

### `reports/services.py`

#### `get_teacher_session_roster(teacher)`
لیست همه جلسات منتسب به معلم.

**برای هر جلسه محاسبه می‌کند:**
- `session_status`: upcoming / ready / pending / rejected / approved
- `can_submit`, `can_edit`
- `report_id`, `report_status`, `is_salary_eligible`, `officer_note`

**منطق:**
- `session_date > today` → upcoming
- بدون گزارش → ready
- pending/rejected/approved → مطابق status

---

### `SessionReportViewSet`

| Action | کار |
|--------|-----|
| `create` | گزارش pending از class_session |
| `update` | ویرایش → reset به pending |
| `destroy` | teacher: فقط pending خودش؛ officer: همه |
| `my_sessions` | roster معلم |
| `approve` | officer + note اختیاری |
| `reject` | officer + note الزامی |

**`get_queryset`:**
- teacher → فقط گزارش خود
- officer → فیلتر school/term/teacher/date
- finance → هیچ

---

### `reports/test_helpers.py` (فقط تست)
| تابع | کار |
|------|-----|
| `create_report_for_session(...)` | ساخت گزارش برای جلسه |
| `approve_all_class_sessions(...)` | approved + eligible برای همه جلسات کلاس |

---

## finance

### `TermBaseRate`
OneToOne با Term — soft delete.

### `SalaryRecord`
- حالت A: `calculation_date` set → unique `(teacher, calculation_date)`
- حالت B: `calculation_date` null → unique `(teacher, year, month)`

---

### `finance/services.py`

#### `get_teacher_sessions_in_period(teacher, start, end)`
جلسات زمان‌بندی‌شده در بازه که معلم به آن‌ها منتسب است.

#### `get_teacher_sessions_in_month(teacher, year, month)`
wrapper روی `calendar_month_range`.

#### `month_sessions_fully_approved(teacher, sessions)`
همه جلسات approved دارند؟

#### `_period_report_stats(teacher, sessions)`
`{reports dict, approved_count, eligible_count}`

#### `explain_teacher_salary_for_period(teacher, start, end)`
```python
{
  "amount": Decimal | None,
  "reason_code": str | None,
  "reason": str | None,
  "session_count": int,
  "approved_count": int,
  "eligible_count": int,
}
```

**ترتیب بررسی:**
1. بدون جلسه → `no_sessions`
2. not all approved → `incomplete_reports`
3. no eligible → `no_eligible_sessions`
4. missing base rate → `missing_base_rate`
5. total <= 0 → `zero_amount`
6. else → amount

#### `explain_teacher_salary(teacher, year, month)`
wrapper ماه تقویمی.

#### `calculate_teacher_salary(teacher, year, month)`
فقط `amount` یا `None`.

#### `calculate_salaries_for_period(start, end, *, calculation_date=None, record_year=None, record_month=None)`
برای همه معلم‌های فعال:
- محاسبه → `update_or_create` رکورد
- عدم واجدیت → delete رکورد + append به `skipped`

#### `calculate_monthly_salaries(year, month)`
wrapper — بازه = کل ماه تقویمی.

**ثابت `SKIP_REASONS`:** پیام‌های human-readable برای UI.

---

### Views (`finance/views.py`)
| کلاس | کار |
|------|-----|
| `TermBaseRateViewSet` | CRUD نرخ — finance_officer |
| `SalaryViewSet` | read-only + `my/` برای معلم |
| `CalculateSalariesView` | POST محاسبه — برمی‌گرداند records + skipped |

---

## frontend

### `frontend/views.py`
`IndexView` — TemplateView برای `index.html`

### `frontend/static/frontend/js/api.js`
- `API` object — fetch wrapper با JWT
- `formatApiError` — parse خطای API
- `salaryEligibleBadge`, `officerNoteCell` — UI helpers
- `openReportActionModal` — modal تأیید/رد (بدون prompt مرورگر)
- `renderTable`, `formValues`, ...

### `frontend/static/frontend/js/app.js`
SPA بر اساس نقش:
- **teacher:** my-reports, new-report (my-sessions), my-salaries, profile
- **education_officer:** schools, terms, classes, assignments, reports, timeline
- **finance_officer:** base-rates, calculate, salary records, profile

---

## جریان کاری End-to-End

```
1. Officer: School → Term → Class (weekdays) → Assignment
2. System: ClassSession auto-generated
3. Teacher: GET my-sessions → POST report (after session date)
4. Officer: approve/reject
5. Finance: set base rate → POST calculate (calculation_date)
6. System: sessions in 30-day window, all approved, eligible counted
```

---

## تست‌ها (158)

| فایل | تعداد | پوشش |
|------|-------|------|
| accounts/tests.py | 33 | auth, commands, permissions |
| config/tests.py | 20 | mixins, datetime, clock, errors |
| education/tests.py | 38 | validation, sessions, API |
| reports/tests.py | 37 | lifecycle, 48h, my-sessions |
| finance/tests.py | 27 | formula, period, skipped, API |
| frontend/tests.py | 3 | index page |

---

## فایل‌های بدون منطق دامنه

| فایل | وضعیت |
|------|--------|
| `frontend/models.py` | stub خالی Django |
| `frontend/admin.py` | stub خالی |
| `finance/admin.py` | stub خالی — مدل‌ها در admin ثبت نشده |

این stubها part استاندارد Django هستند و حذف نشده‌اند.

---

*آخرین به‌روزرسانی: آگوست ۲۰۲۶*
