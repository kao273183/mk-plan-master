"""Adapter registry. Mirrors mk-spec-master's adapters/ pattern."""

from .base import InitiativeSource

REGISTRY: dict[str, type[InitiativeSource]] = {}


def register(name: str):
    def deco(cls):
        REGISTRY[name] = cls
        return cls

    return deco


def get_source(name: str) -> InitiativeSource:
    if name not in REGISTRY:
        raise ValueError(
            f"Unknown PLAN_SOURCE={name!r}. Available: {sorted(REGISTRY)}"
        )
    return REGISTRY[name]()


# Side-effect imports register the concrete adapters into REGISTRY.
from . import markdown_local  # noqa: E402, F401
from . import linear  # noqa: E402, F401
from . import jira  # noqa: E402, F401
from . import notion  # noqa: E402, F401
