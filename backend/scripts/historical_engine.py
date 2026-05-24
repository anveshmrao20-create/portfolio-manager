import yfinance as yf
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import math

# ================= CONFIG =================

SPREADSHEET_NAME = "PortfolioAutomation"

TICKERS = [
    "ASHOKA.NS","BEL.NS","COALINDIA.NS","HAL.NS",
    "HCLTECH.NS","HEROMOTOCO.NS","HINDALCO.NS","IMFA.NS",
    "KPIGREEN.NS","KPITTECH.NS","LTFOODS.NS","NATCOPHARM.NS",
    "NESCO.NS","PETRONET.NS","TMCV.NS","ZYDUSLIFE.NS","TMPV.NS"
]

LOOKBACK_DAYS = 520
RSI_PERIOD = 14
SIGNAL_PERIOD = 9
LOOKBACK_52W = 252

# ================= GOOGLE SHEETS =================

def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("/opt/airflow/scripts/credentials.json", scope)
    client = gspread.authorize(creds)
    return client.open(SPREADSHEET_NAME).worksheet("Historical")

# ================= LOGGER =================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ================= HELPERS =================

def safe_num(v):
    try:
        return float(v)
    except:
        return None

def clean_value(v):
    if v is None:
        return ""
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return ""
    return v

# ================= FETCH =================

def fetch_with_retry(ticker, retries=3):
    for i in range(retries):
        try:
            df = yf.download(
                ticker,
                period=f"{LOOKBACK_DAYS}d",
                interval="1d",
                progress=False,
                auto_adjust=False,  # ✅ TradingView match
                threads=False
            )

            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df

        except Exception as e:
            log(f"Retry {i+1} failed for {ticker}: {e}")

        time.sleep(1)

    return None

# ================= INDICATORS =================

def compute_ema(arr, period):
    series = pd.Series(arr, dtype="float64")
    return series.ewm(span=period, adjust=False).mean().tolist()

def compute_rsi(values, period):
    series = pd.Series(values, dtype="float64")

    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi.tolist()

# ================= MAIN =================

def update_historical():

    sheet = get_sheet()
    log("Fetching data...")

    stock_data = {}
    all_dates = set()

    for ticker in TICKERS:
        name = ticker.replace(".NS", "").upper()
        log(f"Fetching {name}")

        df = fetch_with_retry(ticker)

        if df is None:
            log(f"❌ Failed: {name}")
            continue

        data = []

        for idx, row in df.iterrows():
            try:
                date = pd.to_datetime(idx).strftime("%Y-%m-%d")
            except:
                continue

            close = safe_num(row["Close"])
            volume = safe_num(row["Volume"])

            if close is None:
                continue

            data.append((date, close, volume))
            all_dates.add(date)

        if data:
            stock_data[name] = data

    if not stock_data:
        log("❌ No usable data. Aborting.")
        return

    dates = sorted(all_dates)

    header = ["Date"]
    for name in stock_data.keys():
        header.extend([
            name, "RSI", "EMA100", "EMA200", "EMA12", "EMA26",
            "MACD", "Signal", "52W High", "52W Low",
            "Volume", "Vol MA20"
        ])

    processed = {}

    for name, data in stock_data.items():
        data_map = {d: (c, v) for d, c, v in data}

        closes = [data_map.get(d, (None, None))[0] for d in dates]
        volumes = [data_map.get(d, (None, None))[1] for d in dates]

        close_series = pd.Series(closes, dtype="float64")

        rsi = compute_rsi(close_series, RSI_PERIOD)
        ema100 = compute_ema(close_series, 100)
        ema200 = compute_ema(close_series, 200)

        ema12_series = close_series.ewm(span=12, adjust=False).mean()
        ema26_series = close_series.ewm(span=26, adjust=False).mean()

        macd_series = ema12_series - ema26_series
        signal_series = macd_series.ewm(span=SIGNAL_PERIOD, adjust=False).mean()

        ema12 = ema12_series.tolist()
        ema26 = ema26_series.tolist()
        macd = macd_series.tolist()
        signal = signal_series.tolist()

        highs, lows, vol_ma20 = [], [], []

        for i in range(len(closes)):
            window = close_series[max(0, i - LOOKBACK_52W + 1):i + 1]
            vals = window.dropna()

            highs.append(vals.max() if not vals.empty else None)
            lows.append(vals.min() if not vals.empty else None)

            vol_window = pd.Series(volumes[max(0, i - 19):i + 1]).dropna()
            vol_ma20.append(vol_window.mean() if not vol_window.empty else None)

        processed[name] = [
            [
                clean_value(closes[i]),
                clean_value(rsi[i]),
                clean_value(ema100[i]),
                clean_value(ema200[i]),
                clean_value(ema12[i]),
                clean_value(ema26[i]),
                clean_value(macd[i]),
                clean_value(signal[i]),
                clean_value(highs[i]),
                clean_value(lows[i]),
                clean_value(volumes[i]),
                clean_value(vol_ma20[i])
            ]
            for i in range(len(dates))
        ]

    final_matrix = []

    for i in range(len(dates)):
        row = [dates[i]]
        for name in processed.keys():
            row.extend(processed[name][i])
        final_matrix.append(row)

    log(f"📈 Writing {len(final_matrix)} rows")

    sheet.clear()
    sheet.update(values=[header] + final_matrix, range_name="A1")

    log("✅ SUCCESS — No NaN issues, TradingView aligned")

# ================= RUN =================

if __name__ == "__main__":
    update_historical()