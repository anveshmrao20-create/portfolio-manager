from pydantic import BaseModel


class TechnicalSignalItem(BaseModel):
    symbol: str
    asset_type: str
    broker: str
    close: float | None
    rsi_14: float | None
    ema_20: float | None
    ema_50: float | None
    ema_200: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    volume: float | None
    volume_sma_20: float | None
    trend_strength: str
    momentum_status: str
    dip_from_52w_high_percent: float | None
    distance_from_200ema_percent: float | None


class TechnicalSnapshot(BaseModel):
    total_symbols: int
    generated_items: int
    failed_symbols: list[str]
    items: list[TechnicalSignalItem]
