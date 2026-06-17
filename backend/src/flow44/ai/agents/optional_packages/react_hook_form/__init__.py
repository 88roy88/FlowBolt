"""React Hook Form optional package declaration."""

from __future__ import annotations

from flow44.ai.agents.optional_packages.base import OptionalPackage


class ReactHookFormPackage(OptionalPackage):
    name = "react-hook-form"
    capability = "form_state_validation"
    packages = ("react-hook-form",)
    use_when = (
        "Use when the user asks for forms with validation, required fields, inline errors, complex form state, "
        "multi-field submission flows, or reusable form handling."
    )
    avoid_when = (
        "Avoid for one or two uncontrolled inputs, simple search boxes, or local filters where plain React state "
        "is clearer."
    )
    strong_intent_groups = (
        ("react hook form",),
        ("form", "validation"),
        ("required", "fields"),
        ("inline", "errors"),
        ("submit", "form"),
    )


PACKAGE = ReactHookFormPackage()
