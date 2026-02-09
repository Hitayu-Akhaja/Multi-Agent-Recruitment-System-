from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScoreResult(BaseModel):
    filename: str
    evaluation: Dict[str, Any]


class ScoreResponse(BaseModel):
    job_id: str
    scored_resumes: List[ScoreResult] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    score_sheet_path: Optional[str] = None
