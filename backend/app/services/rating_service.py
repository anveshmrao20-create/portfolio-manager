import json
from pathlib import Path

from backend.app.models.rating import (
    Rating,
    RatingBulkCreate,
    RatingBulkResult,
    RatingCreate,
    RatingDraft,
    RatingImportPayload,
    RatingImportResult,
    RatingSummary,
    RatingWorkflow,
    RatingWorkflowItem,
)
from backend.app.services import portfolio_service


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
RATINGS_FILE = DATA_DIR / "ratings.json"


def _ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not RATINGS_FILE.exists():
        RATINGS_FILE.write_text("[]", encoding="utf-8")


def _read_raw_ratings() -> list[dict]:
    _ensure_storage()
    return json.loads(RATINGS_FILE.read_text(encoding="utf-8-sig"))


def _write_ratings(ratings: list[Rating]) -> None:
    _ensure_storage()
    payload = [rating.model_dump(mode="json") for rating in ratings]
    RATINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def list_ratings() -> list[Rating]:
    return [Rating(**item) for item in _read_raw_ratings()]


def get_rating_by_symbol(symbol: str) -> Rating | None:
    normalized = symbol.strip().upper()
    ratings = [rating for rating in list_ratings() if rating.symbol == normalized]
    if not ratings:
        return None
    return sorted(ratings, key=lambda rating: rating.created_at, reverse=True)[0]


def add_rating(payload: RatingCreate) -> Rating:
    ratings = list_ratings()
    rating = _build_rating(payload)
    ratings.append(rating)
    _write_ratings(ratings)
    return rating


def add_bulk_ratings(payload: RatingBulkCreate) -> RatingBulkResult:
    existing = list_ratings()
    created = [_build_rating(item) for item in payload.ratings]
    _write_ratings(existing + created)
    return RatingBulkResult(count=len(created), created=created)


def import_ratings(payload: RatingImportPayload) -> RatingImportResult:
    holdings = portfolio_service.list_holdings()
    holding_symbols = {holding.symbol for holding in holdings if not holding.is_cash_reserve}
    existing = list_ratings()

    imported: list[Rating] = []
    skipped_symbols: list[str] = []
    missing_symbols: list[str] = []
    seen_symbols: set[str] = set()

    for row in payload.rows:
        symbol = row.symbol.strip().upper()
        if symbol in seen_symbols:
            skipped_symbols.append(symbol)
            continue
        seen_symbols.add(symbol)

        if symbol not in holding_symbols:
            missing_symbols.append(symbol)
            continue

        rating_create = RatingCreate(
            symbol=symbol,
            asset_type=row.asset_type or payload.default_asset_type,
            technical_score=row.technical_score,
            fundamental_score=row.fundamental_score,
            risk_score=row.risk_score,
            notes=row.notes or "Imported from script output.",
        )
        imported.append(_build_rating(rating_create))

    replaced_symbols: set[str] = set()
    if payload.replace_latest_for_symbol and imported:
        imported_symbols_set = {item.symbol for item in imported}
        replaced_symbols = imported_symbols_set
        existing = [item for item in existing if item.symbol not in imported_symbols_set]

    _write_ratings(existing + imported)
    return RatingImportResult(
        imported_count=len(imported),
        skipped_count=len(skipped_symbols),
        replaced_symbol_count=len(replaced_symbols),
        missing_symbol_count=len(missing_symbols),
        imported_symbols=[item.symbol for item in imported],
        skipped_symbols=skipped_symbols,
        missing_symbols=missing_symbols,
    )


def delete_rating(rating_id: str) -> bool:
    ratings = list_ratings()
    remaining = [rating for rating in ratings if rating.id != rating_id]
    if len(remaining) == len(ratings):
        return False
    _write_ratings(remaining)
    return True


