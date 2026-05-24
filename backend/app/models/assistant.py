from pydantic import BaseModel, Field
from datetime import datetime


class AssistantAskRequest(BaseModel):
    question: str = Field(..., min_length=3)


class AssistantEvidence(BaseModel):
    source_type: str
    reference: str
    detail: str


class AssistantAskResponse(BaseModel):
    question: str
    intent: str
    answer: str
    confidence: str
    evidence: list[AssistantEvidence]


class DailySummaryPoint(BaseModel):
    title: str
    detail: str


class DailySummaryResponse(BaseModel):
    generated_at: datetime
    summary_date: str
    headline: str
    points: list[DailySummaryPoint]
