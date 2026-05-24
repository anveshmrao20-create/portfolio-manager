import json
from pathlib import Path

from backend.app.models.portfolio import AccountSummary, Holding, HoldingCreate, PortfolioSummary


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
HOLDINGS_FILE = DATA_DIR / "portfolio_holdings.json"


def _ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not HOLDINGS_FILE.exists():
        HOLDINGS_FILE.write_text("[]", encoding="utf-8")


def _read_raw_holdings() -> list[dict]:
    _ensure_storage()
    return json.loads(HOLDINGS_FILE.read_text(encoding="utf-8-sig"))


def _write_holdings(holdings: list[Holding]) -> None:
    _ensure_storage()
    payload = [holding.model_dump(mode="json") for holding in holdings]
    HOLDINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def list_holdings() -> list[Holding]:
    return [Holding(**item) for item in _read_raw_holdings()]


def add_holding(payload: HoldingCreate) -> Holding:
    holdings = list_holdings()
    holding = Holding(**payload.model_dump())
    holdings.append(holding)
    _write_holdings(holdings)
    return holding


def replace_holdings(payloads: list[HoldingCreate]) -> list[Holding]:
    holdings = [Holding(**payload.model_dump()) for payload in payloads]
    _write_holdings(holdings)
    return holdings


def delete_holding(holding_id: str) -> bool:
    holdings = list_holdings()
    remaining = [holding for holding in holdings if holding.id != holding_id]
    if len(remaining) == len(holdings):
        return False
    _write_holdings(remaining)
    return True


def get_holding_invested_value(holding: Holding) -> float:
    if holding.buy_value is not None:
        return holding.buy_value
    return holding.quantity * holding.average_price


def get_holding_current_value(holding: Holding) -> float:
    if holding.closing_value is not None:
        return holding.closing_value
    if holding.closing_price is not None:
        return holding.quantity * holding.closing_price
    return get_holding_invested_value(holding)


def get_summary() -> PortfolioSummary:
    holdings = list_holdings()
    total_invested = sum(get_holding_invested_value(holding) for holding in holdings)
    current_value = sum(get_holding_current_value(holding) for holding in holdings)
    cash_reserve_value = sum(
        get_holding_current_value(holding) for holding in holdings if holding.is_cash_reserve
    )
    equity_value = current_value - cash_reserve_value
    unrealised_pnl = sum(
        holding.unrealised_pnl
        if holding.unrealised_pnl is not None
        else get_holding_current_value(holding) - get_holding_invested_value(holding)
        for holding in holdings
    )
    stock_count = sum(1 for holding in holdings if holding.asset_type == "stock")
    etf_count = sum(1 for holding in holdings if holding.asset_type == "etf")
    cash_reserve_count = sum(1 for holding in holdings if holding.is_cash_reserve)
    return PortfolioSummary(
        holdings=holdings,
        total_invested=round(total_invested, 2),
        current_value=round(current_value, 2),
        equity_value=round(equity_value, 2),
        cash_reserve_value=round(cash_reserve_value, 2),
        unrealised_pnl=round(unrealised_pnl, 2),
        stock_count=stock_count,
        etf_count=etf_count,
        cash_reserve_count=cash_reserve_count,
        by_account=_account_breakdown(holdings),
    )


def _account_breakdown(holdings: list[Holding]) -> list[AccountSummary]:
    rows: dict[str, dict[str, float]] = {}
    for holding in holdings:
        broker = holding.broker
        if broker not in rows:
            rows[broker] = {
                "current_value": 0.0,
                "equity_value": 0.0,
                "cash_reserve_value": 0.0,
                "stock_value": 0.0,
                "etf_value": 0.0,
                "stock_cash_reserve_value": 0.0,
                "etf_cash_reserve_value": 0.0,
            }

        current = get_holding_current_value(holding)
        rows[broker]["current_value"] += current
        if holding.asset_type == "stock":
            rows[broker]["stock_value"] += current
        else:
            rows[broker]["etf_value"] += current

        if holding.is_cash_reserve:
            rows[broker]["cash_reserve_value"] += current
            if holding.reserve_for == "stock":
                rows[broker]["stock_cash_reserve_value"] += current
            elif holding.reserve_for == "etf":
                rows[broker]["etf_cash_reserve_value"] += current
        else:
            rows[broker]["equity_value"] += current

    return [
        AccountSummary(
            broker=broker,  # type: ignore[arg-type]
            current_value=round(data["current_value"], 2),
            equity_value=round(data["equity_value"], 2),
            cash_reserve_value=round(data["cash_reserve_value"], 2),
            stock_value=round(data["stock_value"], 2),
            etf_value=round(data["etf_value"], 2),
            stock_cash_reserve_value=round(data["stock_cash_reserve_value"], 2),
            etf_cash_reserve_value=round(data["etf_cash_reserve_value"], 2),
        )
        for broker, data in rows.items()
    ]