def get_rating_summary() -> RatingSummary:
    ratings = list_ratings()
    if not ratings:
        return RatingSummary(
            ratings=[],
            average_final_score=0,
            strongest_rating=None,
            weakest_rating=None,
            buy_count=0,
            hold_count=0,
            reduce_or_avoid_count=0,
        )

    sorted_by_score = sorted(ratings, key=lambda rating: rating.final_score, reverse=True)
    buy_count = sum(1 for rating in ratings if rating.rating in {"strong_buy", "buy"})
    hold_count = sum(1 for rating in ratings if rating.rating == "hold")
    reduce_or_avoid_count = sum(1 for rating in ratings if rating.rating in {"reduce", "avoid"})
    average_score = sum(rating.final_score for rating in ratings) / len(ratings)

    return RatingSummary(
        ratings=ratings,
        average_final_score=round(average_score, 2),
        strongest_rating=sorted_by_score[0],
        weakest_rating=sorted_by_score[-1],
        buy_count=buy_count,
        hold_count=hold_count,
        reduce_or_avoid_count=reduce_or_avoid_count,
    )


def get_rating_workflow() -> RatingWorkflow:
    holdings = portfolio_service.list_holdings()
    total_value = sum(portfolio_service.get_holding_current_value(holding) for holding in holdings)
    latest_ratings = _latest_ratings_by_symbol()

    items = []
    for holding in holdings:
        invested_value = portfolio_service.get_holding_invested_value(holding)
        current_value = portfolio_service.get_holding_current_value(holding)
        weight = (current_value / total_value * 100) if total_value else 0
        latest_rating = latest_ratings.get(holding.symbol)
        items.append(
            RatingWorkflowItem(
                symbol=holding.symbol,
                asset_type=holding.asset_type,
                broker=holding.broker,
                reserve_for=holding.reserve_for,
                sector=holding.sector,
                quantity=holding.quantity,
                average_price=holding.average_price,
                invested_value=round(invested_value, 2),
                current_value=round(current_value, 2),
                portfolio_weight_percent=round(weight, 2),
                latest_rating=latest_rating,
                rating_required=not holding.is_cash_reserve,
                rating_template=RatingDraft(
                    symbol=holding.symbol,
                    asset_type=holding.asset_type,
                    notes=f"Initial analyst score for {holding.symbol}",
                ),
            )
        )

    rating_required_count = sum(1 for item in items if item.rating_required)
    rated_count = sum(1 for item in items if item.rating_required and item.latest_rating is not None)
    total_holdings = len(items)
    unrated_symbols = [item.symbol for item in items if item.rating_required and item.latest_rating is None]
    rating_coverage = (rated_count / rating_required_count * 100) if rating_required_count else 0

    return RatingWorkflow(
        total_holdings=total_holdings,
        rated_count=rated_count,
        unrated_count=rating_required_count - rated_count,
        rating_coverage_percent=round(rating_coverage, 2),
        next_unrated_symbols=unrated_symbols,
        items=items,
    )


def _latest_ratings_by_symbol() -> dict[str, Rating]:
    latest: dict[str, Rating] = {}
    for rating in sorted(list_ratings(), key=lambda item: item.created_at):
        latest[rating.symbol] = rating
    return latest


def _build_rating(payload: RatingCreate) -> Rating:
    final_score = _calculate_final_score(payload)
    return Rating(
        **payload.model_dump(),
        final_score=final_score,
        rating=_rating_label(final_score),
        allocation_action=_allocation_action(final_score),
    )


def _calculate_final_score(payload: RatingCreate) -> float:
    if payload.asset_type == "etf":
        final_score = (
            payload.technical_score * 0.45
            + payload.fundamental_score * 0.25
            + payload.risk_score * 0.30
        )
    else:
        final_score = (
            payload.technical_score * 0.35
            + payload.fundamental_score * 0.45
            + payload.risk_score * 0.20
        )
    return round(final_score, 2)


def _rating_label(final_score: float) -> str:
    if final_score >= 80:
        return "strong_buy"
    if final_score >= 65:
        return "buy"
    if final_score >= 50:
        return "hold"
    if final_score >= 35:
        return "reduce"
    return "avoid"


def _allocation_action(final_score: float) -> str:
    if final_score >= 80:
        return "Eligible for SIP and buy-the-dip allocation. Still respect valuation and position size."
    if final_score >= 65:
        return "Accumulate gradually. Use dips rather than chasing sharp rallies."
    if final_score >= 50:
        return "Hold and monitor. No aggressive fresh allocation until score improves."
    if final_score >= 35:
        return "Avoid fresh buying. Reduce exposure on strength if thesis is weakening."
    return "Avoid or exit candidate. Capital is better used elsewhere unless fresh evidence changes the thesis."



