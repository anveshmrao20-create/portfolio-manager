from fastapi import APIRouter

from backend.app.models.analyst import PortfolioAnalystVerdict
from backend.app.services import analyst_service


router = APIRouter(prefix="/analyst", tags=["analyst"])


@router.get("/portfolio-verdict", response_model=PortfolioAnalystVerdict)
def get_portfolio_verdict() -> PortfolioAnalystVerdict:
    return analyst_service.get_portfolio_verdict()
