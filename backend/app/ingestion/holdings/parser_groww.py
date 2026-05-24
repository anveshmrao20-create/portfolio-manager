import pandas as pd

from backend.app.ingestion.holdings.normalizer import ParsedHoldingRow, normalize_symbol, to_float


EXPECTED_HEADERS = (
    "Stock Name",
    "ISIN",
    "Quantity",
    "Average buy price",
    "Buy value",
    "Closing price",
    "Closing value",
    "Unrealised P&L",
)

NAME_TO_SYMBOL = {
    "ASHOKA BUILDCON": "ASHOKA",
    "BHARAT ELECTRONICS": "BEL",
    "COAL INDIA": "COALINDIA",
    "HCL TECHNOLOGIES": "HCLTECH",
    "HERO MOTOCORP": "HEROMOTOCO",
    "HINDALCO": "HINDALCO",
    "HINDUSTAN AERONAUTICS": "HAL",
    "INDIAN METALS & FERRO": "IMFA",
    "KPI GREEN ENERGY": "KPIGREEN",
    "KPIT TECHNOLOGIES": "KPITTECH",
    "LT FOODS": "LTFOODS",
    "NATCO PHARMA": "NATCOPHARM",
    "NESCO": "NESCO",
    "PETRONET LNG": "PETRONET",
    "TATA MOTORS DVR": "TMCV",
    "TATA MOTORS": "TMPV",
    "ZYDUS LIFESCIENCES": "ZYDUSLIFE",
}


def _resolve_symbol(stock_name: str) -> str:
    upper_name = stock_name.upper()
    for key, symbol in NAME_TO_SYMBOL.items():
        if key in upper_name:
            return symbol
    return normalize_symbol(stock_name.split()[0] if stock_name else "")


def _find_header_row(df: pd.DataFrame) -> int:
    for idx in range(len(df)):
        cell_values = [str(x).strip() for x in df.iloc[idx].tolist()]
        if all(header in cell_values for header in EXPECTED_HEADERS):
            return idx
    raise ValueError("Could not find holdings header row in Groww file")


def parse_groww_excel(file_path: str) -> tuple[list[ParsedHoldingRow], list[tuple[int, str]]]:
    raw_df = pd.read_excel(file_path, sheet_name=0, header=None)
    header_row = _find_header_row(raw_df)
    data_df = raw_df.iloc[header_row + 1 :].copy()
    data_df.columns = [str(x).strip() for x in raw_df.iloc[header_row].tolist()]

    records: list[ParsedHoldingRow] = []
    errors: list[tuple[int, str]] = []

    for idx, row in data_df.iterrows():
        row_num = idx + 1
        stock_name = str(row.get("Stock Name", "")).strip()
        symbol = _resolve_symbol(stock_name)
        quantity = to_float(row.get("Quantity"))
        average_price = to_float(row.get("Average buy price"))
        buy_value = to_float(row.get("Buy value"))
        closing_price = to_float(row.get("Closing price"))
        closing_value = to_float(row.get("Closing value"))
        unrealised_pnl = to_float(row.get("Unrealised P&L"))
        isin = str(row.get("ISIN", "")).strip().upper() or None

        if not stock_name:
            continue
        if not symbol:
            errors.append((row_num, "Missing stock symbol"))
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
                name=stock_name,
                isin=isin,
                quantity=quantity,
                average_price=average_price,
                buy_value=computed_buy_value,
                closing_price=closing_price,
                closing_value=closing_value,
                unrealised_pnl=unrealised_pnl,
            )
        )

    return records, errors
