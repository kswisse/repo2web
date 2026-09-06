from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BuildStepResponse(BaseModel):
    id: str
    step_order: int
    name: str
    command: str
    status: str
    exit_code: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BuildLogResponse(BaseModel):
    id: str
    timestamp: datetime
    level: str
    message: str

    model_config = {"from_attributes": True}


class BuildJobResponse(BaseModel):
    id: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    steps: list[BuildStepResponse] = []

    model_config = {"from_attributes": True}
