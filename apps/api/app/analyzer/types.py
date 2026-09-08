"""Type definitions for the Repository Analyzer.

All types are frozen dataclasses for immutability and hashability.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DetectedSignal:
    """A signal detected during analysis with evidence."""

    field: str
    value: str
    confidence: str  # HIGH, MEDIUM, LOW
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EnvironmentVariable:
    """An environment variable detected in the repository."""

    name: str
    required: bool
    secret: bool
    source: str
    default: Optional[str] = None


@dataclass(frozen=True)
class ServiceDependency:
    """An external service dependency detected in the repository."""

    name: str  # postgres, redis, mysql, etc.
    required: bool
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompatibilityResult:
    """Result of compatibility evaluation."""

    status: str  # SUPPORTED, SUPPORTED_WITH_WARNINGS, UNSUPPORTED, BLOCKED
    confidence: str  # HIGH, MEDIUM, LOW
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RepositoryInfo:
    """Information about the repository being analyzed."""

    url: str
    commit_sha: str
    owner: str
    repo: str


@dataclass(frozen=True)
class ApplicationInfo:
    """Detected application information."""

    language: str
    framework: Optional[str]
    framework_version: Optional[str]
    confidence: str


@dataclass(frozen=True)
class BuildInfo:
    """Build configuration detected in the repository."""

    package_manager: str
    install_command: Optional[str]
    build_command: Optional[str]
    working_directory: str


@dataclass(frozen=True)
class RuntimeInfo:
    """Runtime configuration detected in the repository."""

    start_command: str
    port: int
    host: str
    health_check_path: str


@dataclass(frozen=True)
class FileInventory:
    """Inventory of files in the repository."""

    root: str
    files: list[str] = field(default_factory=list)
    key_files: dict[str, Optional[str]] = field(default_factory=dict)
    ignored_dirs: list[str] = field(default_factory=list)
    is_monorepo: bool = False
    monorepo_packages: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionPlan:
    """Immutable, typed ExecutionPlan produced by the analyzer."""

    repository: RepositoryInfo
    application: ApplicationInfo
    build: BuildInfo
    runtime: RuntimeInfo
    environment: list[EnvironmentVariable] = field(default_factory=list)
    services: list[ServiceDependency] = field(default_factory=list)
    compatibility: CompatibilityResult = field(
        default_factory=lambda: CompatibilityResult(
            status="SUPPORTED", confidence="HIGH"
        )
    )
    evidence: list[DetectedSignal] = field(default_factory=list)
    created_at: str = ""
