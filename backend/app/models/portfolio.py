from typing import Literal
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


AssetType = Literal["stock", "etf"]
Broker = Literal["groww", "zerodha", "unknown"]
ReserveFor = Literal["stock", "etf"]


class HoldingCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    quantity: float = Field(..., gt=0)
    average_price: float = Field(..., ge=0)
    buy_value: float | None = Field(default=None, ge=0)
    asset_type: AssetType = "stock"
    name: str | None = None
    isin: str | None = None
    sector: str | None = None
    closing_price: float | None = Field(default=None, ge=0)
    closing_value: float | None = Field(default=None, ge=0)
    unrealised_pnl: float | None = None
    broker: Broker = "unknown"
    is_cash_reserve: bool = False
    reserve_for: ReserveFor | None = None
    notes: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("isin")
    @classmethod
    def normalize_isin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()


class Holding(HoldingCreate):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AccountSummary(BaseModel):
    broker: Broker
    current_value: float
    equity_value: float
    cash_reserve_value: float
    stock_value: float
    etf_value: float
    stock_cash_reserve_value: float
    etf_cash_reserve_value: float


class PortfolioSummary(BaseModel):
    holdings: list[Holding]
    total_invested: float
    current_value: float
    equity_value: float
    cash_reserve_value: float
    unrealised_pnl: float
    stock_count: int
    etf_count: int
    cash_reserve_count: int
    by_account: list[AccountSummary]
