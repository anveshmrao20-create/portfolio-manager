from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from backend.app.models.portfolio import AssetType, Broker, ReserveFor


AnalystRating = Literal["strong_buy", "buy", "hold", "reduce", "avoid"]


class RatingCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    asset_type: AssetType = "stock"
    technical_score: float = Field(..., ge=0, le=100)
    fundamental_score: float = Field(..., ge=0, le=100)
    risk_score: float = Field(..., ge=0, le=100, description="Higher means safer / better risk control.")
    notes: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class RatingDraft(BaseModel):
    symbol: str
    asset_type: AssetType
    technical_score: float | None = Field(default=None, ge=0, le=100)
    fundamental_score: float | None = Field(default=None, ge=0, le=100)
    risk_score: float | None = Field(default=None, ge=0, le=100)
    notes: str | None = None


class Rating(RatingCreate):
    id: str = Field(default_factory=lambda: uuid4().hex)
    final_score: float
    rating: AnalystRating
    allocation_action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RatingBulkCreate(BaseModel):
    ratings: list[RatingCreate]


class RatingBulkResult(BaseModel):
    count: int
    created: list[Rating]


class RatingImportRow(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    technical_score: float = Field(..., ge=0, le=100)
    fundamental_score: float = Field(..., ge=0, le=100)
    risk_score: float = Field(..., ge=0, le=100)
    asset_type: AssetType | None = None
    notes: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class RatingImportPayload(BaseModel):
    rows: list[RatingImportRow]
    replace_latest_for_symbol: bool = True
    default_asset_type: AssetType = "stock"


class RatingImportResult(BaseModel):
    imported_count: int
    skipped_count: int
    replaced_symbol_count: int
    missing_symbol_count: int
    imported_symbols: list[str]
    skipped_symbols: list[str]
    missing_symbols: list[str]


class RatingWorkflowItem(BaseModel):
    symbol: str
    asset_type: AssetType
    broker: Broker
    reserve_for: ReserveFor | None
    sector: str | None
    quantity: float
    average_price: float
    invested_value: float
    current_value: float
    portfolio_weight_percent: float
    latest_rating: Rating | None
    rating_required: bool
    rating_template: RatingDraft


class RatingWorkflow(BaseModel):
    total_holdings: int
    rated_count: int
    unrated_count: int
    rating_coverage_percent: float
    next_unrated_symbols: list[str]
    items: list[RatingWorkflowItem]


class RatingSummary(BaseModel):
    ratings: list[Rating]
    average_final_score: float
    strongest_rating: Rating | None
    weakest_rating: Rating | None
    buy_count: int
    hold_count: int
    reduce_or_avoid_count: int


