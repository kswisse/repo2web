"""
Repair Engine — abstract base class.

The application layer depends on this abstraction.
Concrete providers belong in infrastructure or are injected.
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.repair.types import RepairContext, RepairProposal


class RepairEngine(ABC):
    """Abstract repair engine.

    The AI provider (deterministic or LLM-based) implements this interface.
    The orchestrator depends only on this abstraction.
    """

    @abstractmethod
    def generate_repair(
        self,
        context: RepairContext,
        attempt: int,
    ) -> Optional[RepairProposal]:
        """Generate a repair proposal from failure evidence.

        Args:
            context: Bounded repair context with only permitted information.
            attempt: Current attempt number (0-based).

        Returns:
            RepairProposal if a repair is possible, None otherwise.
        """
        ...

    @abstractmethod
    def supported_failure_stages(self) -> set[str]:
        """Return the set of failure stages this engine can repair.

        Returns:
            Set of stage names (e.g. "build", "analysis").
        """
        ...

    @abstractmethod
    def max_attempts(self) -> int:
        """Return the maximum number of repair attempts allowed.

        Returns:
            Maximum attempts (must be >= 1).
        """
        ...
