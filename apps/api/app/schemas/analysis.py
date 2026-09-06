from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LanguageInfo(BaseModel):
    name: str
    version: Optional[str] = None
    percentage: float = 0.0


class EnvironmentVariable(BaseModel):
    name: str
    required: bool = False
    default: Optional[str] = None
    description: Optional[str] = None


class AnalysisResultResponse(BaseModel):
    id: str
    snapshot_id: str
    detected_languages: list[LanguageInfo]
    framework: Optional[str] = None
    package_manager: Optional[str] = None
    entrypoint: Optional[str] = None
    install_command: Optional[str] = None
    build_command: Optional[str] = None
    run_command: Optional[str] = None
    expected_port: Optional[int] = None
    environment_variables: list[EnvironmentVariable]
    confidence_score: float
    warnings: list[str]
    unsupported_requirements: list[str]
    analyzed_at: datetime

    model_config = {"from_attributes": True}


class AnalyzeRequest(BaseModel):
    url: str
    branch: Optional[str] = None


class AnalyzeResponse(BaseModel):
    repository_id: str
    snapshot_id: str
    status: str
