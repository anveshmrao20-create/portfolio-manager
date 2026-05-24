from backend.app.ingestion.holdings.normalizer import is_cash_reserve, normalize_symbol


def test_normalize_symbol_removes_special_chars() -> None:
    assert normalize_symbol(" cpseetf.ns ") == "CPSEETFNS"


def test_cash_reserve_keyword_match() -> None:
    assert is_cash_reserve("LIQUIDBEES", "Nippon Liquid Bees") is True
    assert is_cash_reserve("CPSEETF", "CPSE ETF") is False
