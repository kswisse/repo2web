import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException
from app.models.repository import Repository, RepositorySnapshot


GITHUB_URL_PATTERN = re.compile(
    r"^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(/.*)?$"
)


def validate_github_url(url: str) -> bool:
    return bool(GITHUB_URL_PATTERN.match(url))


def extract_owner_repo(url: str) -> tuple[str, str]:
    match = GITHUB_URL_PATTERN.match(url)
    if not match:
        raise ValidationException(f"Invalid GitHub URL: {url}")
    parts = url.rstrip("/").split("/")
    owner = parts[-2]
    repo = parts[-1].removesuffix(".git")
    return owner, repo


class RepositoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_url(self, url: str) -> bool:
        if not validate_github_url(url):
            raise ValidationException(
                f"Invalid GitHub URL: {url}. Must match: https://github.com/owner/repo"
            )
        return True

    async def get_or_create(self, url: str, user_id: str) -> Repository:
        await self.validate_url(url)

        result = await self.db.execute(
            select(Repository).where(Repository.url == url, Repository.owner_id == user_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        owner, name = extract_owner_repo(url)
        repo = Repository(url=url, name=name, owner_id=user_id)
        self.db.add(repo)
        await self.db.flush()
        return repo

    async def get(self, repo_id: str) -> Repository:
        result = await self.db.execute(
            select(Repository).where(Repository.id == repo_id)
        )
        repo = result.scalar_one_or_none()
        if not repo:
            raise NotFoundException("Repository", repo_id)
        return repo

    async def create_snapshot(
        self, repo_id: str, commit_sha: str, branch: str
    ) -> RepositorySnapshot:
        snapshot = RepositorySnapshot(
            repository_id=repo_id,
            commit_sha=commit_sha,
            branch=branch,
        )
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot
