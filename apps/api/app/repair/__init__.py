"""
AI Repair module.

Provides controlled, bounded repair proposals for deployment failures.
All proposals are deterministically validated before execution.
"""

from .types import RepairType, RepairProposal, RepairContext, RepairResult
from .engine import RepairEngine
from .validator import validate_repair_proposal, ValidationResult
from .deterministic import DeterministicRepairProvider
from .loop import RepairLoop

__all__ = [
    "RepairType",
    "RepairProposal",
    "RepairContext",
    "RepairResult",
    "RepairEngine",
    "validate_repair_proposal",
    "ValidationResult",
    "DeterministicRepairProvider",
    "RepairLoop",
]
