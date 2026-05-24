import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

TOTAL_SIP = 5000


def get_client():
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)


def safe_float(x):
    try:
        if x in ("", None):
            return None
        return float(x)
    except:
        return None


def run():

    client = get_client()
    ss = client.open("PortfolioAutomation")

    hist = ss.worksheet("ETF_Historical")
    data = hist.get_all_values()

		
    sip = ss.worksheet("ETF_SIP_Weekly")
		   
																		  

			
    sip.clear()
    sip.append_row([
        "Date","Rank","ETF",
        "Weight (%)",
        "Allocation (₹)",
						  
					
						   
        "60D Return",
        "Dip 3M","Dip 6M",
					 
				
        "Trend","Final Score",
        "Dip Multiplier","Comment"
    ])

    ranking = []

    for c in range(1, len(data[0]), 12):

        etf = data[0][c]

        prices = []
        ema100 = None
        ema200 = None

										
        for r in reversed(data[1:]):
            price = safe_float(r[c])
            e100 = safe_float(r[c+2])
            e200 = safe_float(r[c+3])

            if price is not None:
                prices.append(price)

            if ema100 is None and e100 is not None:
                ema100 = e100

            if ema200 is None and e200 is not None:
                ema200 = e200

        if len(prices) < 120 or ema100 is None or ema200 is None:
            continue

        close = prices[0]
		  

        # ===== Momentum =====
							   
        ret = (close / prices[59] - 1) * 100

        # ===== Trend =====
        trend = "Strong" if close > ema100 else "Weak"

        # ===== Trend Penalty =====
        trend_score = 20 if close > ema100 else -10

        # ===== Structural filter =====
        if close < ema200:
            trend_score -= 20

        # ===== DIP =====
        high_3m = max(prices[:60])
        high_6m = max(prices[:120])

        dip_3m = ((high_3m - close) / high_3m) * 100
        dip_6m = ((high_6m - close) / high_6m) * 100

        # ===== Dip Multiplier =====
        dip_multiplier = 1.0
        comment = ""

        if dip_6m > 15:
            dip_multiplier = 1.4
            comment = "Deep Value Zone"
        elif dip_3m > 8:
            dip_multiplier = 1.2
            comment = "Good Dip"

        # ===== Final Score =====
        score = ret + trend_score

        ranking.append({
            "etf": etf,
            "score": score,
            "return": round(ret,2),
            "dip3": round(dip_3m,2),
            "dip6": round(dip_6m,2),
            "trend": trend,
            "multiplier": dip_multiplier,
									   
								   
            "comment": comment
        })

    # ===== SORT =====
    ranking = sorted(ranking, key=lambda x: x["score"], reverse=True)

	
    top = ranking[:3]

    # ===== NORMALIZE SCORES =====
    total_score = sum([max(x["score"], 0) for x in top])

    today = datetime.now().strftime("%Y-%m-%d")

							  
    for i, etf in enumerate(top):

        weight = max(etf["score"], 0) / total_score if total_score > 0 else 0
        alloc = weight * TOTAL_SIP

        # Apply dip multiplier
        alloc = alloc * etf["multiplier"]

        sip.append_row([
            today,
            i+1,
            etf["etf"],
            round(weight*100,2),
            round(alloc),
            etf["return"],
						
            etf["dip3"],
            etf["dip6"],
            etf["trend"],
            round(etf["score"],2),
            etf["multiplier"],
            etf["comment"]
        ])

    print("✅ PRO SIP Engine Updated")


if __name__ == "__main__":
    run()