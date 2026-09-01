"""Custom type registrations for Smoldyn process-bigraph wrapper."""


def register_types(core):
    """Register any custom types needed for Smoldyn simulations.

    Currently no custom types are needed — Smoldyn molecule counts
    and positions map directly to built-in bigraph-schema types.
    """
    return core
