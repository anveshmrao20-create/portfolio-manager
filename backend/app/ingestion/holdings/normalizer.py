from dataclasses import dataclass
import math
import re


CASH_KEYWORDS = ("LIQUID", "LIQ", "MONEY MARKET", "OVERNIGHT", "TREASURY")
SYMBOL_CLEAN_RE = re.compile(r"[^A-Z0-9]")


@dataclass
class ParsedHoldingRow:
    row_number: int
    symbol: str
    name: str | None
    isin: str | None
    quantity: float
    average_price: float
    buy_value: float
    closing_price: float | None
    closing_value: float | None
    unrealised_pnl: float | None


def normalize_symbol(raw_value: str) -> str:
    cleaned = SYMBOL_CLEAN_RE.sub("", str(raw_value).upper())
    return cleaned.strip()


def to_float(value: object, default: float | None = None) -> float | None:
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    text = str(value).replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def is_cash_reserve(symbol: str, name: str | None) -> bool:
    hay = f"{symbol} {name or ''}".upper()
    return any(keyword in hay for keyword in CASH_KEYWORDS)
