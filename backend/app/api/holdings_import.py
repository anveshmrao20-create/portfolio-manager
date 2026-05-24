from pathlib import Path
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.database.session import get_db_session
from backend.app.schemas.holdings_import import (
    HoldingsImportRequest,
    HoldingsImportResult,
    HoldingsSnapshotResponse,
)
from backend.app.services import holdings_import_service


router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/holdings", response_model=HoldingsImportResult, status_code=status.HTTP_201_CREATED)
def import_holdings(
    payload: HoldingsImportRequest,
    db: Session = Depends(get_db_session),
) -> HoldingsImportResult:
    try:
        return holdings_import_service.import_holdings(payload, db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/holdings/snapshot", response_model=HoldingsSnapshotResponse)
def get_holdings_snapshot(db: Session = Depends(get_db_session)) -> HoldingsSnapshotResponse:
    return holdings_import_service.get_holdings_snapshot(db)


@router.post("/holdings/upload", response_model=HoldingsImportResult, status_code=status.HTTP_201_CREATED)
async def import_holdings_upload(
    file: UploadFile = File(...),
    broker: str = Form(...),
    asset_type: str = Form(...),
    replace_existing: bool = Form(True),
    db: Session = Depends(get_db_session),
) -> HoldingsImportResult:
    suffix = Path(file.filename or "").suffix or ".tmp"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(await file.read())
            temp_path = temp_file.name

        payload = HoldingsImportRequest(
            file_path=temp_path,
            broker=broker,  # validated by schema literal
            asset_type=asset_type,  # validated by schema literal
            replace_existing=replace_existing,
        )
        return holdings_import_service.import_holdings(payload, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)
