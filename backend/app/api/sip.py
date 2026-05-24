from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database.session import get_db_session
from backend.app.models.sip import SipDipSnapshot
from backend.app.services import sip_service


router = APIRouter(prefix="/sip", tags=["sip"])


@router.get("/recommendations", response_model=SipDipSnapshot)
def get_sip_recommendations(
    stock_monthly_budget: float = Query(default=25000, ge=1000, le=500000),
    etf_weekly_budget: float = Query(default=15000, ge=1000, le=500000),
    reserve_ratio_target: float = Query(default=20, ge=5, le=50),
    db: Session = Depends(get_db_session),
) -> SipDipSnapshot:
    return sip_service.get_sip_dip_snapshot(
        db=db,
        stock_monthly_budget=stock_monthly_budget,
        etf_weekly_budget=etf_weekly_budget,
        reserve_ratio_target=reserve_ratio_target,
    )
