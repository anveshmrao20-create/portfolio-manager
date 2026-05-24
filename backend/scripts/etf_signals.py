import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

def get_client():
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)


# 🔥 SAFE FLOAT HANDLER
def safe_float(x):
    try:
        if x in ("", None):
            return None
        return float(x)
    except:
        return None


# 🔥 ETF-SPECIFIC CONFIG
ETF_CONFIG = {
    "MOM100": {"dip3": 6, "dip6": 12, "rsi_low": 45, "rsi_high": 60},
    "HDFCSML250": {"dip3": 8, "dip6": 15, "rsi_low": 40, "rsi_high": 55},
    "CPSEETF": {"dip3": 7, "dip6": 14, "rsi_low": 40, "rsi_high": 55},
    "JUNIORBEES": {"dip3": 5, "dip6": 10, "rsi_low": 40, "rsi_high": 55},
    "GOLDBEES": {"dip3": 4, "dip6": 8, "rsi_low": 35, "rsi_high": 50},
    "SILVERBEES": {"dip3": 6, "dip6": 12, "rsi_low": 40, "rsi_high": 55},
    "MON100": {"dip3": 5, "dip6": 10, "rsi_low": 40, "rsi_high": 55}
}


def run():
    client = get_client()
    ss = client.open("PortfolioAutomation")

    hist = ss.worksheet("ETF_Historical").get_all_values()
    sig = ss.worksheet("ETF_Signals")

    try:
        buy = ss.worksheet("ETF_BuyHistory")
    except:
        buy = ss.add_worksheet(title="ETF_BuyHistory", rows=1000, cols=10)
        buy.append_row(["Date","ETF","Price","Score","Reason"])

    sig.clear()
    sig.append_row(["Date","ETF","Action","Score","Price","RSI","EMA100","Dip%","Reason"])

    today = datetime.now().strftime("%Y-%m-%d")

    for c in range(1, len(hist[0]), 12):

        etf = hist[0][c]

        config = ETF_CONFIG.get(etf, {"dip3":5, "dip6":10, "rsi_low":40, "rsi_high":55})

        close = safe_float(hist[-1][c])
        rsi = safe_float(hist[-1][c+1])
        ema100 = safe_float(hist[-1][c+2])

  
        prev_rsi = safe_float(hist[-2][c+1]) if len(hist) > 2 else None

        reason = []
        score = 0
        action = "HOLD"
        dip = 0

        # =====================
        # 🔴 DATA VALIDATION
        # =====================
        if close is None or rsi is None or ema100 is None:
            action = "SKIPPED"
            reason.append("Missing Data")

            sig.append_row([
                today, etf, action, 0,
                close or 0, rsi or 0, ema100 or 0,
                0, ",".join(reason)
            ])
            continue

        # =====================
        # 🔴 OVERBOUGHT FILTER
        # =====================
        if rsi >= 65:
            action = "SKIPPED"
            reason.append("Overbought RSI")

            sig.append_row([
                today, etf, action, 0,
                close, rsi, ema100,
                0, ",".join(reason)
            ])
            continue

        # =====================
        # 🔴 DIP CALCULATION
        # =====================
        highs_3m = [safe_float(r[c]) for r in hist[-60:] if safe_float(r[c]) is not None]
        highs_6m = [safe_float(r[c]) for r in hist[-120:] if safe_float(r[c]) is not None]

	
	
        if not highs_3m:
            action = "SKIPPED"
            reason.append("Insufficient Data")

            sig.append_row([
                today, etf, action, 0,
                close, rsi, ema100,
                0, ",".join(reason)
            ])
            continue

        high_3m = max(highs_3m)
        dip_3m = ((high_3m - close) / high_3m) * 100

        dip = dip_3m

        dip_6m = 0

        if highs_6m:
            high_6m = max(highs_6m)
            dip_6m = ((high_6m - close) / high_6m) * 100

		

	 
	   

        # =====================
        # 🟢 SCORING
        # =====================
        if dip_3m > config["dip3"]:
            score += 20
            reason.append("3M Dip")

        if dip_6m > config["dip6"]:
            score += 20
            reason.append("6M Deep Dip")

		  
        if config["rsi_low"] <= rsi <= config["rsi_high"]:

            if prev_rsi is not None and rsi > prev_rsi + 1:
                score += 25
                reason.append("RSI Rising")

            else:
                score += 15
                reason.append("RSI Neutral")

        if close > ema100:
            score += 20
            reason.append("Trend")

        # =====================
        # 🚫 DUPLICATE BUY PROTECTION
        # =====================
        ALLOW_BUY = True

        BUY_COOLDOWN_DAYS = 14
        MIN_PRICE_DROP_FOR_REBUY = 3
        MIN_NEW_DIP_IMPROVEMENT = 2
        MIN_RSI_IMPROVEMENT = 5

        last_buy_price = None
        last_buy_date = None
        last_buy_score = None

        buy_data = buy.get_all_values()

        for r in reversed(buy_data[1:]):

            if len(r) < 4:
                continue

            if r[1] != etf:
                continue

            try:
                last_buy_date = datetime.strptime(r[0], "%Y-%m-%d")
                last_buy_price = float(r[2])
                last_buy_score = float(r[3])
                break

            except:
                continue

		
        # =====================
        # 🎯 FINAL DECISION
        # =====================
        action = "BUY" if score >= 60 else "HOLD"

		
        # =====================
        # 🔒 BUY FILTER
        # =====================
        if action == "BUY" and last_buy_date is not None:

            days_since_buy = (datetime.now() - last_buy_date).days

            price_drop_from_last_buy = (
                ((last_buy_price - close) / last_buy_price) * 100
                if last_buy_price else 0
            )

            dip_improvement = 0

            if len(highs_3m) > 0:
                dip_improvement = dip_3m

            rsi_improvement = 0

            if prev_rsi is not None:
                rsi_improvement = rsi - prev_rsi

		
            # 🚫 SAME DIP ZONE PROTECTION
            if (
                days_since_buy < BUY_COOLDOWN_DAYS
                and price_drop_from_last_buy < MIN_PRICE_DROP_FOR_REBUY
                and dip_improvement < (config["dip3"] + MIN_NEW_DIP_IMPROVEMENT)
                and rsi_improvement < MIN_RSI_IMPROVEMENT
            ):

                action = "HOLD"
                reason.append("Duplicate Buy Prevented")

		
        # =====================
        # 📝 SAVE BUY
        # =====================
        if action == "BUY":

            buy.append_row([
                today,
                etf,
                round(close, 2),
                score,
                ",".join(reason)
            ])

        sig.append_row([
            today, etf, action, score,
            close, rsi, ema100,
            round(dip, 2), ",".join(reason)
        ])


if __name__ == "__main__":
    run()