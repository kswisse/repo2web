"""Plan Builder module.

Builds an ExecutionPlan from analysis results.
"""

from dataclasses import dataclass
from typing import Optional

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
from app.analyzer.framework_detector import FrameworkDetection, get_framework_default_port
from app.analyzer.entrypoint_detector import EntrypointDetection
from app.analyzer.port_detector import PortDetection


@dataclass(frozen=True)
class AnalysisContext:
    """Context containing all analysis results."""

    repository: RepositoryInfo
    inventory: FileInventory
    language: Optional[str]
    framework: Optional[FrameworkDetection]
    entrypoint: Optional[EntrypointDetection]
    port: Optional[PortDetection]
    environment: list[EnvironmentVariable]
    services: list[ServiceDependency]
    compatibility: CompatibilityResult
    evidence: list[DetectedSignal]
    package_manager: str
    all_dependencies: dict[str, str]


def build_execution_plan(context: AnalysisContext) -> ExecutionPlan:
    """Build an ExecutionPlan from analysis context.

    Args:
        context: AnalysisContext containing all analysis results.

    Returns:
        ExecutionPlan built from the analysis.
    """
    # Build application info
    application = _build_application_info(context)

    # Build build info
    build = _build_build_info(context)

    # Build runtime info
    runtime = _build_runtime_info(context)

    # Create the execution plan
    return ExecutionPlan(
        repository=context.repository,
        application=application,
        build=build,
        runtime=runtime,
        environment=context.environment,
        services=context.services,
        compatibility=context.compatibility,
        evidence=context.evidence,
        created_at="",  # Will be set by the analyzer
    )


def _build_application_info(context: AnalysisContext) -> ApplicationInfo:
    """Build application info from context.

    Args:
        context: AnalysisContext.

    Returns:
        ApplicationInfo.
    """
    language = context.language or "unknown"
    framework_name = context.framework.name if context.framework else None
    framework_version = None
    confidence = context.framework.confidence if context.framework else "LOW"

    # Try to extract framework version from dependencies
    if framework_name and framework_name in context.all_dependencies:
        version = context.all_dependencies[framework_name]
        if version and version != "*":
            framework_version = version

    return ApplicationInfo(
        language=language,
        framework=framework_name,
        framework_version=framework_version,
        confidence=confidence,
    )


def _build_build_info(context: AnalysisContext) -> BuildInfo:
    """Build build info from context.

    Args:
        context: AnalysisContext.

    Returns:
        BuildInfo.
    """
    package_manager = context.package_manager
    install_command = None
    build_command = None
    working_directory = "."

    # Determine install command based on package manager
    if package_manager == "npm":
        install_command = "npm install"
        # Check for build script
        if context.inventory.key_files.get("package.json"):
            import json
            try:
                pkg = json.loads(context.inventory.key_files["package.json"])
                scripts = pkg.get("scripts", {})
                if "build" in scripts:
                    build_command = "npm run build"
            except json.JSONDecodeError:
                pass
    elif package_manager == "yarn":
        install_command = "yarn install"
        if context.inventory.key_files.get("package.json"):
            import json
            try:
                pkg = json.loads(context.inventory.key_files["package.json"])
                scripts = pkg.get("scripts", {})
                if "build" in scripts:
                    build_command = "yarn build"
            except json.JSONDecodeError:
                pass
    elif package_manager == "pnpm":
        install_command = "pnpm install"
        if context.inventory.key_files.get("package.json"):
            import json
            try:
                pkg = json.loads(context.inventory.key_files["package.json"])
                scripts = pkg.get("scripts", {})
                if "build" in scripts:
                    build_command = "pnpm build"
            except json.JSONDecodeError:
                pass
    elif package_manager == "pip":
        install_command = "pip install -r requirements.txt"
        # Check if pyproject.toml exists
        if "pyproject.toml" in context.inventory.key_files:
            install_command = "pip install ."
    elif package_manager == "pipenv":
        install_command = "pipenv install"
    elif package_manager == "poetry":
        install_command = "poetry install"

    return BuildInfo(
        package_manager=package_manager,
        install_command=install_command,
        build_command=build_command,
        working_directory=working_directory,
    )


def _build_runtime_info(context: AnalysisContext) -> RuntimeInfo:
    """Build runtime info from context.

    Args:
        context: AnalysisContext.

    Returns:
        RuntimeInfo.
    """
    # Get start command
    if context.entrypoint:
        start_command = context.entrypoint.command
    else:
        start_command = _get_default_start_command(context)

    # Get port
    if context.port:
        port = context.port.port
    elif context.framework:
        port = get_framework_default_port(context.framework.name)
    else:
        port = 3000

    # Get host
    host = "0.0.0.0"

    # Get health check path
    health_check_path = _get_health_check_path(context)

    return RuntimeInfo(
        start_command=start_command,
        port=port,
        host=host,
        health_check_path=health_check_path,
    )


def _get_default_start_command(context: AnalysisContext) -> str:
    """Get default start command based on framework.

    Args:
        context: AnalysisContext.

    Returns:
        Default start command.
    """
    if not context.framework:
        if context.language == "python":
            return "python app.py"
        elif context.language == "node":
            return "npm start"
        return "echo 'No start command detected'"

    framework = context.framework.name

    if framework == "fastapi":
        return "uvicorn main:app --host 0.0.0.0 --port 8000"
    elif framework == "flask":
        return "python app.py"
    elif framework == "django":
        return "python manage.py runserver 0.0.0.0:8000"
    elif framework == "streamlit":
        return "streamlit run app.py"
    elif framework == "gradio":
        return "python app.py"
    elif framework == "sanic":
        return "python app.py"
    elif framework == "tornado":
        return "python app.py"
    elif framework == "nextjs":
        return "npm start"
    elif framework == "nuxt":
        return "npm start"
    elif framework == "svelte":
        return "npm run dev"
    elif framework == "angular":
        return "npm start"
    elif framework == "vue":
        return "npm run serve"
    elif framework == "react":
        return "npm start"
    elif framework == "express":
        return "npm start"
    elif framework == "koa":
        return "npm start"
    elif framework == "fastify":
        return "npm start"

    return "npm start"


def _get_health_check_path(context: AnalysisContext) -> str:
    """Get health check path based on framework.

    Args:
        context: AnalysisContext.

    Returns:
        Health check path.
    """
    if not context.framework:
        return "/"

    framework = context.framework.name

    if framework == "fastapi":
        return "/health"
    elif framework == "flask":
        return "/health"
    elif framework == "django":
        return "/health/"
    elif framework == "streamlit":
        return "/healthz"
    elif framework == "gradio":
        return "/info"
    elif framework == "nextjs":
        return "/api/health"
    elif framework == "express":
        return "/health"
    elif framework == "koa":
        return "/health"
    elif framework == "fastify":
        return "/health"

    return "/health"
