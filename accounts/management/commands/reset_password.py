"""Set a user's password from the command line."""

from django.core.management.base import BaseCommand, CommandError

from accounts.models import User


class Command(BaseCommand):
    """Simple password reset for development and support."""

    help = "Reset a user's password"

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist as exc:
            raise CommandError(f"User '{options['username']}' not found.") from exc

        user.set_password(options["password"])
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Password updated for {user.username}."))
