# ================= CLEAN ETF HISTORICAL SCRIPT =================

import yfinance as yf
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

ETF_LIST = [
    "CPSEETF.NS","MOM100.NS","HDFCSML250.NS",
    "MON100.NS","GOLDBEES.NS","SILVERBEES.NS","JUNIORBEES.NS"
]

SPREADSHEET_NAME = "PortfolioAutomation"


def get_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)


def safe(v):
    try:
        if pd.isna(v):
            return ""
        return float(v)
    except:
        return ""


# 🔥 Wilder RSI (matches TradingView)
def compute_rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def run():

    client = get_client()
    ss = client.open(SPREADSHEET_NAME)

    try:
        sheet = ss.worksheet("ETF_Historical")
    except:
        sheet = ss.add_worksheet(title="ETF_Historical", rows=2000, cols=200)

    sheet.clear()

    etf_data = {}
    all_dates = set()

    for etf in ETF_LIST:

        print(f"Fetching {etf}...")

        # 🔥 MORE DATA (CRITICAL)
        df = yf.download(etf, period="2y", progress=False)

        if df.empty:
            continue

        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)

        if "Close" not in df.columns:
            continue

        df = df.dropna(subset=["Close"])

        # 🔥 EMA FIX (matches TradingView)
        df["EMA100"] = df["Close"].ewm(span=100, adjust=False).mean()
        df["EMA200"] = df["Close"].ewm(span=200, adjust=False).mean()

        # 🔥 RSI FIX (Wilder)
        df["RSI"] = compute_rsi(df["Close"], 14)

        # MACD (already correct, just add adjust=False)
        df["MACD"] = df["Close"].ewm(span=12, adjust=False).mean() - df["Close"].ewm(span=26, adjust=False).mean()
        df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

        df["VolMA"] = df["Volume"].rolling(20).mean()

        df.index = pd.to_datetime(df.index)

        # 🔥 NOW trim AFTER indicators
        df = df.tail(250)

        etf_data[etf] = df
        all_dates.update(df.index)

    all_dates = sorted(all_dates)

    header = ["Date"]

    for etf in ETF_LIST:
        name = etf.replace(".NS", "")
        header += [
            name, "RSI", "EMA100", "EMA200",
            "-", "-", "MACD", "Signal",
            "-", "-", "Volume", "VolMA"
        ]

    sheet.append_row(header)

    data_rows = []

    for date in all_dates:
        row = [date.strftime("%Y-%m-%d")]

        for etf in ETF_LIST:

            df = etf_data.get(etf)

            if df is None or date not in df.index:
                row += [""] * 12
                continue

            r = df.loc[date]

            row += [
                safe(r["Close"]),
                safe(r["RSI"]),
                safe(r["EMA100"]),
                safe(r["EMA200"]),
                "", "",
                safe(r["MACD"]),
                safe(r["Signal"]),
                "", "",
                safe(r["Volume"]),
                safe(r["VolMA"])
            ]

        data_rows.append(row)

    CHUNK_SIZE = 200

    for i in range(0, len(data_rows), CHUNK_SIZE):
        sheet.append_rows(data_rows[i:i+CHUNK_SIZE])

    print("✅ ETF Historical Data Updated Successfully")


if __name__ == "__main__":
    run()