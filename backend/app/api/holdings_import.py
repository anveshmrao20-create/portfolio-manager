from fastapi import APIRouter, Depends, HTTPException, status
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
