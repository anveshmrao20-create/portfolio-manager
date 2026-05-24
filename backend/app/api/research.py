import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from backend.app.database.session import get_db_session
from backend.app.models.research import (
    ResearchDocumentItem,
    ResearchIngestRequest,
    ResearchIngestResult,
    ResearchSearchRequest,
    ResearchSearchResponse,
    TelegramAuthStartRequest,
    TelegramAuthVerifyRequest,
    TelegramFetchRequest,
    TelegramGroupItem,
)
from backend.app.services import research_service, telegram_service


router = APIRouter(prefix="/research", tags=["research"])


@router.post("/telegram/auth/start")
def telegram_auth_start(payload: TelegramAuthStartRequest) -> dict:
    status = telegram_service.start_login(payload.api_id, payload.api_hash, payload.phone_number)
    return {"status": status}


@router.post("/telegram/auth/verify")
def telegram_auth_verify(payload: TelegramAuthVerifyRequest) -> dict:
    status = telegram_service.verify_login(payload.code, payload.password)
    return {"status": status}


@router.get("/telegram/groups", response_model=list[TelegramGroupItem])
def telegram_groups(api_id: int = Query(...), api_hash: str = Query(...)) -> list[TelegramGroupItem]:
    try:
        return telegram_service.list_joined_groups(api_id, api_hash)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/telegram/fetch")
def telegram_fetch(payload: TelegramFetchRequest) -> dict:
    try:
        paths = telegram_service.fetch_documents(
            api_id=payload.api_id,
            api_hash=payload.api_hash,
            group_ids=payload.group_ids,
            group_usernames=payload.group_usernames,
            days_back=payload.days_back,
            max_docs_per_group=payload.max_docs_per_group,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"downloaded_count": len(paths), "downloaded_paths": paths[:50]}


@router.post("/ingest", response_model=ResearchIngestResult)
def ingest_documents(payload: ResearchIngestRequest, db: Session = Depends(get_db_session)) -> ResearchIngestResult:
    try:
        return research_service.ingest_research_documents(payload, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/search", response_model=ResearchSearchResponse)
def search_documents(payload: ResearchSearchRequest, db: Session = Depends(get_db_session)) -> ResearchSearchResponse:
    return research_service.search_research(payload, db)


@router.get("/documents", response_model=list[ResearchDocumentItem])
def list_documents(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db_session)) -> list[ResearchDocumentItem]:
    return research_service.list_research_documents(db, limit=limit)


@router.post("/ingest/upload-file", response_model=ResearchIngestResult)
async def ingest_uploaded_file(
    file: UploadFile = File(...),
    channel_name: str | None = Form(None),
    clear_existing: bool = Form(False),
    max_pdf_pages: int = Form(30),
    db: Session = Depends(get_db_session),
) -> ResearchIngestResult:
    suffix = Path(file.filename or "").suffix or ".txt"
    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = Path(temp_dir) / (file.filename or f"upload{suffix}")
        file_path.write_bytes(await file.read())
        payload = ResearchIngestRequest(
            source_folder=temp_dir,
            channel_name=channel_name,
            clear_existing=clear_existing,
            max_files=1,
            max_pdf_pages=max_pdf_pages,
        )
        return research_service.ingest_research_documents(payload, db)
