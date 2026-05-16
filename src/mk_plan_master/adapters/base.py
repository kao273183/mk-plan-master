"""Initiative source abstraction. One concrete subclass per adapter
(markdown_local in Phase 1; linear / jira / notion in Phase 2+)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InitiativeSummary:
    """Lightweight listing entry — id + title + url + status + labels."""

    id: str
    source: str
    title: str
    url: str = ""
    status: str = ""
    labels: list[str] = field(default_factory=list)


@dataclass
class Initiative:
    """Full initiative record returned by fetch().

    raw_metadata is the catch-all for scoring inputs (reach / impact /
    confidence / effort) and any source-specific fields. Phase 1 just
    surfaces them; Phase 2's scoring tool consumes them.
    """

    id: str
    source: str
    title: str
    body: str
    url: str = ""
    status: str = ""
    labels: list[str] = field(default_factory=list)
    raw_metadata: dict[str, Any] = field(default_factory=dict)


class InitiativeSource(ABC):
    """Implementations must be inexpensive to instantiate (no network on init).
    Network calls happen inside list_initiatives / fetch."""

    name: str = "base"

    @abstractmethod
    def list_initiatives(
        self,
        status: str | None = None,
        label: str | None = None,
        limit: int = 50,
    ) -> list[InitiativeSummary]:
        """Filters: status, label, limit. Adapters may accept extra source-
        specific kwargs in subclasses."""

    @abstractmethod
    def fetch(self, initiative_id: str) -> Initiative:
        """Return full initiative content. Raises ValueError if the id is
        unknown."""
