from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database.session import get_db_session
from backend.app.models.fundamental import FundamentalSnapshot
from backend.app.services import fundamental_service


router = APIRouter(prefix="/fundamental", tags=["fundamental"])


@router.get("/snapshot", response_model=FundamentalSnapshot)
def get_fundamental_snapshot(db: Session = Depends(get_db_session)) -> FundamentalSnapshot:
    return fundamental_service.get_fundamental_snapshot(db)
