from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl


class RepositoryCreate(BaseModel):
    url: HttpUrl


class RepositoryResponse(BaseModel):
    id: str
    url: str
    name: str
    default_branch: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RepositorySnapshotResponse(BaseModel):
    id: str
    commit_sha: str
    branch: str
    cloned_at: datetime

    model_config = {"from_attributes": True}
