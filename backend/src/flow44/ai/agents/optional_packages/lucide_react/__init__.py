"""Lucide React optional package declaration."""

from __future__ import annotations

from flow44.ai.agents.optional_packages.base import OptionalPackage


class LucideReactPackage(OptionalPackage):
    name = "lucide-react"
    capability = "iconography"
    packages = ("lucide-react",)
    use_when = (
        "Use when the user asks for icons, visual symbols, navigation icons, feature icons, status icons, "
        "or more scannable dashboard cards and actions."
    )
    avoid_when = (
        "Avoid when decorative text, emoji, CSS shapes, or existing inline SVGs are enough, or when the user "
        "asks for custom illustrations or logos."
    )
    strong_intent_groups = (
        ("icon",),
        ("icons",),
        ("lucide",),
        ("visual", "symbols"),
        ("dashboard", "icons"),
    )


PACKAGE = LucideReactPackage()
