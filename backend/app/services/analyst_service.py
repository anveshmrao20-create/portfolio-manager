from backend.app.models.analyst import PortfolioAnalystVerdict, RatedHolding, SectorExposure
from backend.app.models.portfolio import Holding
from backend.app.models.rating import Rating
from backend.app.services import portfolio_service, rating_service, settings_service


def get_portfolio_verdict() -> PortfolioAnalystVerdict:
    portfolio_summary = portfolio_service.get_summary()
    goal_verdict = settings_service.get_goal_verdict()
    ratings_by_symbol = _latest_ratings_by_symbol()
    holdings = portfolio_summary.holdings
    total_value = portfolio_summary.current_value

    rated_holdings = [
        _build_rated_holding(holding, ratings_by_symbol.get(holding.symbol), total_value)
        for holding in holdings
    ]
    rating_eligible_holdings = [holding for holding in rated_holdings if not holding.is_cash_reserve]
    rated_count = sum(1 for holding in rating_eligible_holdings if holding.rating is not None)
    holdings_count = len(rated_holdings)
    rating_eligible_count = len(rating_eligible_holdings)
    rating_coverage = (rated_count / rating_eligible_count * 100) if rating_eligible_count else 0
    unrated_symbols = [holding.symbol for holding in rating_eligible_holdings if holding.rating is None]
    sector_exposure = _build_sector_exposure(holdings, total_value)
    top_position = _top_position(rated_holdings)

    key_findings = _key_findings(
        holdings_count=holdings_count,
        rated_count=rated_count,
        rating_coverage=rating_coverage,
        top_position=top_position,
        sector_exposure=sector_exposure,
        goal_status=goal_verdict.status,
    )
    warnings = _warnings(
        holdings_count=holdings_count,
        rating_coverage=rating_coverage,
        top_position=top_position,
        sector_exposure=sector_exposure,
        rated_holdings=rated_holdings,
    )
    recommended_actions = _recommended_actions(
        holdings_count=holdings_count,
        rating_coverage=rating_coverage,
        unrated_symbols=unrated_symbols,
        rated_holdings=rated_holdings,
        goal_actions=goal_verdict.recommended_actions,
    )
    status = _overall_status(
        holdings_count=holdings_count,
        rating_coverage=rating_coverage,
        rated_holdings=rated_holdings,
        goal_status=goal_verdict.status,
    )
    headline, verdict = _headline_and_verdict(status)

    return PortfolioAnalystVerdict(
        status=status,
        headline=headline,
        verdict=verdict,
        portfolio_value=total_value,
        holdings_count=holdings_count,
        rated_count=rated_count,
        rating_coverage_percent=round(rating_coverage, 2),
        unrated_symbols=unrated_symbols,
        top_position=top_position,
        holdings=rated_holdings,
        sector_exposure=sector_exposure,
        key_findings=key_findings,
        recommended_actions=recommended_actions,
        warnings=warnings,
        goal_verdict=goal_verdict,
    )


def _latest_ratings_by_symbol() -> dict[str, Rating]:
    ratings_by_symbol: dict[str, Rating] = {}
    for rating in sorted(rating_service.list_ratings(), key=lambda item: item.created_at):
        ratings_by_symbol[rating.symbol] = rating
    return ratings_by_symbol


def _build_rated_holding(holding: Holding, rating: Rating | None, total_value: float) -> RatedHolding:
    invested_value = portfolio_service.get_holding_invested_value(holding)
    current_value = portfolio_service.get_holding_current_value(holding)
    weight = (current_value / total_value * 100) if total_value else 0
    unrealised_pnl = holding.unrealised_pnl
    if unrealised_pnl is None:
        unrealised_pnl = current_value - invested_value
    return RatedHolding(
        symbol=holding.symbol,
        name=holding.name,
        isin=holding.isin,
        asset_type=holding.asset_type,
        sector=holding.sector,
        quantity=holding.quantity,
        average_price=holding.average_price,
        closing_price=holding.closing_price,
        invested_value=round(invested_value, 2),
        current_value=round(current_value, 2),
        unrealised_pnl=round(unrealised_pnl, 2),
        portfolio_weight_percent=round(weight, 2),
        is_cash_reserve=holding.is_cash_reserve,
        rating=rating,
        action=_holding_action(holding, rating),
    )


def _holding_action(holding: Holding, rating: Rating | None) -> str:
    if holding.is_cash_reserve:
        return "Treat as dip-buy cash reserve. Do not rate as an equity compounding position."
    if rating is None:
        return "No rating yet. Do not allocate fresh capital until technical, fundamental, and risk scores are loaded."
    return rating.allocation_action


def _build_sector_exposure(holdings: list[Holding], total_value: float) -> list[SectorExposure]:
    exposure: dict[str, dict[str, float | int]] = {}
    for holding in holdings:
        sector = holding.sector or "Unclassified"
        current_value = portfolio_service.get_holding_current_value(holding)
        if sector not in exposure:
            exposure[sector] = {"current_value": 0.0, "holdings_count": 0}
        exposure[sector]["current_value"] += current_value
        exposure[sector]["holdings_count"] += 1

    sectors = []
    for sector, data in exposure.items():
        current_value = float(data["current_value"])
        weight = (current_value / total_value * 100) if total_value else 0
        sectors.append(
            SectorExposure(
                sector=sector,
                current_value=round(current_value, 2),
                portfolio_weight_percent=round(weight, 2),
                holdings_count=int(data["holdings_count"]),
            )
        )
    return sorted(sectors, key=lambda item: item.portfolio_weight_percent, reverse=True)


