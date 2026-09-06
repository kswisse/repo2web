"""Deterministic Repository Analyzer.

This package provides static analysis of repositories to produce
structured ExecutionPlan objects without executing any code.
"""

from app.analyzer.analyzer import analyze_repository
from app.analyzer.types import (
    ApplicationInfo,
    BuildInfo,
    CompatibilityResult,
    DetectedSignal,
    EnvironmentVariable,
    ExecutionPlan,
    FileInventory,
    RepositoryInfo,
    RuntimeInfo,
    ServiceDependency,
)

__all__ = [
    "analyze_repository",
    "ApplicationInfo",
    "BuildInfo",
    "CompatibilityResult",
    "DetectedSignal",
    "EnvironmentVariable",
    "ExecutionPlan",
    "FileInventory",
    "RepositoryInfo",
    "RuntimeInfo",
    "ServiceDependency",
]
