"""Management command to create application users."""

from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, User


class Command(BaseCommand):
    """Create a user with username, password, role, and optional profile fields."""

    help = "Create a new user with a specific role"

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--role", required=True, choices=[c.value for c in Role])
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")
        parser.add_argument("--phone", default="")
        parser.add_argument("--emergency-phone", default="")
        parser.add_argument(
            "--staff",
            action="store_true",
            help="Grant Django admin (staff) access to this user.",
        )

    def handle(self, *args, **options):
        username = options["username"]
        if User.objects.filter(username=username).exists():
            raise CommandError(f"User '{username}' already exists.")

        user = User.objects.create_user(
            username=username,
            password=options["password"],
            role=options["role"],
            first_name=options["first_name"],
            last_name=options["last_name"],
            phone=options["phone"],
            emergency_phone=options["emergency_phone"],
            is_staff=options["staff"],
        )
        staff_note = " (staff/admin)" if user.is_staff else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Created user {user.username} with role {user.get_role_display()}{staff_note}."
            )
        )
