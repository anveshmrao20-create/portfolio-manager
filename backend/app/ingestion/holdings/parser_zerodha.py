import pandas as pd

from backend.app.ingestion.holdings.normalizer import ParsedHoldingRow, normalize_symbol, to_float


def parse_zerodha_csv(file_path: str) -> tuple[list[ParsedHoldingRow], list[tuple[int, str]]]:
    df = pd.read_csv(file_path)
    records: list[ParsedHoldingRow] = []
    errors: list[tuple[int, str]] = []

    for idx, row in df.iterrows():
        row_num = idx + 2
        symbol = normalize_symbol(row.get("Instrument", ""))
        quantity = to_float(row.get("Qty."))
        average_price = to_float(row.get("Avg. cost"))
        buy_value = to_float(row.get("Invested"))
        closing_price = to_float(row.get("LTP"))
        closing_value = to_float(row.get("Cur. val"))
        unrealised_pnl = to_float(row.get("P&L"))

        if not symbol:
            errors.append((row_num, "Missing instrument symbol"))
            continue
        if quantity is None or quantity <= 0:
            errors.append((row_num, f"Invalid quantity for symbol {symbol}"))
            continue
        if average_price is None or average_price < 0:
            errors.append((row_num, f"Invalid average price for symbol {symbol}"))
            continue

        computed_buy_value = buy_value if buy_value is not None else quantity * average_price
        records.append(
            ParsedHoldingRow(
                row_number=row_num,
                symbol=symbol,
                name=symbol,
                isin=None,
                quantity=quantity,
                average_price=average_price,
                buy_value=computed_buy_value,
                closing_price=closing_price,
                closing_value=closing_value,
                unrealised_pnl=unrealised_pnl,
            )
        )
    return records, errors
