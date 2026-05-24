from pydantic import BaseModel


class SipPick(BaseModel):
    symbol: str
    asset_type: str
    broker: str
    combined_score: float
    suggested_amount: float
    reason: str


class DipOpportunity(BaseModel):
    symbol: str
    asset_type: str
    dip_percent: float | None
    technical_score: float
    fundamental_score: int
    conviction: str
    suggested_action: str
    suggested_amount: float


class ReserveCashPlan(BaseModel):
    current_reserve_value: float
    target_reserve_value: float
    reserve_gap_value: float
    reserve_ratio_percent: float
    recommended_ratio_percent: float


class SipDipSnapshot(BaseModel):
    stock_monthly_picks: list[SipPick]
    etf_weekly_picks: list[SipPick]
    dip_opportunities: list[DipOpportunity]
    reserve_cash_plan: ReserveCashPlan
    notes: list[str]