def _top_position(holdings: list[RatedHolding]) -> RatedHolding | None:
    equity_holdings = [holding for holding in holdings if not holding.is_cash_reserve]
    if not equity_holdings:
        return None
    return sorted(equity_holdings, key=lambda holding: holding.portfolio_weight_percent, reverse=True)[0]


def _key_findings(
    holdings_count: int,
    rated_count: int,
    rating_coverage: float,
    top_position: RatedHolding | None,
    sector_exposure: list[SectorExposure],
    goal_status: str,
) -> list[str]:
    findings = [
        f"Portfolio has {holdings_count} holdings, with {rated_count} rated by the analyst engine.",
        f"Rating coverage is {rating_coverage:.0f}%.",
        f"Goal engine status is {goal_status}.",
    ]
    if top_position is not None:
        findings.append(
            f"Largest equity position is {top_position.symbol} at {top_position.portfolio_weight_percent:.1f}% of current portfolio value."
        )
    if sector_exposure:
        top_sector = sector_exposure[0]
        findings.append(
            f"Largest sector exposure is {top_sector.sector} at {top_sector.portfolio_weight_percent:.1f}%."
        )
    return findings


def _warnings(
    holdings_count: int,
    rating_coverage: float,
    top_position: RatedHolding | None,
    sector_exposure: list[SectorExposure],
    rated_holdings: list[RatedHolding],
) -> list[str]:
    warnings = [
        "Portfolio values use Zerodha statement closing values; live market refresh is not connected yet.",
        "Ratings are manually supplied until your technical and fundamental scripts are connected.",
    ]
    if holdings_count == 0:
        warnings.append("No holdings are loaded. Analyst verdict is incomplete.")
    if 0 < rating_coverage < 100:
        warnings.append("Some holdings are unrated, so portfolio verdict confidence is limited.")
    if top_position is not None and top_position.portfolio_weight_percent > 25:
        warnings.append(
            f"{top_position.symbol} is above 25% of current portfolio value. Concentration risk is high."
        )
    if sector_exposure and sector_exposure[0].portfolio_weight_percent > 40:
        warnings.append(
            f"{sector_exposure[0].sector} exposure is above 40%. Sector concentration needs review."
        )
    weak_symbols = [
        holding.symbol
        for holding in rated_holdings
        if holding.rating is not None and holding.rating.rating in {"reduce", "avoid"}
    ]
    if weak_symbols:
        warnings.append(f"Weak-rated holdings found: {', '.join(weak_symbols)}.")
    return warnings


def _recommended_actions(
    holdings_count: int,
    rating_coverage: float,
    unrated_symbols: list[str],
    rated_holdings: list[RatedHolding],
    goal_actions: list[str],
) -> list[str]:
    actions = []
    if holdings_count == 0:
        actions.append("Add your actual portfolio holdings before using the verdict for decisions.")
    if unrated_symbols:
        actions.append(f"Rate these holdings next: {', '.join(unrated_symbols)}.")
    if rating_coverage == 100:
        actions.append("Use only strong_buy and buy names for SIP or buy-the-dip candidates.")

    reduce_symbols = [
        holding.symbol
        for holding in rated_holdings
        if holding.rating is not None and holding.rating.rating in {"reduce", "avoid"}
    ]
    if reduce_symbols:
        actions.append(f"Review exit or reduction plan for: {', '.join(reduce_symbols)}.")

    for action in goal_actions:
        if action not in actions:
            actions.append(action)
    return actions


def _overall_status(
    holdings_count: int,
    rating_coverage: float,
    rated_holdings: list[RatedHolding],
    goal_status: str,
) -> str:
    if holdings_count == 0:
        return "no_data"
    weak_count = sum(
        1
        for holding in rated_holdings
        if holding.rating is not None and holding.rating.rating in {"reduce", "avoid"}
    )
    if goal_status == "off_track" or weak_count > 0 or rating_coverage < 60:
        return "needs_action"
    if goal_status == "needs_attention" or rating_coverage < 100:
        return "watchlist"
    return "healthy"


def _headline_and_verdict(status: str) -> tuple[str, str]:
    if status == "healthy":
        return (
            "Portfolio operating picture is healthy.",
            "The goal plan and rating coverage are acceptable. Now the focus should be execution discipline and avoiding emotional overtrading.",
        )
    if status == "watchlist":
        return (
            "Portfolio is usable, but not fully decision-ready.",
            "The structure is improving, but you still have open monitoring gaps. Close those before relying on the system for allocation calls.",
        )
    if status == "needs_action":
        return (
            "Portfolio needs action before serious allocation decisions.",
            "Brutal view: there is not enough confirmed quality or goal alignment yet. Fix ratings, weak names, and SIP math before scaling capital.",
        )
    return (
        "Portfolio verdict is not available yet.",
        "You need to add holdings first. Without holdings, the analyst engine can only discuss goals, not portfolio quality.",
    )

