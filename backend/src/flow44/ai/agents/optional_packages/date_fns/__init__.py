from flow44.ai.agents.optional_packages.base import OptionalPackage


class DateFnsPackage(OptionalPackage):
    name = "date-fns"
    capability = "date_formatting"
    packages = ("date-fns",)
    use_when = (
        "Formatting dates/times for display, relative times ('3 days ago'), due dates, "
        "calendars, timelines, or date math (add/subtract/compare)."
    )
    avoid_when = (
        "Only showing raw ISO strings, or a single simple date where "
        "Intl.DateTimeFormat / toLocaleDateString already suffices."
    )


PACKAGE = DateFnsPackage()
