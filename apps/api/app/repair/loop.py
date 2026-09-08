"""
Repair Loop — bounded retry model for deployment repair.

Integrates with the orchestrator to provide controlled repair attempts
after deployment failures.

Lifecycle:
    attempt 0 = original deterministic plan
    if deployment fails:
        collect bounded failure evidence
        if failure class is supported:
            generate repair proposal
            validate proposal
            if proposal valid:
                execute repaired plan in sandbox
                if successful: accept
                else: bounded next attempt
            else: reject repair
        else: fail deployment
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.repair.engine import RepairEngine
from app.repair.types import RepairContext, RepairProposal, RepairResult
from app.repair.validator import validate_repair_proposal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RepairLoopResult:
    """Result of a complete repair loop execution.

    Attributes:
        attempts: List of individual repair results.
        final_success: Whether the repair loop ultimately succeeded.
        total_attempts: Total number of repair attempts made.
        exhausted: Whether all repair attempts were used.
    """

    attempts: tuple[RepairResult, ...] = ()
    final_success: bool = False
    total_attempts: int = 0
    exhausted: bool = False


class RepairLoop:
    """Bounded repair loop.

    Coordinates the repair process:
    1. Collects failure evidence
    2. Asks the RepairEngine for proposals
    3. Validates proposals deterministically
    4. Returns results for the orchestrator to apply

    The RepairLoop does NOT execute repairs itself.
    It returns structured results that the orchestrator applies.
    """

    def __init__(self, engine: RepairEngine):
        """Initialize the repair loop.

        Args:
            engine: The repair engine to use for generating proposals.
        """
        self.engine = engine

    def attempt_repair(
        self,
        context: RepairContext,
        attempt: int,
    ) -> RepairResult:
        """Attempt a single repair.

        Args:
            context: Bounded repair context with failure evidence.
            attempt: Current attempt number (0-based).

        Returns:
            RepairResult with the outcome of this repair attempt.
        """
        # Check if this failure stage is supported
        if context.failure_stage not in self.engine.supported_failure_stages():
            logger.info(
                "repair.unsupported_stage",
                extra={"stage": context.failure_stage},
            )
            return RepairResult(
                attempt=attempt,
                proposal=None,
                accepted=False,
                applied=False,
                plan_repaired=None,
                error=f"Failure stage '{context.failure_stage}' is not supported for repair",
            )

        # Check attempt limit
        if attempt >= self.engine.max_attempts():
            logger.info("repair.max_attempts", extra={"attempt": attempt})
            return RepairResult(
                attempt=attempt,
                proposal=None,
                accepted=False,
                applied=False,
                plan_repaired=None,
                error=f"Maximum repair attempts ({self.engine.max_attempts()}) exceeded",
            )

        # Generate proposal
        try:
            proposal = self.engine.generate_repair(context, attempt)
        except Exception as e:
            logger.error(f"repair.engine_error: {e}", exc_info=True)
            return RepairResult(
                attempt=attempt,
                proposal=None,
                accepted=False,
                applied=False,
                plan_repaired=None,
                error=f"Repair engine error: {e}",
            )

        if proposal is None:
            logger.info("repair.no_proposal", extra={"attempt": attempt})
            return RepairResult(
                attempt=attempt,
                proposal=None,
                accepted=False,
                applied=False,
                plan_repaired=None,
                error="No repair proposal generated",
            )

        # Validate proposal
        validation = validate_repair_proposal(proposal)

        if not validation.valid:
            logger.warning(
                "repair.proposal_rejected",
                extra={
                    "attempt": attempt,
                    "errors": validation.errors,
                    "repair_type": proposal.repair_type.value,
                },
            )
            return RepairResult(
                attempt=attempt,
                proposal=proposal,
                accepted=False,
                applied=False,
                plan_repaired=None,
                reject_reason=f"Validation failed: {'; '.join(validation.errors)}",
            )

        # Proposal accepted — return it for the orchestrator to apply
        logger.info(
            "repair.proposal_accepted",
            extra={
                "attempt": attempt,
                "repair_type": proposal.repair_type.value,
                "target": proposal.target,
                "original": proposal.original_value,
                "proposed": proposal.proposed_value,
            },
        )

        return RepairResult(
            attempt=attempt,
            proposal=proposal,
            accepted=True,
            applied=False,  # Not yet applied — orchestrator applies it
            plan_repaired=None,
        )

    def can_repair(self, failure_stage: str) -> bool:
        """Check if the repair loop can handle this failure stage.

        Args:
            failure_stage: The stage where deployment failed.

        Returns:
            True if repair is possible for this stage.
        """
        return failure_stage in self.engine.supported_failure_stages()

    def max_attempts(self) -> int:
        """Return maximum repair attempts."""
        return self.engine.max_attempts()
