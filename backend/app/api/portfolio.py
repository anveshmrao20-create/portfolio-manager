from fastapi import APIRouter, HTTPException, status

from backend.app.models.portfolio import Holding, HoldingCreate, PortfolioSummary
from backend.app.services import portfolio_service


router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/holdings", response_model=list[Holding])
def list_holdings() -> list[Holding]:
    return portfolio_service.list_holdings()


@router.post("/holdings", response_model=Holding, status_code=status.HTTP_201_CREATED)
def add_holding(payload: HoldingCreate) -> Holding:
    return portfolio_service.add_holding(payload)


@router.put("/holdings/replace", response_model=list[Holding])
def replace_holdings(payload: list[HoldingCreate]) -> list[Holding]:
    return portfolio_service.replace_holdings(payload)


@router.delete("/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(holding_id: str) -> None:
    deleted = portfolio_service.delete_holding(holding_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")


@router.get("/summary", response_model=PortfolioSummary)
def get_summary() -> PortfolioSummary:
    return portfolio_service.get_summary()
