from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


Broker = Literal["groww", "zerodha"]
AssetType = Literal["stock", "etf"]


class HoldingsImportRequest(BaseModel):
    file_path: str = Field(..., min_length=3)
    broker: Broker
    asset_type: AssetType
    replace_existing: bool = True


class ImportErrorRow(BaseModel):
    row_number: int
    message: str


class HoldingsImportResult(BaseModel):
    import_job_id: int
    source_path: str
    broker: Broker
    asset_type: AssetType
    total_rows: int
    imported_rows: int
    skipped_rows: int
    errors: list[ImportErrorRow]
    created_at: datetime


class ImportedHolding(BaseModel):
    symbol: str
    name: str | None = None
    isin: str | None = None
    broker: str
    asset_type: str
    quantity: float
    average_price: float
    buy_value: float
    closing_price: float | None = None
    closing_value: float | None = None
    unrealised_pnl: float | None = None
    is_cash_reserve: bool
    reserve_for: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class HoldingsSnapshotResponse(BaseModel):
    holdings: list[ImportedHolding]
