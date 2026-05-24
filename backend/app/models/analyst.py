from pydantic import BaseModel

from backend.app.models.portfolio import AssetType
from backend.app.models.rating import Rating
from backend.app.models.settings import GoalVerdict


class RatedHolding(BaseModel):
    symbol: str
    name: str | None
    isin: str | None
    asset_type: AssetType
    sector: str | None
    quantity: float
    average_price: float
    closing_price: float | None
    invested_value: float
    current_value: float
    unrealised_pnl: float
    portfolio_weight_percent: float
    is_cash_reserve: bool
    rating: Rating | None
    action: str


class SectorExposure(BaseModel):
    sector: str
    current_value: float
    portfolio_weight_percent: float
    holdings_count: int


class PortfolioAnalystVerdict(BaseModel):
    status: str
    headline: str
    verdict: str
    portfolio_value: float
    holdings_count: int
    rated_count: int
    rating_coverage_percent: float
    unrated_symbols: list[str]
    top_position: RatedHolding | None
    holdings: list[RatedHolding]
    sector_exposure: list[SectorExposure]
    key_findings: list[str]
    recommended_actions: list[str]
    warnings: list[str]
    goal_verdict: GoalVerdict
