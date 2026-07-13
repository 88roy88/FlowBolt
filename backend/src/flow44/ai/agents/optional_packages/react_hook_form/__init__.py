from flow44.ai.agents.optional_packages.base import OptionalPackage


class ReactHookFormPackage(OptionalPackage):
    name = "react-hook-form"
    capability = "forms"
    packages = ("react-hook-form",)
    use_when = (
        "Building forms with multiple fields, validation, or submit handling — sign-up, "
        "settings, filters, multi-step wizards, or any form where per-field errors matter."
    )
    avoid_when = (
        "A single uncontrolled input or a trivial one-field form where local useState "
        "plus native required/pattern validation is simpler."
    )


PACKAGE = ReactHookFormPackage()
