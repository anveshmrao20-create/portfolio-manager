from datetime import datetime

from pydantic import BaseModel, Field


class ResearchIngestRequest(BaseModel):
    source_folder: str = Field(..., min_length=3)
    channel_name: str | None = None
    clear_existing: bool = False
    max_files: int = Field(default=50, ge=1, le=5000)
    max_pdf_pages: int = Field(default=30, ge=1, le=500)


class ResearchIngestResult(BaseModel):
    ingest_job_id: int
    total_files: int
    imported_documents: int
    skipped_files: int
    errors: list[str]
    created_at: datetime


class ResearchDocumentItem(BaseModel):
    document_id: int
    channel_name: str | None
    file_name: str
    file_type: str
    symbols: list[str]
    created_at: datetime


class ResearchSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    symbol: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class ResearchSearchHit(BaseModel):
    document_id: int
    file_name: str
    channel_name: str | None
    symbols: list[str]
    snippet: str
    score: float


class ResearchSearchResponse(BaseModel):
    total_hits: int
    hits: list[ResearchSearchHit]


class TelegramAuthStartRequest(BaseModel):
    api_id: int
    api_hash: str
    phone_number: str


class TelegramAuthVerifyRequest(BaseModel):
    code: str
    password: str | None = None


class TelegramGroupItem(BaseModel):
    id: int
    title: str
    username: str | None


class TelegramFetchRequest(BaseModel):
    api_id: int
    api_hash: str
    group_ids: list[int] = Field(default_factory=list)
    group_usernames: list[str] = Field(default_factory=list)
    days_back: int = Field(default=7, ge=1, le=365)
    max_docs_per_group: int = Field(default=100, ge=1, le=1000)
