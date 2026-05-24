from pydantic import BaseModel


class FundamentalMetrics(BaseModel):
    trailing_pe: float | None
    forward_pe: float | None
    price_to_book: float | None
    peg_ratio: float | None
    roe_percent: float | None
    debt_to_equity: float | None
    operating_margin_percent: float | None
    profit_margin_percent: float | None
    revenue_growth_percent: float | None
    earnings_growth_percent: float | None
    free_cash_flow: float | None
    operating_cash_flow: float | None


class FundamentalSignalItem(BaseModel):
    symbol: str
    asset_type: str
    broker: str
    score: int
    grade: str
    confidence_percent: float
    metrics: FundamentalMetrics
    strengths: list[str]
    weaknesses: list[str]


class FundamentalSnapshot(BaseModel):
    total_symbols: int
    generated_items: int
    failed_symbols: list[str]
    items: list[FundamentalSignalItem]
