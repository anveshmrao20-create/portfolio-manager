import math
from pathlib import Path

import pandas as pd
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.orm import Session
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD

from backend.app.database.models import HoldingRecord
from backend.app.models.technical import TechnicalSignalItem, TechnicalSnapshot

PROJECT_ROOT = Path(__file__).resolve().parents[3]
YF_CACHE_DIR = PROJECT_ROOT / "data" / "yf_cache"
YF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
yf.set_tz_cache_location(str(YF_CACHE_DIR))


def get_technical_snapshot(db: Session, lookback_days: int = 365) -> TechnicalSnapshot:
    holdings = (
        db.execute(select(HoldingRecord).where(HoldingRecord.is_cash_reserve == False))  # noqa: E712
        .scalars()
        .all()
    )
    symbols = sorted({holding.symbol for holding in holdings})
    items: list[TechnicalSignalItem] = []
    failed: list[str] = []

    for symbol in symbols:
        meta = next(holding for holding in holdings if holding.symbol == symbol)
        try:
            item = _build_symbol_signal(symbol, meta.asset_type, meta.broker, lookback_days)
            items.append(item)
        except Exception:
            failed.append(symbol)

    return TechnicalSnapshot(
        total_symbols=len(symbols),
        generated_items=len(items),
        failed_symbols=failed,
        items=sorted(items, key=lambda item: (item.trend_strength, item.momentum_status, item.symbol), reverse=True),
    )


def _build_symbol_signal(symbol: str, asset_type: str, broker: str, lookback_days: int) -> TechnicalSignalItem:
    ticker = _to_nse_ticker(symbol)
    history = yf.download(
        tickers=ticker,
        period=f"{lookback_days}d",
        interval="1d",
        progress=False,
        auto_adjust=False,
        threads=False,
    )
    if history is None or history.empty:
        raise ValueError(f"No history for {symbol}")

    if isinstance(history.columns, pd.MultiIndex):
        history.columns = history.columns.get_level_values(0)

    close_series = pd.Series(history["Close"], dtype="float64")
    volume_series = pd.Series(history["Volume"], dtype="float64")

    rsi_14 = RSIIndicator(close=close_series, window=14).rsi()
    ema_20 = EMAIndicator(close=close_series, window=20).ema_indicator()
    ema_50 = EMAIndicator(close=close_series, window=50).ema_indicator()
    ema_200 = EMAIndicator(close=close_series, window=200).ema_indicator()
    macd_calc = MACD(close=close_series, window_slow=26, window_fast=12, window_sign=9)
    macd_line = macd_calc.macd()
    macd_signal = macd_calc.macd_signal()
    macd_hist = macd_calc.macd_diff()
    volume_sma_20 = volume_series.rolling(window=20).mean()

    close = _safe_float(close_series.iloc[-1])
    ema_20_v = _safe_float(ema_20.iloc[-1])
    ema_50_v = _safe_float(ema_50.iloc[-1])
    ema_200_v = _safe_float(ema_200.iloc[-1])
    rsi_v = _safe_float(rsi_14.iloc[-1])
    macd_v = _safe_float(macd_line.iloc[-1])
    macd_signal_v = _safe_float(macd_signal.iloc[-1])
    macd_hist_v = _safe_float(macd_hist.iloc[-1])
    volume_v = _safe_float(volume_series.iloc[-1])
    volume_sma_v = _safe_float(volume_sma_20.iloc[-1])

    rolling_high = close_series.tail(252).max()
    dip_52w = _pct((close - rolling_high), rolling_high) if close is not None else None
    dist_200 = _pct((close - ema_200_v), ema_200_v) if close is not None and ema_200_v else None

    trend_strength = _trend_strength(close, ema_20_v, ema_50_v, ema_200_v)
    momentum_status = _momentum_status(rsi_v, macd_v, macd_signal_v, macd_hist_v)

    return TechnicalSignalItem(
        symbol=symbol,
        asset_type=asset_type,
        broker=broker,
        close=close,
        rsi_14=rsi_v,
        ema_20=ema_20_v,
        ema_50=ema_50_v,
        ema_200=ema_200_v,
        macd=macd_v,
        macd_signal=macd_signal_v,
        macd_histogram=macd_hist_v,
        volume=volume_v,
        volume_sma_20=volume_sma_v,
        trend_strength=trend_strength,
        momentum_status=momentum_status,
        dip_from_52w_high_percent=dip_52w,
        distance_from_200ema_percent=dist_200,
    )


def _to_nse_ticker(symbol: str) -> str:
    return symbol if "." in symbol else f"{symbol}.NS"


def _safe_float(value: object) -> float | None:
    try:
        v = float(value)
    except Exception:
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return round(v, 2)


def _pct(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100, 2)


def _trend_strength(close: float | None, ema_20: float | None, ema_50: float | None, ema_200: float | None) -> str:
    if close is None or ema_20 is None or ema_50 is None or ema_200 is None:
        return "unknown"
    if close > ema_20 > ema_50 > ema_200:
        return "strong_uptrend"
    if close > ema_50 > ema_200:
        return "uptrend"
    if close < ema_20 < ema_50 < ema_200:
        return "strong_downtrend"
    if close < ema_50 < ema_200:
        return "downtrend"
    return "sideways"


def _momentum_status(
    rsi: float | None,
    macd: float | None,
    macd_signal: float | None,
    macd_hist: float | None,
) -> str:
    if rsi is None or macd is None or macd_signal is None or macd_hist is None:
        return "unknown"
    if rsi >= 60 and macd > macd_signal and macd_hist > 0:
        return "bullish"
    if rsi <= 40 and macd < macd_signal and macd_hist < 0:
        return "bearish"
    return "neutral"
