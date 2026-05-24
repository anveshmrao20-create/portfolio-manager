import math
from pathlib import Path

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.models import HoldingRecord
from backend.app.models.fundamental import (
    FundamentalMetrics,
    FundamentalSignalItem,
    FundamentalSnapshot,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
YF_CACHE_DIR = PROJECT_ROOT / "data" / "yf_cache"
YF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
yf.set_tz_cache_location(str(YF_CACHE_DIR))


def get_fundamental_snapshot(db: Session) -> FundamentalSnapshot:
    holdings = (
        db.execute(select(HoldingRecord).where(HoldingRecord.is_cash_reserve == False))  # noqa: E712
        .scalars()
        .all()
    )
    symbols = sorted({holding.symbol for holding in holdings})
    items: list[FundamentalSignalItem] = []
    failed: list[str] = []

    for symbol in symbols:
        meta = next(holding for holding in holdings if holding.symbol == symbol)
        try:
            item = _build_symbol_fundamental(symbol, meta.asset_type, meta.broker)
            items.append(item)
        except Exception:
            failed.append(symbol)

    return FundamentalSnapshot(
        total_symbols=len(symbols),
        generated_items=len(items),
        failed_symbols=failed,
        items=sorted(items, key=lambda i: (i.score, i.confidence_percent, i.symbol), reverse=True),
    )


def _build_symbol_fundamental(symbol: str, asset_type: str, broker: str) -> FundamentalSignalItem:
    ticker = _to_nse_ticker(symbol)
    info = yf.Ticker(ticker).info

    metrics = FundamentalMetrics(
        trailing_pe=_safe_float(info.get("trailingPE")),
        forward_pe=_safe_float(info.get("forwardPE")),
        price_to_book=_safe_float(info.get("priceToBook")),
        peg_ratio=_safe_float(info.get("pegRatio")),
        roe_percent=_ratio_to_percent(info.get("returnOnEquity")),
        debt_to_equity=_normalize_debt_to_equity(info.get("debtToEquity")),
        operating_margin_percent=_ratio_to_percent(info.get("operatingMargins")),
        profit_margin_percent=_ratio_to_percent(info.get("profitMargins")),
        revenue_growth_percent=_ratio_to_percent(info.get("revenueGrowth")),
        earnings_growth_percent=_ratio_to_percent(info.get("earningsGrowth")),
        free_cash_flow=_safe_float(info.get("freeCashflow")),
        operating_cash_flow=_safe_float(info.get("operatingCashflow")),
    )

    score, strengths, weaknesses, confidence = _score_fundamentals(metrics)
    grade = _grade(score)

    return FundamentalSignalItem(
        symbol=symbol,
        asset_type=asset_type,
        broker=broker,
        score=score,
        grade=grade,
        confidence_percent=confidence,
        metrics=metrics,
        strengths=strengths,
        weaknesses=weaknesses,
    )


def _score_fundamentals(metrics: FundamentalMetrics) -> tuple[int, list[str], list[str], float]:
    score = 50
    strengths: list[str] = []
    weaknesses: list[str] = []
    checks = 0
    available = 0

    def mark_available(v: float | None) -> bool:
        nonlocal checks, available
        checks += 1
        if v is not None:
            available += 1
            return True
        return False

    if mark_available(metrics.trailing_pe):
        if 0 < metrics.trailing_pe <= 25:
            score += 5
            strengths.append("Reasonable trailing PE")
        elif metrics.trailing_pe > 45:
            score -= 6
            weaknesses.append("Expensive trailing PE")

    if mark_available(metrics.peg_ratio):
        if 0 < metrics.peg_ratio <= 1.5:
            score += 6
            strengths.append("Healthy PEG")
        elif metrics.peg_ratio > 2.5:
            score -= 6
            weaknesses.append("Stretched PEG")

    if mark_available(metrics.price_to_book):
        if 0 < metrics.price_to_book <= 3:
            score += 4
            strengths.append("Reasonable price-to-book")
        elif metrics.price_to_book > 8:
            score -= 4
            weaknesses.append("High price-to-book")

    if mark_available(metrics.roe_percent):
        if metrics.roe_percent >= 18:
            score += 8
            strengths.append("Strong ROE")
        elif metrics.roe_percent < 10:
            score -= 7
            weaknesses.append("Weak ROE")

    if mark_available(metrics.debt_to_equity):
        if metrics.debt_to_equity <= 0.5:
            score += 8
            strengths.append("Conservative leverage")
        elif metrics.debt_to_equity > 1.5:
            score -= 10
            weaknesses.append("High leverage")

    if mark_available(metrics.operating_margin_percent):
        if metrics.operating_margin_percent >= 15:
            score += 6
            strengths.append("Healthy operating margins")
        elif metrics.operating_margin_percent < 8:
            score -= 6
            weaknesses.append("Weak operating margins")

    if mark_available(metrics.profit_margin_percent):
        if metrics.profit_margin_percent >= 10:
            score += 5
            strengths.append("Healthy net margins")
        elif metrics.profit_margin_percent < 5:
            score -= 5
            weaknesses.append("Weak net margins")

    if mark_available(metrics.revenue_growth_percent):
        if metrics.revenue_growth_percent >= 12:
            score += 6
            strengths.append("Strong revenue growth")
        elif metrics.revenue_growth_percent < 5:
            score -= 5
            weaknesses.append("Slow revenue growth")

    if mark_available(metrics.earnings_growth_percent):
        if metrics.earnings_growth_percent >= 12:
            score += 7
            strengths.append("Strong earnings growth")
        elif metrics.earnings_growth_percent < 5:
            score -= 6
            weaknesses.append("Weak earnings growth")

    if mark_available(metrics.free_cash_flow):
        if metrics.free_cash_flow > 0:
            score += 6
            strengths.append("Positive free cash flow")
        else:
            score -= 8
            weaknesses.append("Negative free cash flow")

    if mark_available(metrics.operating_cash_flow):
        if metrics.operating_cash_flow > 0:
            score += 4
            strengths.append("Positive operating cash flow")
        else:
            score -= 7
            weaknesses.append("Negative operating cash flow")

    bounded_score = max(0, min(100, int(round(score))))
    confidence = round((available / checks) * 100, 2) if checks else 0.0
    if confidence < 50:
        weaknesses.append("Low metric coverage; score confidence is limited")
    return bounded_score, strengths, weaknesses, confidence


def _grade(score: int) -> str:
    if score >= 70:
        return "Strong"
    if score >= 50:
        return "Moderate"
    return "Weak"


def _safe_float(value: object) -> float | None:
    try:
        v = float(value)
    except Exception:
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return round(v, 4)


def _ratio_to_percent(value: object) -> float | None:
    raw = _safe_float(value)
    if raw is None:
        return None
    return round(raw * 100, 2)


def _normalize_debt_to_equity(value: object) -> float | None:
    raw = _safe_float(value)
    if raw is None:
        return None
    # Yahoo frequently reports debtToEquity as percent-like values (e.g., 35 means 0.35).
    return round(raw / 100, 4) if raw > 3 else raw


def _to_nse_ticker(symbol: str) -> str:
    return symbol if "." in symbol else f"{symbol}.NS"
