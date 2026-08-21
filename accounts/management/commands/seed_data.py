"""Seed the database with rich sample data for demos and manual testing."""

from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Role, User
from education.models import (
    ClassRoom,
    ClassRoomWeekday,
    ClassSession,
    School,
    TeacherAssignment,
    Term,
    Weekday,
)
from education.session_helpers import ensure_classroom_sessions
from finance.models import TermBaseRate
from reports.models import ReportStatus, SessionReport


SEED_SCHOOL_NAME = "Tehran Partner School"
SEED_MARKER = "seed_v2"


class Command(BaseCommand):
    """
    Create sample users, schools, terms, classes (with weekly sessions),
    teacher assignments, base rates, and a few demo reports.

    Safe to run multiple times — skips when seed marker school already exists.
    Users are created with get_or_create so partial runs can be completed.
    """

    help = "Create sample data for testing the system"

    def handle(self, *args, **options):
        self._ensure_users()

        if School.objects.filter(name=SEED_SCHOOL_NAME).exists():
            self.stdout.write("Sample data already exists.")
            self._print_credentials()
            return

        school = self._create_schools()
        summer_term, main_term = self._create_terms()
        teacher1 = User.objects.get(username="teacher1")
        teacher2 = User.objects.get(username="teacher2")

        summer_class = self._create_class(
            school=school,
            term=summer_term,
            name="Programming Bootcamp",
            class_type="programming",
            session_duration=90,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 8, 31),
            weekdays=[Weekday.MONDAY, Weekday.THURSDAY],
            teacher=teacher1,
        )
        robotics_class = self._create_class(
            school=school,
            term=main_term,
            name="Robotics",
            class_type="robotics",
            session_duration=90,
            start_date=date(2026, 9, 1),
            end_date=date(2027, 3, 31),
            weekdays=[Weekday.SUNDAY, Weekday.WEDNESDAY],
            teacher=teacher1,
        )
        self._create_class(
            school=school,
            term=main_term,
            name="English Conversation",
            class_type="language",
            session_duration=60,
            start_date=date(2026, 9, 1),
            end_date=date(2027, 3, 31),
            weekdays=[Weekday.TUESDAY, Weekday.FRIDAY],
            teacher=teacher2,
        )

        TermBaseRate.objects.create(term=summer_term, base_rate=450_000)
        TermBaseRate.objects.create(term=main_term, base_rate=500_000)

        self._create_summer_demo_reports(summer_class, teacher1)

        session_count = ClassSession.objects.filter(is_deleted=False).count()
        self.stdout.write(self.style.SUCCESS(f"Sample data created ({SEED_MARKER})."))
        self.stdout.write(f"  Schools: {School.objects.filter(is_deleted=False).count()}")
        self.stdout.write(f"  Terms: {Term.objects.filter(is_deleted=False).count()}")
        self.stdout.write(f"  Classes: {ClassRoom.objects.filter(is_deleted=False).count()}")
        self.stdout.write(f"  Scheduled sessions: {session_count}")
        self.stdout.write(f"  Base rates: {TermBaseRate.objects.filter(is_deleted=False).count()}")
        self.stdout.write("")
        self._print_credentials()
        self.stdout.write("")
        self.stdout.write("Demo tips:")
        self.stdout.write("  - teacher1: summer bootcamp has past sessions + sample reports")
        self.stdout.write("  - teacher1: Robotics starts Sep 2026 — use Timeline to test")
        self.stdout.write("  - finance1: set calculation_date e.g. 2026-08-20 for summer payroll")

    def _ensure_users(self):
        users = [
            dict(
                username="teacher1",
                role=Role.TEACHER,
                first_name="Ali",
                last_name="Ahmadi",
                phone="09120000001",
                emergency_phone="09120000002",
            ),
            dict(
                username="teacher2",
                role=Role.TEACHER,
                first_name="Sara",
                last_name="Mohammadi",
                phone="09120000011",
                emergency_phone="09120000012",
            ),
            dict(
                username="officer1",
                role=Role.EDUCATION_OFFICER,
                first_name="Maryam",
                last_name="Rezaei",
                phone="09120000003",
            ),
            dict(
                username="finance1",
                role=Role.FINANCE_OFFICER,
                first_name="Hossein",
                last_name="Karimi",
                phone="09120000004",
            ),
            dict(
                username="admin1",
                role=Role.EDUCATION_OFFICER,
                first_name="Admin",
                last_name="User",
                phone="09120000005",
                is_staff=True,
                is_superuser=True,
            ),
        ]
        for spec in users:
            password = "pass12345"
            username = spec.pop("username")
            is_staff = spec.pop("is_staff", False)
            is_superuser = spec.pop("is_superuser", False)
            user, created = User.objects.get_or_create(
                username=username,
                defaults={**spec, "is_staff": is_staff, "is_superuser": is_superuser},
            )
            if created:
                user.set_password(password)
                user.save()

    def _create_schools(self):
        school, _ = School.objects.get_or_create(
            name=SEED_SCHOOL_NAME,
            defaults={
                "level": "High School",
                "gender": "mixed",
                "email": "info@tehran-partner.edu",
                "phone": "02112345678",
                "address": "Tehran, Valiasr St.",
            },
        )
        School.objects.get_or_create(
            name="Isfahan Partner School",
            defaults={
                "level": "Middle School",
                "phone": "03132345678",
                "address": "Isfahan",
            },
        )
        return school

    def _create_terms(self):
        summer_term, _ = Term.objects.get_or_create(
            name="Summer 2026",
            defaults={
                "start_date": date(2026, 7, 1),
                "end_date": date(2026, 8, 31),
                "is_summer": True,
            },
        )
        main_term, _ = Term.objects.get_or_create(
            name="2026-2027",
            defaults={
                "start_date": date(2026, 9, 1),
                "end_date": date(2027, 6, 30),
                "is_summer": False,
            },
        )
        return summer_term, main_term

    def _create_class(
        self,
        *,
        school,
        term,
        name,
        class_type,
        session_duration,
        start_date,
        end_date,
        weekdays,
        teacher,
    ):
        classroom, created = ClassRoom.objects.get_or_create(
            school=school,
            term=term,
            name=name,
            defaults={
                "class_type": class_type,
                "session_duration": session_duration,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        for weekday in weekdays:
            item, was_created = ClassRoomWeekday.objects.get_or_create(
                classroom=classroom,
                weekday=weekday,
            )
            if not was_created and item.is_deleted:
                item.restore()

        classroom.regenerate_sessions()
        TeacherAssignment.objects.get_or_create(
            classroom=classroom,
            teacher=teacher,
            defaults={"start_date": start_date},
        )
        ensure_classroom_sessions(classroom)
        if created:
            self.stdout.write(
                f"  Class '{name}': {classroom.sessions.filter(is_deleted=False).count()} sessions"
            )
        return classroom

    def _aware_datetime(self, value: date, hour=10):
        naive = datetime.combine(value, time(hour, 0))
        return timezone.make_aware(naive, timezone.get_current_timezone())

    def _create_summer_demo_reports(self, classroom, teacher):
        """
        Add sample reports on the first past sessions (relative to Aug 20 2026).

        - 2 approved + salary eligible
        - 1 pending (waiting for officer)
        - 1 rejected with a reason
        """
        today = date(2026, 8, 20)
        past_sessions = list(
            classroom.sessions.filter(is_deleted=False, session_date__lt=today).order_by(
                "session_number"
            )[:4]
        )
        if len(past_sessions) < 4:
            self.stdout.write(
                self.style.WARNING(
                    f"  Only {len(past_sessions)} past sessions for demo reports (expected 4)."
                )
            )

        scenarios = [
            ("approved", "Summer session went well.", 14, 1, True),
            ("approved", "Students completed all exercises.", 12, 2, True),
            ("pending", "Good participation today.", 11, 3, False),
            ("rejected", "Needs correction on attendance.", 8, 4, False),
        ]

        for session, (status, summary, present, absent, eligible) in zip(
            past_sessions, scenarios
        ):
            if SessionReport.objects.filter(class_session=session, is_deleted=False).exists():
                continue

            if status == "rejected":
                report = SessionReport.objects.create(
                    classroom=classroom,
                    class_session=session,
                    teacher=teacher,
                    session_date=session.session_date,
                    session_number=session.session_number,
                    summary=summary,
                    present_count=present,
                    absent_count=absent,
                    status=ReportStatus.REJECTED,
                    officer_note="تعداد حاضرین با لیست کلاس مطابقت ندارد — لطفاً اصلاح کنید.",
                )
                continue

            report = SessionReport.objects.create(
                classroom=classroom,
                class_session=session,
                teacher=teacher,
                session_date=session.session_date,
                session_number=session.session_number,
                summary=summary,
                present_count=present,
                absent_count=absent,
                status=ReportStatus.PENDING,
            )

            if status == "approved":
                approved_at = self._aware_datetime(session.session_date + timedelta(days=1))
                report.status = ReportStatus.APPROVED
                report.approved_at = approved_at
                report.is_salary_eligible = eligible
                report.save(
                    update_fields=["status", "approved_at", "is_salary_eligible", "updated_at"]
                )

    def _print_credentials(self):
        self.stdout.write("Login credentials (password for all: pass12345):")
        self.stdout.write("  teacher1   — Teacher (bootcamp + robotics)")
        self.stdout.write("  teacher2   — Teacher (English class)")
        self.stdout.write("  officer1   — Education Officer")
        self.stdout.write("  finance1   — Finance Officer")
        self.stdout.write("  admin1     — Education Officer + Django admin")
