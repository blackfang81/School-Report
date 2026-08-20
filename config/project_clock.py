"""Project-wide virtual clock for manual timeline testing."""

from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

CACHE_KEY = "project_clock_override"


def is_clock_override_enabled() -> bool:
    return getattr(settings, "PROJECT_CLOCK_ENABLED", settings.DEBUG)


def get_override() -> datetime | None:
    if not is_clock_override_enabled():
        return None
    value = cache.get(CACHE_KEY)
    if value is None:
        return None
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def set_override(value: datetime | None) -> None:
    if not is_clock_override_enabled():
        raise RuntimeError("Project clock override is disabled.")
    if value is None:
        cache.delete(CACHE_KEY)
        return
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    cache.set(CACHE_KEY, value, timeout=None)


def parse_override_value(raw: str) -> datetime:
    parsed = parse_datetime(raw)
    if parsed is None:
        raise ValueError("Invalid datetime. Use ISO format, e.g. 2026-01-20T14:30:00.")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def project_now() -> datetime:
    override = get_override()
    if override is not None:
        return override
    return timezone.now()


def project_localdate():
    return timezone.localdate(project_now())
