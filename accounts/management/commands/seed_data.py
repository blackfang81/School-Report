from django.core.management.base import BaseCommand

from accounts.models import Role, User
from education.models import ClassRoom, School, TeacherAssignment, Term
from finance.models import TermBaseRate


class Command(BaseCommand):
    help = "Create sample data for testing the system"

    def handle(self, *args, **options):
        if User.objects.filter(username="teacher1").exists():
            self.stdout.write("Sample data already exists.")
            return

        User.objects.create_user(
            username="teacher1",
            password="pass12345",
            role=Role.TEACHER,
            first_name="Ali",
            last_name="Ahmadi",
            phone="09120000001",
            emergency_phone="09120000002",
        )
        User.objects.create_user(
            username="officer1",
            password="pass12345",
            role=Role.EDUCATION_OFFICER,
            first_name="Maryam",
            last_name="Rezaei",
            phone="09120000003",
        )
        User.objects.create_user(
            username="finance1",
            password="pass12345",
            role=Role.FINANCE_OFFICER,
            first_name="Hossein",
            last_name="Karimi",
            phone="09120000004",
        )

        school = School.objects.create(name="Sample School", phone="02112345678", address="Tehran")
        term = Term.objects.create(
            name="2025-2026",
            start_date="2025-09-01",
            end_date="2026-06-30",
            is_summer=False,
        )
        classroom = ClassRoom.objects.create(
            school=school,
            term=term,
            name="Robotics Class",
            class_type="robotics",
            session_duration=90,
            start_date="2025-09-01",
            end_date="2026-06-30",
        )
        TeacherAssignment.objects.create(
            classroom=classroom,
            teacher=User.objects.get(username="teacher1"),
            start_date="2025-09-01",
        )
        TermBaseRate.objects.create(term=term, base_rate=200_000)

        self.stdout.write(self.style.SUCCESS("Sample data created."))
        self.stdout.write("teacher1 / pass12345")
        self.stdout.write("officer1 / pass12345")
        self.stdout.write("finance1 / pass12345")
