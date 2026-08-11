# مستندات کامل API — سیستم گزارش کلاس و حقوق معلم

این سند تمام endpointها، مدل‌ها، سرویس‌ها و قوانین دسترسی پروژه **School-Report** را توضیح می‌دهد.

- **Base URL:** `http://127.0.0.1:8000`
- **احراز هویت:** JWT — هدر `Authorization: Bearer <access_token>`
- **فرمت تاریخ:** میلادی ISO (`YYYY-MM-DD`)
- **Swagger UI:** `/api/docs/`
- **OpenAPI Schema:** `/api/schema/`

---

## فهرست

1. [احراز هویت و کاربران (`accounts`)](#1-احراز-هویت-و-کاربران-accounts)
2. [آموزش — مدارس، ترم، کلاس (`education`)](#2-آموزش--مدارس-ترم-کلاس-education)
3. [گزارش جلسات (`reports`)](#3-گزارش-جلسات-reports)
4. [مالی — نرخ پایه و حقوق (`finance`)](#4-مالی--نرخ-پایه-و-حقوق-finance)
5. [Soft Delete](#5-soft-delete)
6. [ساختار خطا](#6-ساختار-خطا)
7. [نقش‌ها و دسترسی](#7-نقشها-و-دسترسی)

---

## 1. احراز هویت و کاربران (`accounts`)

### مدل `User`

| فیلد | نوع | توضیح |
|------|-----|-------|
| `username` | string | نام کاربری یکتا |
| `role` | enum | `teacher` \| `education_officer` \| `finance_officer` |
| `first_name`, `last_name` | string | نام و نام خانوادگی |
| `phone`, `emergency_phone` | string | تلفن و تماس اضطراری |
| `is_staff` | bool | دسترسی به Django Admin و API ساخت کاربر |
| `is_active` | bool | غیرفعال‌سازی حساب (جایگزین حذف فیزیکی) |

**Propertyها:**
- `is_teacher`, `is_education_officer`, `is_finance_officer` — بررسی نقش

---

### `POST /api/auth/login/`

**توضیح:** ورود با نام کاربری و رمز عبور؛ دریافت JWT.

**دسترسی:** عمومی

**بدنه درخواست:**
```json
{
  "username": "teacher1",
  "password": "pass12345"
}
```

**پاسخ موفق (200):**
```json
{
  "access": "<access_token>",
  "refresh": "<refresh_token>"
}
```

**تابع:** `CustomTokenObtainPairView` — wrapper ساده روی `TokenObtainPairView` از simplejwt.

---

### `POST /api/auth/refresh/`

**توضیح:** تمدید access token با refresh token.

**دسترسی:** عمومی

**بدنه:**
```json
{ "refresh": "<refresh_token>" }
```

---

### `GET /api/auth/me/` — `PATCH /api/auth/me/`

**توضیح:** مشاهده یا ویرایش پروفایل کاربر جاری.

**دسترسی:** احراز هویت شده

**GET — فیلدهای پاسخ:** `id`, `username`, `first_name`, `last_name`, `role`, `role_display`, `phone`, `emergency_phone`, `is_staff`

**PATCH — فیلدهای قابل ویرایش:** `first_name`, `last_name`, `phone`, `emergency_phone`

**تابع:** `MeView.get_object()` — همیشه `request.user` را برمی‌گرداند.

---

### `POST /api/auth/change-password/`

**توضیح:** تغییر رمز عبور کاربر جاری.

**بدنه:**
```json
{
  "old_password": "pass12345",
  "new_password": "newpass123"
}
```

**اعتبارسنجی:** `ChangePasswordSerializer.validate_old_password` — رمز فعلی باید درست باشد؛ رمز جدید حداقل ۸ کاراکتر.

---

### `GET /api/auth/role/`

**توضیح:** بررسی وضعیت ورود و نقش فعلی.

**پاسخ:**
```json
{
  "username": "teacher1",
  "role": "teacher",
  "role_display": "Teacher",
  "is_teacher": true,
  "is_education_officer": false,
  "is_finance_officer": false,
  "is_staff": false
}
```

---

### `GET /api/auth/teachers/`

**توضیح:** لیست معلم‌های فعال.

**دسترسی:** فقط `education_officer`

---

### `POST /api/auth/users/`

**توضیح:** ساخت کاربر جدید توسط ادمین (staff).

**دسترسی:** `is_staff=True`

**بدنه:**
```json
{
  "username": "newuser",
  "password": "pass12345",
  "role": "teacher",
  "first_name": "Ali",
  "last_name": "Ahmadi",
  "phone": "09121111111",
  "emergency_phone": "09122222222",
  "is_staff": false
}
```

---

## 2. آموزش — مدارس، ترم، کلاس (`education`)

همه مدل‌های این اپ از **Soft Delete** پشتیبانی می‌کنند.

### مدل‌ها

#### `School`
مدرسه همکار — فیلدها: `name`, `level`, `gender`, `email`, `phone`, `fax`, `address`

#### `Term`
ترم تحصیلی — `name`, `start_date`, `end_date`, `is_summer`

**اعتبارسنجی (`Term.clean`):**
- `end_date >= start_date`
- بازه تاریخ با هیچ ترم دیگری همپوشانی نداشته باشد

#### `ClassRoom`
کلاس در یک مدرسه و ترم — `session_duration` فقط `60`, `90`, `120` دقیقه

**متدها:**
- `get_active_teacher(date)` — معلم فعال در تاریخ مشخص
- `get_current_assignment(date)` — معلم فعلی، آینده، یا آخرین معلم

#### `TeacherAssignment`
انتساب معلم به کلاس — `start_date`, `end_date` (nullable → پایان کلاس)

**متدها:**
- `get_effective_end_date()` — پایان صریح یا پایان کلاس
- `is_active_on(date)` — آیا در تاریخ مشخص فعال است؟
- `clean()` — جلوگیری از همپوشانی انتساب‌ها

---

### `/api/schools/` — SchoolViewSet

| متد | مسیر | دسترسی | توضیح |
|-----|------|--------|-------|
| GET | `/api/schools/` | authenticated | لیست + فیلتر `name`, `level`, `gender` + جستجو |
| POST | `/api/schools/` | education_officer | ایجاد |
| GET | `/api/schools/{id}/` | authenticated | جزئیات |
| PUT/PATCH | `/api/schools/{id}/` | education_officer | ویرایش |
| DELETE | `/api/schools/{id}/` | education_officer | **soft delete** → 204 |

---

### `/api/terms/` — TermViewSet

همان CRUD با اعتبارسنجی عدم همپوشانی ترم‌ها.

فیلتر: `is_summer`, `name` — مرتب‌سازی: `start_date`, `name`

---

### `/api/classes/` — ClassRoomViewSet

**فیلترها:** `school`, `term`, `teacher`, `class_type`, `session_duration`, `search` (نام کلاس)

**محدودیت معلم:** معلم فقط کلاس‌هایی را می‌بیند که به آن‌ها منتسب شده (گذشته، حال، آینده).

**فیلد اضافی در پاسخ:** `current_teacher` — خلاصه معلم جاری

---

### `/api/teacher-assignments/` — TeacherAssignmentViewSet

**فیلترها:** `classroom`, `teacher`, `school`, `term`

**قوانین:**
- فقط کاربران با نقش `teacher` قابل انتساب
- بازه‌های انتساب روی یک کلاس نباید همپوشانی داشته باشند
- معلم فقط انتساب‌های خود را می‌بیند

---

## 3. گزارش جلسات (`reports`)

### مدل `SessionReport`

| فیلد | توضیح |
|------|-------|
| `classroom`, `teacher` | کلاس و معلم |
| `session_date` | تاریخ جلسه |
| `session_number` | شماره جلسه (خودکار) |
| `summary` | خلاصه جلسه |
| `present_count`, `absent_count` | حاضر / غایب |
| `status` | `pending` \| `approved` \| `rejected` |
| `officer_note` | یادداشت مسئول آموزش |
| `is_salary_eligible` | واجد شرایط حقوق (تأیید تا ۴۸ ساعت پس از تاریخ جلسه) |
| `is_deleted`, `deleted_at` | soft delete |

**متدهای استاتیک:**
- `next_session_number(classroom)` — شماره جلسه بعدی (فقط گزارش‌های حذف‌نشده)
- `teacher_owns_class_on_date(teacher, classroom, date)` — آیا معلم در آن تاریخ به کلاس منتسب است؟

**متدهای نمونه:**
- `mark_approved()` — تأیید + محاسبه `is_salary_eligible`
- `mark_rejected(note)` — رد + پاک کردن واجدیت حقوق

**محدودیت یکتا:** `(classroom, session_number)` فقط برای رکوردهای `is_deleted=False`

---

### `/api/reports/` — SessionReportViewSet

| متد | مسیر | دسترسی | توضیح |
|-----|------|--------|-------|
| GET | `/api/reports/` | authenticated | لیست (محدود به نقش) |
| POST | `/api/reports/` | teacher | ثبت گزارش جدید |
| GET | `/api/reports/{id}/` | authenticated | جزئیات |
| PUT/PATCH | `/api/reports/{id}/` | teacher | ویرایش (فقط pending/rejected؛ پس از ویرایش → pending) |
| DELETE | `/api/reports/{id}/` | teacher (pending خود) / officer | **soft delete** |
| POST | `/api/reports/{id}/approve/` | education_officer | تأیید |
| POST | `/api/reports/{id}/reject/` | education_officer | رد |

**فیلترهای لیست (مسئول آموزش):** `school`, `classroom`, `teacher`, `date_from`, `date_to`

**اعتبارسنجی ایجاد:**
- معلم باید در تاریخ جلسه به کلاس منتسب باشد
- `present_count + absent_count > 0`

**ویرایش:** گزارش‌های `approved` قابل ویرایش نیستند.

---

## 4. مالی — نرخ پایه و حقوق (`finance`)

### مدل `TermBaseRate` (Soft Delete)

نرخ پایه (`base_rate`) برای هر ترم — OneToOne با `Term`.

### مدل `SalaryRecord`

رکورد حقوق ماهانه معلم — `teacher`, `year`, `month`, `amount`, `calculated_at`

یکتا: `(teacher, year, month)`

---

### `/api/finance/base-rates/` — TermBaseRateViewSet

**دسترسی:** `finance_officer` — CRUD کامل + soft delete

---

### `/api/finance/salaries/` — SalaryViewSet (فقط خواندن)

| متد | مسیر | دسترسی |
|-----|------|--------|
| GET | `/api/finance/salaries/` | finance_officer |
| GET | `/api/finance/salaries/{id}/` | finance_officer |
| GET | `/api/finance/salaries/my/` | teacher (حقوق خود) |

**فیلتر:** `year`, `month`, `teacher`

---

### `POST /api/finance/salaries/calculate/`

**توضیح:** محاسبه حقوق ماهانه همه معلم‌ها.

**بدنه:**
```json
{ "year": 2026, "month": 1 }
```

**سرویس `calculate_teacher_salary(teacher, year, month)`:**
1. گزارش‌های تأییدشده و واجد شرایط حقوق در آن ماه
2. اگر گزارش pending/rejected باشد → حقوق `null`
3. فرمول برای هر ترم:
   - `x` = نرخ پایه ترم
   - `a` = تعداد جلسات ۹۰ دقیقه‌ای، `b` = ۶۰، `c` = ۱۲۰
   - `wage = a×x + b×(0.7x) + c×(1.3x)`
   - ترم تابستانی: `× 1.1`
4. جمع و گرد کردن به بالا (`ceil`)

**سرویس `calculate_monthly_salaries(year, month)`:**
- برای هر معلم فعال محاسبه می‌کند
- اگر حقوق `null` → رکورد قبلی حذف می‌شود
- در غیر این صورت `update_or_create`

---

## 5. Soft Delete

### پیاده‌سازی (`config/mixins.py`)

**`SoftDeleteModel`** — فیلدهای `is_deleted`, `deleted_at`

| Manager | رفتار |
|---------|-------|
| `objects` | فقط رکوردهای زنده |
| `all_objects` | همه رکوردها |

**متدها:**
- `delete()` — soft delete
- `hard_delete()` — حذف فیزیکی
- `restore()` — بازگردانی

**ViewSet mixin:** `SoftDeleteModelViewSetMixin` — `DELETE` → soft delete → 204

### مدل‌های دارای Soft Delete

| مدل | اپ |
|-----|-----|
| School, Term, ClassRoom, TeacherAssignment | education |
| SessionReport | reports |
| TermBaseRate | finance |

### مدل‌های بدون Soft Delete

| مدل | جایگزین |
|-----|---------|
| User | `is_active=False` |
| SalaryRecord | حذف هنگام محاسبه مجدد |

---

## 6. ساختار خطا

Handler: `config.exceptions.custom_exception_handler`

```json
{
  "error_code": "validation_error",
  "error_message": "پیام خطا یا آبجکت فیلدها"
}
```

---

## 7. نقش‌ها و دسترسی

| نقش | دسترسی کلی |
|-----|------------|
| `teacher` | پروفایل، گزارش جلسات خود، کلاس/انتساب خود، حقوق خود |
| `education_officer` | CRUD آموزشی، تأیید/رد گزارش، لیست معلم‌ها |
| `finance_officer` | نرخ پایه، محاسبه حقوق، مشاهده حقوق همه |
| `is_staff` | Django Admin + `POST /api/auth/users/` |

---

## Management Commands

| دستور | توضیح |
|-------|-------|
| `create_user` | ساخت کاربر با نقش |
| `reset_password` | بازنشانی رمز |
| `seed_data` | داده نمونه (idempotent) |

---

## توابع کمکی (`config/datetime_utils.py`)

| تابع | توضیح |
|------|-------|
| `calendar_month_range(year, month)` | اول و آخر ماه میلادی |
| `session_salary_deadline(session_date)` | مهلت ۴۸ ساعته تأیید |
| `is_salary_eligible(session_date, approved_at)` | آیا تأیید به‌موقع بوده؟ |

---

*آخرین به‌روزرسانی: آگوست ۲۰۲۶*
