from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database.session import get_db_session
from backend.app.models.technical import TechnicalSnapshot
from backend.app.services import technical_service


router = APIRouter(prefix="/technical", tags=["technical"])


@router.get("/snapshot", response_model=TechnicalSnapshot)
def get_technical_snapshot(
    lookback_days: int = Query(default=365, ge=120, le=1500),
    db: Session = Depends(get_db_session),
) -> TechnicalSnapshot:
    return technical_service.get_technical_snapshot(db, lookback_days=lookback_days)
