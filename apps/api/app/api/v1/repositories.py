from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user_id
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.repository import RepositoryService, validate_github_url
from app.core.exceptions import ValidationException

router = APIRouter()


class AnalysisResponse(BaseModel):
    """Response model for repository analysis."""

    repository_url: str
    commit_sha: str
    owner: str
    repo: str
    language: Optional[str] = None
    framework: Optional[str] = None
    framework_version: Optional[str] = None
    package_manager: str
    install_command: Optional[str] = None
    build_command: Optional[str] = None
    start_command: str
    port: int
    host: str
    health_check_path: str
    environment: list[dict]
    services: list[dict]
    compatibility_status: str
    compatibility_confidence: str
    warnings: list[str]
    blockers: list[str]
    evidence: list[dict]
    created_at: str


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_repository(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if not validate_github_url(request.url):
        raise ValidationException(
            f"Invalid GitHub URL: {request.url}. Must match: https://github.com/owner/repo"
        )

    repo_service = RepositoryService(db)
    repo = await repo_service.get_or_create(request.url, user_id)

    from app.services.build import BuildService
    build_service = BuildService()
    analysis = build_service.analyze_repository(str(request.url))

    snapshot = await repo_service.create_snapshot(
        repo.id, "pending", request.branch or "main"
    )

    await db.commit()

    return AnalyzeResponse(
        repository_id=str(repo.id),
        snapshot_id=str(snapshot.id),
        status="queued",
    )


@router.post("/analyze-direct", response_model=AnalysisResponse)
async def analyze_repository_direct(
    request: AnalyzeRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Analyze a repository directly and return the ExecutionPlan.

    This endpoint performs static analysis without persisting to database.
    It never executes repository code.
    """
    if not validate_github_url(request.url):
        raise ValidationException(
            f"Invalid GitHub URL: {request.url}. Must match: https://github.com/owner/repo"
        )

    # Extract owner and repo from URL
    from app.services.repository import extract_owner_repo
    owner, repo = extract_owner_repo(request.url)

    # For now, we'll analyze a local snapshot
    # In production, this would clone the repo first
    # For demonstration, we'll use a placeholder
    import os
    from pathlib import Path

    # Check if there's a local snapshot available
    snapshot_dir = Path("snapshots") / owner / repo
    if not snapshot_dir.exists():
        raise ValidationException(
            f"Repository snapshot not found for {request.url}. "
            "Please clone the repository first."
        )

    from app.analyzer.analyzer import analyze_repository as run_analysis

    plan = run_analysis(
        repo_path=str(snapshot_dir),
        url=request.url,
        commit_sha="placeholder",  # Would be actual commit SHA
        owner=owner,
        repo=repo,
    )

    return AnalysisResponse(
        repository_url=plan.repository.url,
        commit_sha=plan.repository.commit_sha,
        owner=plan.repository.owner,
        repo=plan.repository.repo,
        language=plan.application.language,
        framework=plan.application.framework,
        framework_version=plan.application.framework_version,
        package_manager=plan.build.package_manager,
        install_command=plan.build.install_command,
        build_command=plan.build.build_command,
        start_command=plan.runtime.start_command,
        port=plan.runtime.port,
        host=plan.runtime.host,
        health_check_path=plan.runtime.health_check_path,
        environment=[asdict(e) for e in plan.environment],
        services=[asdict(s) for s in plan.services],
        compatibility_status=plan.compatibility.status,
        compatibility_confidence=plan.compatibility.confidence,
        warnings=plan.compatibility.warnings,
        blockers=plan.compatibility.blockers,
        evidence=[asdict(e) for e in plan.evidence],
        created_at=plan.created_at,
    )
