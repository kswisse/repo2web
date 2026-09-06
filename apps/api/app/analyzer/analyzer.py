"""Main Analyzer module.

Orchestrates the repository analysis pipeline.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.analyzer.types import (
    DetectedSignal,
    EnvironmentVariable,
    ExecutionPlan,
    FileInventory,
    RepositoryInfo,
    ServiceDependency,
)
from app.analyzer.file_inventory import scan_repository
from app.analyzer.manifest_parser import detect_package_manager, parse_manifests
from app.analyzer.framework_detector import detect_framework
from app.analyzer.entrypoint_detector import detect_entrypoint
from app.analyzer.port_detector import detect_port
from app.analyzer.env_detector import detect_environment_variables
from app.analyzer.dependency_detector import detect_service_dependencies
from app.analyzer.compatibility import evaluate_compatibility
from app.analyzer.plan_builder import AnalysisContext, build_execution_plan
from app.analyzer.plan_validator import validate_plan


def analyze_repository(
    repo_path: str,
    url: str = "",
    commit_sha: str = "",
    owner: str = "",
    repo: str = "",
) -> ExecutionPlan:
    """Analyze a repository and produce an ExecutionPlan.

    This function performs static analysis only - it never executes code.

    Args:
        repo_path: Path to the repository snapshot.
        url: Repository URL.
        commit_sha: Commit SHA.
        owner: Repository owner.
        repo: Repository name.

    Returns:
        ExecutionPlan with all detected information.

    Raises:
        FileNotFoundError: If repo_path does not exist.
        ValueError: If required parameters are missing.
    """
    # Validate inputs
    if not Path(repo_path).exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

    # Step 1: Scan repository
    inventory = scan_repository(repo_path)

    # Step 2: Parse manifests
    manifests = parse_manifests(inventory.key_files)
    package_manager = detect_package_manager(inventory.key_files)

    # Merge all dependencies
    all_dependencies = {}
    for manifest in manifests:
        all_dependencies.update(manifest.dependencies)

    # Step 3: Detect language
    language = _detect_language(inventory, all_dependencies)

    # Step 4: Detect framework
    file_names = [Path(f).name for f in inventory.files]
    framework = detect_framework(all_dependencies, file_names, language)

    # Step 5: Detect entrypoint
    entrypoint = detect_entrypoint(
        inventory.key_files,
        file_names,
        framework.name if framework else None,
        language or "unknown",
    )

    # Step 6: Detect port
    port = detect_port(inventory.key_files, file_names, framework.name if framework else None)

    # Step 7: Detect environment variables
    environment = detect_environment_variables(inventory.key_files, file_names)

    # Step 8: Detect service dependencies
    services = detect_service_dependencies(inventory.key_files, all_dependencies)

    # Step 9: Collect evidence
    evidence = _collect_evidence(
        language,
        framework,
        entrypoint,
        port,
        environment,
        services,
        package_manager,
    )

    # Step 10: Evaluate compatibility
    compatibility = evaluate_compatibility(
        language=language,
        framework=framework.name if framework else None,
        entrypoint=entrypoint.command if entrypoint else None,
        port=port.port if port else None,
        key_files=inventory.key_files,
        file_names=file_names,
        evidence=evidence,
    )

    # Step 11: Build repository info
    repository_info = RepositoryInfo(
        url=url,
        commit_sha=commit_sha,
        owner=owner,
        repo=repo,
    )

    # Step 12: Build execution plan
    context = AnalysisContext(
        repository=repository_info,
        inventory=inventory,
        language=language,
        framework=framework,
        entrypoint=entrypoint,
        port=port,
        environment=environment,
        services=services,
        compatibility=compatibility,
        evidence=evidence,
        package_manager=package_manager,
        all_dependencies=all_dependencies,
    )

    plan = build_execution_plan(context)

    # Step 13: Validate plan
    validation = validate_plan(plan)
    if not validation.valid:
        # If validation fails, adjust compatibility
        from app.analyzer.types import CompatibilityResult
        plan = ExecutionPlan(
            repository=plan.repository,
            application=plan.application,
            build=plan.build,
            runtime=plan.runtime,
            environment=plan.environment,
            services=plan.services,
            compatibility=CompatibilityResult(
                status="SUPPORTED_WITH_WARNINGS",
                confidence=plan.compatibility.confidence,
                blockers=plan.compatibility.blockers,
                warnings=plan.compatibility.warnings + validation.errors,
            ),
            evidence=plan.evidence,
            created_at=plan.created_at,
        )

    # Step 14: Set creation timestamp
    plan = ExecutionPlan(
        repository=plan.repository,
        application=plan.application,
        build=plan.build,
        runtime=plan.runtime,
        environment=plan.environment,
        services=plan.services,
        compatibility=plan.compatibility,
        evidence=plan.evidence,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    return plan


def _detect_language(
    inventory: FileInventory,
    dependencies: dict[str, str],
) -> Optional[str]:
    """Detect the primary language of the repository.

    Args:
        inventory: File inventory.
        dependencies: Parsed dependencies.

    Returns:
        Detected language or None.
    """
    # Check for Python indicators
    python_indicators = [
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "Pipfile",
        "poetry.lock",
    ]

    has_python_manifest = any(f in inventory.key_files for f in python_indicators)
    has_python_files = any(f.endswith(".py") for f in inventory.files)

    # Check for Node.js indicators
    node_indicators = [
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
    ]

    has_node_manifest = any(f in inventory.key_files for f in node_indicators)
    has_node_files = any(
        f.endswith((".js", ".ts", ".jsx", ".tsx")) for f in inventory.files
    )

    # Determine language based on evidence
    python_score = 0
    node_score = 0

    if has_python_manifest:
        python_score += 2
    if has_python_files:
        python_score += 1

    if has_node_manifest:
        node_score += 2
    if has_node_files:
        node_score += 1

    # Check dependencies for language clues
    python_deps = {"flask", "django", "fastapi", "streamlit", "gradio", "sanic", "tornado"}
    node_deps = {"express", "koa", "fastify", "next", "react", "vue", "angular", "svelte"}

    for dep in dependencies:
        if dep in python_deps:
            python_score += 2
        if dep in node_deps:
            node_score += 2

    # Return the language with higher score
    if python_score > node_score:
        return "python"
    elif node_score > python_score:
        return "node"
    elif python_score > 0:
        return "python"
    elif node_score > 0:
        return "node"

    return None


def _collect_evidence(
    language: Optional[str],
    framework,
    entrypoint,
    port,
    environment: list[EnvironmentVariable],
    services: list[ServiceDependency],
    package_manager: str,
) -> list[DetectedSignal]:
    """Collect all evidence from detection results.

    Args:
        language: Detected language.
        framework: Framework detection result.
        entrypoint: Entrypoint detection result.
        port: Port detection result.
        environment: Detected environment variables.
        services: Detected service dependencies.
        package_manager: Detected package manager.

    Returns:
        List of DetectedSignal objects.
    """
    evidence = []

    # Language evidence
    if language:
        evidence.append(DetectedSignal(
            field="language",
            value=language,
            confidence="HIGH",
            evidence=[f"Detected language: {language}"],
        ))

    # Framework evidence
    if framework:
        evidence.append(DetectedSignal(
            field="framework",
            value=framework.name,
            confidence=framework.confidence,
            evidence=framework.evidence,
        ))

    # Entrypoint evidence
    if entrypoint:
        evidence.append(DetectedSignal(
            field="entrypoint",
            value=entrypoint.command,
            confidence=entrypoint.confidence,
            evidence=entrypoint.evidence,
        ))

    # Port evidence
    if port:
        evidence.append(DetectedSignal(
            field="port",
            value=str(port.port),
            confidence=port.confidence,
            evidence=port.evidence,
        ))

    # Package manager evidence
    evidence.append(DetectedSignal(
        field="package_manager",
        value=package_manager,
        confidence="HIGH",
        evidence=[f"Detected package manager: {package_manager}"],
    ))

    # Environment variables evidence
    if environment:
        evidence.append(DetectedSignal(
            field="environment_variables",
            value=str(len(environment)),
            confidence="MEDIUM",
            evidence=[f"Found {len(environment)} environment variables"],
        ))

    # Service dependencies evidence
    if services:
        service_names = [s.name for s in services]
        evidence.append(DetectedSignal(
            field="service_dependencies",
            value=str(len(services)),
            confidence="MEDIUM",
            evidence=[f"Found service dependencies: {', '.join(service_names)}"],
        ))

    return evidence
