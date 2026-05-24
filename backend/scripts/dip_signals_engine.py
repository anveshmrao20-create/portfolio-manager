# ================= UNIFIED DIP COMPOUNDING ENGINE (EXPLANATION ADDED) =================
# Enhancement: Adds human-readable explanation for BUY decisions
# Added: Indicator visibility + 2M & 6M dip logic + 2M/6M HIGH display
# NEW: RSI slope logic + STAGGERED BUY (no existing logic changed)

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import re
import math

# ================= CONFIG =================
SPREADSHEET_NAME = "PortfolioAutomation"

TOTAL_CAPITAL = 0  
CASH_RESERVE = 0.2
MAX_PORTFOLIO = 0  

MAX_PER_STOCK_PCT = 0.08
MAX_PER_SECTOR_PCT = 0.25
ROLLING_WINDOW_DAYS = 60

# ================= SECTOR MAP =================
SECTOR_MAP = {
    "HCLTECH": "IT","KPITTECH": "IT",
    "COALINDIA": "METAL","HINDALCO": "METAL",
    "HEROMOTOCO": "AUTO","TMCV": "AUTO","TMPV": "AUTO",
    "NATCOPHARM": "PHARMA","ZYDUSLIFE": "PHARMA",
    "BEL": "DEFENCE","HAL": "DEFENCE",
    "PETRONET": "ENERGY","ASHOKA": "INFRA",
    "LTFOODS": "FMCG","NESCO": "REALTY","IMFA": "METAL"
}

# ================= NAME MAP =================
NAME_MAP = {
    "ashoka": "ASHOKA","bel": "BEL","coal india": "COALINDIA","coalindia": "COALINDIA",
}

# ================= HELPERS =================
def normalize_name(name):
    return re.sub(r'[^a-z0-9]', '', str(name).lower())

def normalize_stock(name):
    key = re.sub(r'[^a-z0-9\\s]', '', str(name).lower()).strip()
    return NAME_MAP.get(key, str(name).upper())

def get_client():
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("/opt/airflow/scripts/credentials.json", scope)
    return gspread.authorize(creds)

def safe_cell(arr, r, c):
    try:
        v = arr[r][c]
        if v in ("", None): return None
        return float(str(v).replace(",", "").strip())
    except:
        return None

def find_last_numeric(arr, c):
    for i in range(len(arr)-1, 0, -1):
        try:
            return i, float(arr[i][c])
        except:
            continue
    return None

# ================= BUY HISTORY FIX =================
def ensure_buy_history_sheet(ss):
    try:
        sheet = ss.worksheet("BuyHistory")
    except:
        sheet = ss.add_worksheet(title="BuyHistory", rows=1000, cols=10)
        sheet.append_row(["Date","Stock","Price","Score","Reason"])
        return sheet

    data = sheet.get_all_values()

    if not data:
        sheet.append_row(["Date","Stock","Price","Score","Reason"])
        return sheet

    headers = data[0]
    expected = ["Date","Stock","Price","Score","Reason"]

    if headers[:3] != expected:
        print("⚠️ Fixing BuyHistory format...")

        old_data = data[:]
        sheet.clear()
        sheet.append_row(expected)

        for row in old_data:
            if len(row) >= 3:
                try:
                    datetime.strptime(row[0], "%Y-%m-%d")
                    float(row[2])
                    sheet.append_row(row[:3])
                except:
                    continue

    return sheet

