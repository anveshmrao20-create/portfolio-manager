import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import math
import re

# ================= CONFIG =================
SPREADSHEET_NAME = "PortfolioAutomation"

# ================= NAME STANDARDIZATION =================
NAME_MAP = {
    "ashoka": "ASHOKA",
    "bel": "BEL",
    "coal india": "COALINDIA",
    "coalindia": "COALINDIA",
    "hal": "HAL",
    "hcl tech": "HCLTECH",
    "hcltech": "HCLTECH",
    "hero motocorp": "HEROMOTOCO",
    "heromotoco": "HEROMOTOCO",
    "hindalco industries": "HINDALCO",
    "hindalco": "HINDALCO",
    "imfa": "IMFA",
    "indian metals": "IMFA",
    "kpigreen": "KPIGREEN",
    "kpit tech": "KPITTECH",
    "kpittech": "KPITTECH",
    "lt foods": "LTFOODS",
    "ltfoods": "LTFOODS",
    "natco pharma": "NATCOPHARM",
    "natcopharm": "NATCOPHARM",
    "nesco ltd": "NESCO",
    "nesco": "NESCO",
    "petronet lng": "PETRONET",
    "petronet": "PETRONET",
    "tmcv": "TMCV",
    "tmpv": "TMPV",
    "zydus lifesciences": "ZYDUSLIFE",
    "zyduslife": "ZYDUSLIFE"
}

def normalize_stock_name(name):
    key = re.sub(r'[^a-z0-9\s]', '', str(name).lower()).strip()
    return NAME_MAP.get(key, str(name).upper())

# ================= GOOGLE SHEETS =================
def get_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("/opt/airflow/scripts/credentials.json", scope)
    return gspread.authorize(creds)

# ================= MAIN FUNCTION =================
def monthly_sip_picker():

    client = get_client()
    ss = client.open(SPREADSHEET_NAME)

    sig_sheet = ss.worksheet("Signals")

    try:
        sip_history_sheet = ss.worksheet("SIP_History")
    except:
        sip_history_sheet = ss.add_worksheet(title="SIP_History", rows=1000, cols=10)
        sip_history_sheet.append_row(["Date", "Stock"])

    hist_data = sip_history_sheet.get_all_values()

    recent_sip = set()
    now = datetime.now()
    two_months_ago = now - timedelta(days=60)

    for row in hist_data[1:]:
        try:
            date_str, stock = row[:2]
            if not stock or not date_str:
                continue

            d = datetime.strptime(date_str, "%Y-%m-%d")
            if d > two_months_ago:
                # ✅ STANDARDIZE
                stock = normalize_stock_name(stock)
                recent_sip.add(stock.lower().strip())
        except:
            continue

    all_data = sig_sheet.get_all_values()
    if len(all_data) < 2:
        raise Exception("Signals sheet is empty.")

    headers = all_data[0]
    data = all_data[1:]

    idx = {
        "stock": headers.index("Stock"),
        "fundGrade": headers.index("Fundamental Grade"),
        "fundScore": headers.index("Fundamental Score"),
        "techGrade": headers.index("Technical Grade"),
        "techScore": headers.index("Technical Score"),
        "close": headers.index("Close"),
        "signal": headers.index("Signal"),
    }

    valid = [r for r in data if r[idx["fundScore"]] and r[idx["techScore"]]]

    if not valid:
        raise Exception("No valid stocks found.")

    stocks = []
    for r in valid:

        # ✅ STANDARDIZE
        stock = normalize_stock_name(r[idx["stock"]])

        fund_score = float(r[idx["fundScore"]] or 0)
        tech_score = float(r[idx["techScore"]] or 0)
        fund_grade = str(r[idx["fundGrade"]] or "")
        tech_grade = str(r[idx["techGrade"]] or "")
        signal = str(r[idx["signal"]] or "")
        close = float(r[idx["close"]] or 0)

        combined = (fund_score * 0.6) + (tech_score * 0.4)

        if fund_grade == "Strong" and tech_grade == "Strong":
            reason = "Excellent fundamentals and strong momentum — stable long-term compounder."
        elif fund_grade == "Strong" and tech_grade == "Moderate":
            reason = "Financially solid company with improving technicals — ideal for steady SIP accumulation."
        elif fund_grade == "Moderate" and tech_grade == "Strong":
            reason = "Technical breakout with improving business strength — emerging momentum play."
        elif "BUY DIP" in signal:
            reason = "Recently corrected from highs but strong underlying fundamentals — good entry point."
        elif tech_grade == "Weak" and fund_grade == "Strong":
            reason = "Temporarily weak technicals; long-term fundamentals remain attractive — accumulate gradually."
        else:
            reason = "Balanced setup with moderate valuation and trend — suitable for diversification."

        stocks.append({
            "stock": stock,
            "fundGrade": fund_grade,
            "fundScore": fund_score,
            "techGrade": tech_grade,
            "techScore": tech_score,
            "close": close,
            "combined": combined,
            "reason": reason
        })

    stocks.sort(key=lambda x: x["combined"], reverse=True)

    final_picks = []
    for s in stocks:
        if len(final_picks) >= 4:
            break
        if s["stock"].lower().strip() in recent_sip:
            continue
        final_picks.append(s)

    try:
        sip_sheet = ss.worksheet("SIP Allocation")
    except:
        sip_sheet = ss.add_worksheet(title="SIP Allocation", rows=1000, cols=20)

    sip_sheet.clear()

    if not final_picks:
        sip_sheet.append_row(["All top stocks were recently picked — no new SIP suggestions this month."])
        return

    SIP_BUDGET = 20000
    weights = [7000, 6000, 4000, 3000]

    for i, s in enumerate(final_picks):
        s["amount"] = weights[i] if i < len(weights) else round(SIP_BUDGET / 4)
        s["qty"] = math.floor(s["amount"] / s["close"]) if s["close"] > 0 else 0

    today_str = datetime.now().strftime("%Y-%m-%d")

    sip_sheet.append_row(["📅 Monthly SIP Allocation – Top 4 Long-Term Stocks"])
    sip_sheet.append_row(["Date:", today_str])
    sip_sheet.append_row(["Total SIP Budget (₹):", SIP_BUDGET])
    sip_sheet.append_row(["Allocated (₹):", sum(s["amount"] for s in final_picks)])
    sip_sheet.append_row(["──────────────────────────────────────────────"])
    sip_sheet.append_row([
        "📘 Strategy Note:",
        "Avoids repeats in last 2 months. Replaces skipped stocks automatically."
    ])
    sip_sheet.append_row(["──────────────────────────────────────────────"])
    sip_sheet.append_row([
        "Stock", "Fundamental Grade", "Technical Grade",
        "Fund Score", "Tech Score", "Combined",
        "Close (₹)", "Amount (₹)", "Qty", "Reason"
    ])

    out = [
        [
            s["stock"], s["fundGrade"], s["techGrade"],
            s["fundScore"], s["techScore"], round(s["combined"], 1),
            s["close"], s["amount"], s["qty"], s["reason"]
        ]
        for s in final_picks
    ]

    sip_sheet.append_rows(out)

    for s in final_picks:
        sip_history_sheet.append_row([today_str, s["stock"]])

    print("✅ Smart SIP allocation generated successfully")


# ================= RUN =================
if __name__ == "__main__":
    monthly_sip_picker()