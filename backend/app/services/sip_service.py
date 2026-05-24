from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.models import HoldingRecord
from backend.app.models.sip import (
    DipOpportunity,
    ReserveCashPlan,
    SipDipSnapshot,
    SipPick,
)
from backend.app.services.fundamental_service import get_fundamental_snapshot
from backend.app.services.technical_service import get_technical_snapshot


def get_sip_dip_snapshot(
    db: Session,
    stock_monthly_budget: float = 25000,
    etf_weekly_budget: float = 15000,
    reserve_ratio_target: float = 20.0,
) -> SipDipSnapshot:
    technical = get_technical_snapshot(db=db, lookback_days=365)
    fundamentals = get_fundamental_snapshot(db=db)
    fund_map = {item.symbol: item for item in fundamentals.items}
    tech_map = {item.symbol: item for item in technical.items}

    holdings = db.execute(select(HoldingRecord)).scalars().all()
    total_value = sum(_holding_value(h) for h in holdings)
    reserve_value = sum(_holding_value(h) for h in holdings if h.is_cash_reserve)
    reserve_ratio = (reserve_value / total_value * 100) if total_value else 0.0

    stock_candidates: list[tuple[str, str, float, str]] = []
    etf_candidates: list[tuple[str, str, float, str]] = []
    dip_candidates: list[DipOpportunity] = []

    for symbol, tech in tech_map.items():
        fund = fund_map.get(symbol)
        if fund is None:
            continue

        tech_score = _technical_score(tech.trend_strength, tech.momentum_status, tech.rsi_14)
        combined = round((fund.score * 0.55) + (tech_score * 0.45), 2)
        reason = f"F:{fund.score} T:{tech_score:.1f} Trend:{tech.trend_strength} Momentum:{tech.momentum_status}"

        if tech.asset_type == "stock":
            stock_candidates.append((symbol, tech.broker, combined, reason))
        else:
            etf_candidates.append((symbol, tech.broker, combined, reason))

        dip = tech.dip_from_52w_high_percent
        if dip is not None and dip <= -10 and fund.grade != "Weak":
            conviction = "high" if combined >= 75 and dip <= -15 else "medium"
            action = "staggered_buy" if conviction == "high" else "watch_and_accumulate"
            dip_candidates.append(
                DipOpportunity(
                    symbol=symbol,
                    asset_type=tech.asset_type,
                    dip_percent=dip,
                    technical_score=round(tech_score, 2),
                    fundamental_score=fund.score,
                    conviction=conviction,
                    suggested_action=action,
                    suggested_amount=0.0,
                )
            )

    stock_picks = _build_sip_picks(stock_candidates, max_picks=5, min_picks=4, budget=stock_monthly_budget, asset_type="stock")
    etf_picks = _build_sip_picks(etf_candidates, max_picks=4, min_picks=3, budget=etf_weekly_budget, asset_type="etf")

    dip_candidates.sort(key=lambda d: (d.conviction, d.fundamental_score, d.technical_score, -(d.dip_percent or 0)), reverse=True)
    dip_selected = dip_candidates[:6]

    dip_budget = _dip_budget(reserve_value=reserve_value, reserve_ratio=reserve_ratio, reserve_target=reserve_ratio_target)
    _assign_dip_amounts(dip_selected, dip_budget)

    reserve_plan = _reserve_plan(total_value, reserve_value, reserve_ratio_target)
    notes = _build_notes(technical.failed_symbols, fundamentals.failed_symbols, reserve_plan)

    return SipDipSnapshot(
        stock_monthly_picks=stock_picks,
        etf_weekly_picks=etf_picks,
        dip_opportunities=dip_selected,
        reserve_cash_plan=reserve_plan,
        notes=notes,
    )


def _holding_value(holding: HoldingRecord) -> float:
    if holding.closing_value is not None and holding.closing_value > 0:
        return float(holding.closing_value)
    return float(holding.buy_value)


def _technical_score(trend: str, momentum: str, rsi: float | None) -> float:
    score = 50.0
    score += {"strong_uptrend": 20, "uptrend": 12, "sideways": 0, "downtrend": -10, "strong_downtrend": -18}.get(trend, 0)
    score += {"bullish": 15, "neutral": 0, "bearish": -12}.get(momentum, 0)
    if rsi is not None:
        if 45 <= rsi <= 65:
            score += 8
        elif rsi < 35:
            score -= 8
        elif rsi > 75:
            score -= 6
    return max(0.0, min(100.0, score))


def _build_sip_picks(
    candidates: list[tuple[str, str, float, str]],
    max_picks: int,
    min_picks: int,
    budget: float,
    asset_type: str,
) -> list[SipPick]:
    ordered = sorted(candidates, key=lambda x: x[2], reverse=True)
    picks = ordered[:max_picks]
    if len(picks) < min_picks:
        picks = ordered[:min(len(ordered), min_picks)]
    if not picks:
        return []

    total_score = sum(max(1.0, pick[2]) for pick in picks)
    result: list[SipPick] = []
    for symbol, broker, score, reason in picks:
        amount = round((max(1.0, score) / total_score) * budget, 2)
        result.append(
            SipPick(
                symbol=symbol,
                asset_type=asset_type,
                broker=broker,
                combined_score=round(score, 2),
                suggested_amount=amount,
                reason=reason,
            )
        )
    return result


def _dip_budget(reserve_value: float, reserve_ratio: float, reserve_target: float) -> float:
    if reserve_ratio <= reserve_target:
        return 0.0
    excess = reserve_value * ((reserve_ratio - reserve_target) / max(reserve_ratio, 0.0001))
    return round(excess * 0.5, 2)


def _assign_dip_amounts(items: list[DipOpportunity], budget: float) -> None:
    if not items or budget <= 0:
        return
    weights = []
    for item in items:
        weight = (item.fundamental_score * 0.6) + (item.technical_score * 0.4) + abs(item.dip_percent or 0)
        weights.append(max(1.0, weight))
    denom = sum(weights)
    for idx, item in enumerate(items):
        item.suggested_amount = round((weights[idx] / denom) * budget, 2)


def _reserve_plan(total: float, reserve: float, target_ratio: float) -> ReserveCashPlan:
    target_value = round(total * (target_ratio / 100), 2) if total else 0.0
    gap = round(target_value - reserve, 2)
    ratio = round((reserve / total) * 100, 2) if total else 0.0
    return ReserveCashPlan(
        current_reserve_value=round(reserve, 2),
        target_reserve_value=target_value,
        reserve_gap_value=gap,
        reserve_ratio_percent=ratio,
        recommended_ratio_percent=target_ratio,
    )


def _build_notes(tech_failed: list[str], fund_failed: list[str], reserve_plan: ReserveCashPlan) -> list[str]:
    notes = [
        "SIP picks are ranked by combined technical and fundamental quality, not by recent hype.",
        "Dip engine only surfaces names with non-weak fundamentals and meaningful correction depth.",
    ]
    if reserve_plan.reserve_ratio_percent < reserve_plan.recommended_ratio_percent:
        notes.append("Reserve cash is below target; prioritize replenishing cash buffer before aggressive dip deployment.")
    if tech_failed:
        notes.append(f"Technical data unavailable for: {', '.join(tech_failed[:5])}.")
    if fund_failed:
        notes.append(f"Fundamental data unavailable for: {', '.join(fund_failed[:5])}.")
    return notes