# ================= MAIN =================
def run_engine():

    client = get_client()
    ss = client.open(SPREADSHEET_NAME)

    hist = ss.worksheet("Historical").get_all_values()
    fund = ss.worksheet("Fundamentals").get_all_values()

    # ===== PORTFOLIO INTEGRATION =====
    portfolio = ss.worksheet("Portfolio").get_all_values()

    stock_investment = {}
    sector_investment = {}
    total_invested = 0
    LIQUID_CASH = 0

    for row in portfolio[1:]:
        try:
            stock_raw = row[0]
            invested_val = float(row[5]) if row[5] else 0

            stock = normalize_stock(stock_raw)
            key = normalize_name(stock)

            if "LIQUID" in stock.upper():
                LIQUID_CASH += invested_val
                continue

            stock_investment[key] = invested_val
            total_invested += invested_val

            sector = SECTOR_MAP.get(stock, "OTHER")
            sector_investment[sector] = sector_investment.get(sector, 0) + invested_val

        except:
            continue

    # ===== DYNAMIC CAPITAL APPLICATION =====
    TOTAL_CAPITAL = total_invested + LIQUID_CASH
    MAX_PORTFOLIO = TOTAL_CAPITAL * (1 - CASH_RESERVE)
    
    MAX_PER_STOCK = TOTAL_CAPITAL * MAX_PER_STOCK_PCT
    MAX_PER_SECTOR = TOTAL_CAPITAL * MAX_PER_SECTOR_PCT

    # ===== BUY HISTORY =====
    buy_hist = ensure_buy_history_sheet(ss)
    buy_data = buy_hist.get_all_values()

    headers = hist[0]

		 
	   
		
	   
    last_buy_price = {}
    recent_buy_count = {}

    now = datetime.now()
    window_start = now - timedelta(days=ROLLING_WINDOW_DAYS)

    for row in buy_data[1:]:
        try:
            date_str = row[0]
            stock_raw = row[1]
            price = float(row[2])

            stock = normalize_name(stock_raw)

															   
		   

            last_buy_price[stock] = price

				
																   

            if date_str:
                d = datetime.strptime(date_str, "%Y-%m-%d")
                if d >= window_start:
                    recent_buy_count[stock] = recent_buy_count.get(stock, 0) + 1

        except:
            continue

    # ===== FUNDAMENTALS =====
    fund_headers = fund[0]

    if "Stock" in fund_headers:
        stock_idx = fund_headers.index("Stock")
    elif "Stock Name" in fund_headers:
        stock_idx = fund_headers.index("Stock Name")
    elif "Company" in fund_headers:
        stock_idx = fund_headers.index("Company")
    else:
        raise Exception("No stock column found")

    if "Fundamental Grade" in fund_headers:
        grade_idx = fund_headers.index("Fundamental Grade")
    elif "Grade" in fund_headers:
        grade_idx = fund_headers.index("Grade")
    else:
        raise Exception("No grade column found")

    fund_map = {}
    for r in fund[1:]:
        fund_map[normalize_name(r[stock_idx])] = r[grade_idx]

    # ===== OUTPUT =====
    sig_sheet = ss.worksheet("Signals")
    sig_sheet.clear()

    sig_sheet.append_row([
        "Date","Stock","Signal",
        "Fundamental Grade","Fundamental Score",
        "Technical Grade","Technical Score",
        "Close",
        "RSI","EMA100","EMA200","MACD","SignalLine","Volume","VolMA",
        "High2M","High6M",
        "Investment","Qty","Reason","Explanation"
    ])

    today = datetime.now().strftime("%Y-%m-%d")
    out = []

 
    for c in range(1, len(headers), 12):

        stock = normalize_stock(headers[c])
        key = normalize_name(stock)

        found = find_last_numeric(hist, c)
        if not found: continue

        row_idx, close = found

        rsi = safe_cell(hist, row_idx, c+1)
        prev_rsi = safe_cell(hist, row_idx-1, c+1)

        ema100 = safe_cell(hist, row_idx, c+2)
        ema200 = safe_cell(hist, row_idx, c+3)
        macd = safe_cell(hist, row_idx, c+6)
        sig_ln = safe_cell(hist, row_idx, c+7)
        volume = safe_cell(hist, row_idx, c+10)
        vol_ma = safe_cell(hist, row_idx, c+11)

        prev_macd = safe_cell(hist, row_idx-1, c+6)
        prev_sig = safe_cell(hist, row_idx-1, c+7)

        closes = [safe_cell(hist, i, c) for i in range(1, len(hist)) if safe_cell(hist, i, c)]

        recent_5day_high = max(closes[-5:]) if len(closes) >= 5 else close
        if len(closes) < 40: continue

   
        high2m = max(closes[-40:])
        high6m = max(closes[-120:]) if len(closes) >= 120 else high2m

        dip_pct = ((high2m - close) / high2m) * 100
        dip_6m = ((high6m - close) / high6m) * 100

  
        tech_score = 0
        explanation_parts = []

   
        if dip_6m >= 35:
            tech_score += 30
            explanation_parts.append("Deep long-term correction (6M)")
        elif dip_6m >= 25:
            tech_score += 20
            explanation_parts.append("Strong long-term dip (6M)")

   
        if rsi and prev_rsi:
            if 35 <= rsi <= 50 and rsi > prev_rsi:
                tech_score += 30
                explanation_parts.append("RSI recovering (bullish)")
            elif 35 <= rsi <= 50:
                tech_score += 15
                explanation_parts.append("RSI neutral")

        if ema100 and ema200 and ema100 > ema200:
            tech_score += 20
            explanation_parts.append("Uptrend intact")

        if prev_macd and prev_sig and macd and sig_ln:
            if prev_macd <= prev_sig and macd > sig_ln:
                tech_score += 20
                explanation_parts.append("MACD bullish crossover")

        if volume and vol_ma and volume > 1.2 * vol_ma:
            tech_score += 15
            explanation_parts.append("Volume expansion")

        if dip_pct >= 20:
            tech_score += 25
            explanation_parts.append("Deep correction")
        elif dip_pct >= 15:
            tech_score += 18
            explanation_parts.append("Healthy dip")

        grade = fund_map.get(key, "Unknown")
        confidence = min(100, tech_score)

			
        is_confirmation = False
        
        
        if key in last_buy_price:
            last_price = last_buy_price[key]
        
            # 🔹 Recovery (confirmation)
            if (close > last_price * 1.03 and
                close > ema100 and
                rsi and prev_rsi and rsi > prev_rsi + 2 and rsi > 45 and
                prev_macd and prev_sig and macd and sig_ln and macd > sig_ln and
                close > recent_5day_high):
                is_confirmation = True
        
            # 🔹 Additional dip ≥ 12%
            drop_from_last = ((close - last_price) / last_price) * 100
            is_deep_dip = False

            if drop_from_last <= -12:
            
                dip_quality = True
            
                # RSI should not be extremely weak
                if rsi and rsi < 30:
                    dip_quality = False
            
                # Trend check (avoid broken trend)
                if ema100 and ema200 and ema100 < ema200:
                    dip_quality = False
            
                # Avoid strong bearish momentum
                if macd and sig_ln and macd < sig_ln and prev_macd and prev_sig and prev_macd < prev_sig:
                    dip_quality = False
            
                if dip_quality:
                    is_deep_dip = True

        allow_entry = False
        buy_count = recent_buy_count.get(key, 0)
        
        if buy_count == 0:
            if tech_score >= 75 and grade == "Strong":
                allow_entry = True
            elif tech_score >= 60:
                allow_entry = True
        
        elif buy_count == 1:
            if is_confirmation or is_deep_dip:
                if tech_score >= 60:
                    allow_entry = True

        invested_stock = stock_investment.get(key, 0)
        sector = SECTOR_MAP.get(stock, "OTHER")
        invested_sector = sector_investment.get(sector, 0)

        remaining_stock = MAX_PER_STOCK - invested_stock
        remaining_sector = MAX_PER_SECTOR - invested_sector
        remaining_portfolio = max(0, MAX_PORTFOLIO - total_invested)

        portfolio_pct = (invested_stock / total_invested * 100) if total_invested else 0

        multiplier = 1
        if key in last_buy_price:
            drop = ((close - last_buy_price[key]) / last_buy_price[key]) * 100
            if drop <= -20: multiplier = 1.6
            elif drop <= -15: multiplier = 1.4
            elif drop <= -10: multiplier = 1.2

        action = "HOLD"
        investment = 0
        qty = 0

        if portfolio_pct > 25:
            action = "TRIM"
            explanation = "Position oversized, trimming for risk control"

        elif allow_entry and remaining_stock > 0 and remaining_sector > 0:

            base = 15000 if tech_score >= 75 else 10000

			
            if is_confirmation:
                base = int(base * 1.3)
                explanation_parts.append("Confirmation buy (trend improving)")
            else:
                explanation_parts.append("Initial buy (dip entry)")

            investment = max(0, min(base * multiplier, remaining_stock, remaining_sector, remaining_portfolio, LIQUID_CASH))
            qty = math.floor(investment / close)

            if qty > 0:
                action = "BUY"
                buy_hist.append_row([today, stock, close, tech_score, ", ".join(explanation_parts)])
                explanation = ", ".join(explanation_parts) + f" | Fundamental: {grade}"
        else:
            explanation = "No strong signal or allocation constraints"

   
        reason = f"Dip2M:{dip_pct:.1f}% Dip6M:{dip_6m:.1f}% Score:{tech_score} Grade:{grade} Alloc:{portfolio_pct:.1f}% Buys60D:{recent_buy_count.get(key,0)}"

        # 🔹 Define grades + scores
        fund_grade = grade
        fund_score = 100 if grade == "Strong" else 70 if grade == "Moderate" else 50
        
        tech_score = tech_score
        tech_grade = "Strong" if tech_score >= 75 else "Moderate" if tech_score >= 60 else "Weak"
        
        signal = action  # BUY / HOLD / TRIM
        
        out.append([
            today, stock, signal,
            fund_grade, fund_score,
            tech_grade, tech_score,
            close,
            rsi, ema100, ema200, macd, sig_ln, volume, vol_ma,
            round(high2m,2), round(high6m,2),
            round(investment,0), qty, reason, explanation
        ])

    if out:
        sig_sheet.append_rows(out)

    print("✅ Engine with Correct Dynamic Allocation Running")


if __name__ == "__main__":
    run_engine()