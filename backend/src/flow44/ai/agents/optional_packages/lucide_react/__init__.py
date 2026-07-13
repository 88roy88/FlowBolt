from flow44.ai.agents.optional_packages.base import OptionalPackage


class LucideReactPackage(OptionalPackage):
    name = "lucide-react"
    capability = "icons"
    packages = ("lucide-react",)
    use_when = (
        "The UI needs crisp vector icons — nav items, buttons, status indicators, empty states, "
        "or any polished interface where inline SVGs would otherwise be hand-written."
    )
    avoid_when = "A single emoji or a plain text label is enough, or the design uses no icons."


PACKAGE = LucideReactPackage()
