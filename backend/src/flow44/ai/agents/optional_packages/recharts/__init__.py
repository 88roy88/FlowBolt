from flow44.ai.agents.optional_packages.base import OptionalPackage


class RechartsPackage(OptionalPackage):
    name = "recharts"
    capability = "charts"
    packages = ("recharts",)
    use_when = (
        "Visualizing data as charts — dashboards/analytics showing trends over time, comparisons "
        "across categories, compositions, or distributions (line, bar, area, or pie)."
    )
    avoid_when = "A single KPI number, a plain table, or a tiny sparkline that a little CSS/SVG can do."


PACKAGE = RechartsPackage()
