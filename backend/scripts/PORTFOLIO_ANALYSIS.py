import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re

SPREADSHEET_NAME = "PortfolioAutomation"

# ================= NORMALIZE =================
def normalize(name):
    if not name:
        return ""
    name = str(name).upper()

    name = name.replace("NSE:", "").replace("BSE:", "")
    name = name.replace(".NS", "")

    return re.sub(r'[^A-Z0-9]', '', name)


# ================= AUTH =================
def get_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("/opt/airflow/scripts/credentials.json", scope)
    return gspread.authorize(creds)


# ================= SAFE =================
def safe_num(v):
    try:
        return float(v)
    except:
        return None


def find_last_numeric(arr, c):
    for i in range(len(arr)-1, 0, -1):
        try:
            return i, float(arr[i][c])
        except:
            continue
    return None


# ================= MAIN =================
def portfolio_analysis():

    client = get_client()
    ss = client.open(SPREADSHEET_NAME)

    f = ss.worksheet("Fundamentals")
    h = ss.worksheet("Historical")

    try:
        pa = ss.worksheet("Portfolio Analysis")
        pa.clear()
    except:
        pa = ss.add_worksheet(title="Portfolio Analysis", rows=2000, cols=10)

    pa.append_row([
        "Date","Stock","Fundamental Score","Technical Score",
        "Final Score","Recommendation","Comment"
    ])

    fd = f.get_all_values()
    fh = fd[0]

    hd = h.get_all_values()
    hh = hd[0]

    sc = fh.index("Score")
    sn = fh.index("Stock Name") if "Stock Name" in fh else fh.index("Stock")

    # ================= HEADER MAP (FIXED) =================
    header_map = {}

    # First stock (ASHOKA)
    c = 1
    if c < len(hh):
        header_map[normalize(hh[c])] = c

    # Second stock (BEL)
    c += 12

    # Remaining stocks (step = 12)
    while c < len(hh):
        header = hh[c]
        key = normalize(header)

        if key:
            header_map[key] = c

        c += 12

    print("🔍 Header map keys:", list(header_map.keys()))

    today = datetime.now().strftime("%Y-%m-%d")

    written = 0

    for i in range(1, len(fd)):

        stock_raw = fd[i][sn]
        stock_key = normalize(stock_raw)

        fs = safe_num(fd[i][sc])

        best_col = header_map.get(stock_key)

        if best_col is None:
            print(f"❌ No match for {stock_raw} → ({stock_key})")
            continue

        found = find_last_numeric(hd, best_col)
        if not found:
            print(f"❌ No data for {stock_raw}")
            continue

        row_idx, close = found

        rsi = safe_num(hd[row_idx][best_col + 1])
        ema100 = safe_num(hd[row_idx][best_col + 2])
        ema200 = safe_num(hd[row_idx][best_col + 3])
        macd = safe_num(hd[row_idx][best_col + 7])
        sig = safe_num(hd[row_idx][best_col + 8])

        # ================= TECH SCORE =================
        t = 0

        if rsi is not None:
            if 35 <= rsi <= 55:
                t += 25
            elif rsi < 35:
                t += 15

        if ema200 and ema100:
            if close >= ema200 and ema100 >= ema200:
                t += 20
            elif close >= ema200:
                t += 10
            else:
                t -= 10

        if ema100:
            diff = abs((close - ema100) / ema100)
            if diff <= 0.03:
                t += 15
            elif diff <= 0.07:
                t += 10

        if macd is not None and sig is not None:
            t += 20 if macd > sig else 10

        t = max(0, min(100, t))

        final = round((fs or 0) * 0.8 + t * 0.2)

        # ================= RECOMMENDATION =================
        if final >= 80:
            rec = "STRONG BUY"
        elif final >= 65:
            rec = "BUY"
        elif final >= 50:
            rec = "HOLD"
        else:
            rec = "AVOID"

        # ================= COMMENT =================
        comments = []

        if fs:
            if fs >= 80:
                comments.append("Strong fundamentals")
            elif fs >= 60:
                comments.append("Good fundamentals")
            else:
                comments.append("Weak fundamentals")

        if ema200:
            if close >= ema200:
                comments.append("Uptrend")
            else:
                comments.append("Weak trend")

        if rsi:
            if 40 <= rsi <= 60:
                comments.append("Stable momentum")
            elif rsi < 35:
                comments.append("Weak momentum")
            elif rsi > 65:
                comments.append("Overbought")

        comment = ", ".join(comments)

        pa.append_row([
            today, stock_raw, fs, t, final, rec, comment
        ])

        print(f"✅ {stock_raw} → {rec}")
        written += 1

    print(f"\n🎯 DONE: {written} stocks written")


# ================= RUN =================
if __name__ == "__main__":
    portfolio_analysis()