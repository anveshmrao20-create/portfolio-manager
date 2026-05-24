from pydantic import BaseModel, Field


class GoalSettings(BaseModel):
    target_portfolio_value: float = Field(..., gt=0)
    time_horizon_years: int = Field(10, ge=1, le=50)
    monthly_sip_amount: float = Field(..., ge=0)
    dip_cash_reserve: float = Field(..., ge=0)
    expected_annual_return_percent: float = Field(12, ge=0, le=40)
    risk_tolerance: str = Field(default="moderate", pattern="^(conservative|moderate|aggressive)$")
    return_volatility_percent: float = Field(18, ge=1, le=80)


class ProjectionPoint(BaseModel):
    year: int
    conservative_value: float
    realistic_value: float
    aggressive_value: float


class GoalScenario(BaseModel):
    name: str
    annual_return_percent: float
    projected_value: float
    required_monthly_sip: float
    status: str


class GoalProjection(BaseModel):
    target_portfolio_value: float
    current_portfolio_value: float
    time_horizon_years: int
    months_remaining: int
    expected_annual_return_percent: float
    monthly_sip_amount: float
    projected_value: float
    future_value_of_current_portfolio: float
    future_value_of_sips: float
    gap_to_goal: float
    required_monthly_sip: float
    additional_monthly_sip_required: float
    dip_cash_reserve: float
    suggested_dip_cash_reserve: float
    dip_cash_reserve_gap: float
    status: str
    realistic_target_value: float
    aggressive_target_value: float
    success_probability_percent: float
    scenarios: list[GoalScenario]
    projection_points: list[ProjectionPoint]


class GoalVerdict(BaseModel):
    status: str
    headline: str
    verdict: str
    key_findings: list[str]
    recommended_actions: list[str]
    warnings: list[str]
    projection: GoalProjection
