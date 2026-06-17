"""date-fns optional package declaration."""

from __future__ import annotations

from flow44.ai.agents.optional_packages.base import OptionalPackage


class DateFnsPackage(OptionalPackage):
    name = "date-fns"
    capability = "date_formatting"
    packages = ("date-fns",)
    use_when = (
        "Use when the user asks for formatted dates, relative times, due dates, timelines, calendar labels, "
        "date sorting, date ranges, or date math."
    )
    avoid_when = (
        "Avoid when static date strings, simple timestamps, or native Intl formatting are enough and no date "
        "calculation is needed."
    )
    strong_intent_groups = (
        ("date-fns",),
        ("relative", "date"),
        ("relative", "time"),
        ("due date",),
        ("timeline", "date"),
        ("date", "format"),
    )


PACKAGE = DateFnsPackage()
