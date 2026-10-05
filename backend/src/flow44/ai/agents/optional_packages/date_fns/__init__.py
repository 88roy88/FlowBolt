from pathlib import Path

from flow44.ai.agents.optional_packages.base import OptionalPackage

PACKAGE = OptionalPackage(
    name="date-fns",
    capability="date_math",
    packages=("date-fns",),
    templates_dir=Path(__file__).parent / "templates",
    use_when=(
        "Date logic the native Date/Intl APIs lack and would otherwise be hand-rolled: "
        "interval math (add/subtract/difference), week/month boundaries, calendar grids, "
        "relative times ('3 days ago'), or parsing custom date formats."
    ),
    avoid_when=(
        "Formatting or displaying dates and times — Intl.DateTimeFormat / toLocaleDateString already cover it."
    ),
)
