from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database.session import get_db_session
from backend.app.models.assistant import AssistantAskRequest, AssistantAskResponse, DailySummaryResponse
from backend.app.services.assistant_service import ask_portfolio_assistant, generate_daily_summary, get_latest_daily_summary


router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/ask", response_model=AssistantAskResponse)
def ask_assistant(payload: AssistantAskRequest, db: Session = Depends(get_db_session)) -> AssistantAskResponse:
    return ask_portfolio_assistant(payload.question, db)


@router.get("/daily-summary", response_model=DailySummaryResponse)
def latest_daily_summary(db: Session = Depends(get_db_session)) -> DailySummaryResponse:
    return get_latest_daily_summary(db)


@router.post("/daily-summary/generate", response_model=DailySummaryResponse)
def create_daily_summary(db: Session = Depends(get_db_session)) -> DailySummaryResponse:
    return generate_daily_summary(db)
