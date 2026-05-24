import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import time

# ================= CONFIG =================
SPREADSHEET_NAME = "PortfolioAutomation"
SHEET_NAME = "Fundamentals"

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
def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("/opt/airflow/scripts/credentials.json", scope)
    client = gspread.authorize(creds)
    return client.open(SPREADSHEET_NAME).worksheet(SHEET_NAME)

# ================= SAFE NUMERIC =================
def safe_num(v):
    if v is None or v == "" or v == "NA":
        return None
    try:
        return float(str(v).replace(",", ""))
    except:
        return None

# ================= COLUMN LETTER =================
def column_letter(n):
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result

# ================= HEADER =================
def ensure_header(sh, headers, header_name):
    if header_name in headers:
        return headers.index(header_name)
    else:
        new_col = len(headers)
        sh.update_cell(1, new_col + 1, header_name)
        return new_col

# ================= MAIN FUNCTION =================
def update_fundamentals_scores_exact():

    sh = get_sheet()
    data = sh.get_all_values()

    headers = [str(h).strip() for h in data[0]]
    rows = data[1:]
    num_rows = len(rows)

    header_map = {h: i for i, h in enumerate(headers)}

    score_col = ensure_header(sh, headers, "Score")
    grade_col = ensure_header(sh, headers, "Fundamental Grade")
    comment_col = ensure_header(sh, headers, "Fundamental Comment")

    stock_col = header_map.get("Stock Name", -1)

    scores, grades, comments = [], [], []

    for r in range(num_rows):

        row = rows[r]
        stock_raw = row[stock_col]

        if not stock_raw:
            scores.append("")
            grades.append("")
            comments.append("")
            continue

        stock = normalize_stock_name(stock_raw)

        if stock != stock_raw:
            sh.update_cell(r + 2, stock_col + 1, stock)

        # ================= READ =================
        pe = safe_num(row[header_map.get("P/E", -1)])
        indpe = safe_num(row[header_map.get("Ind PE", -1)])
        pb = safe_num(row[header_map.get("CMP / BV", -1)])
        cmp_val = safe_num(row[header_map.get("CMP Rs.", -1)])
        iv = safe_num(row[header_map.get("IV Rs.", -1)])
        roe = safe_num(row[header_map.get("ROE 5Yr %", -1)])
        roce = safe_num(row[header_map.get("ROCE %", -1)])
        opm = safe_num(row[header_map.get("OPM %", -1)])
        sales = safe_num(row[header_map.get("Sales Var 5Yrs %", -1)])
        profit = safe_num(row[header_map.get("Profit Var 5Yrs %", -1)])
        eps_var = safe_num(row[header_map.get("EPS Var 5Yrs %", -1)])
        peg = safe_num(row[header_map.get("PEG", -1)])
        debt = safe_num(row[header_map.get("Debt / Eq", -1)])
        ic = safe_num(row[header_map.get("Int Coverage", -1)])
        cr = safe_num(row[header_map.get("Current ratio", -1)])
        prom = safe_num(row[header_map.get("Prom. Hold. %", -1)])
        pledge = safe_num(row[header_map.get("Pledged %", -1)])
        alt = safe_num(row[header_map.get("Altman Z Scr", -1)])
        fcf = safe_num(row[header_map.get("Free Cash Flow 5Yrs Rs.Cr.", -1)])
        payout = safe_num(row[header_map.get("Dividend Payout %", -1)])
        divy = safe_num(row[header_map.get("Div Yld %", -1)])
        ev = safe_num(row[header_map.get("EV / EBITDA", -1)])

        # ================= TMCV =================
        if stock == "TMCV":
            score = 0
            remarks = []
            improve = []

            if pe is not None and indpe is not None:
                if pe <= indpe * 0.5:
                    score += 30
                    remarks.append("Deep undervaluation vs Industry")
                elif pe <= indpe:
                    score += 20
                    remarks.append("Undervalued vs Industry")
                else:
                    improve.append("Not cheap vs Industry")

            if debt is not None:
                if debt < 0.5:
                    score += 10
                elif debt < 1:
                    score += 6
                else:
                    improve.append("High debt")

            if alt is not None:
                if alt >= 3:
                    score += 15
                    remarks.append("Strong balance sheet")
                else:
                    improve.append("Weak Altman Z")

            if pledge == 0:
                score += 5

            if cr is not None:
                if cr >= 1.5:
                    score += 10
                else:
                    improve.append("Weak liquidity")

            if prom is not None:
                if prom >= 50:
                    score += 10
                elif prom >= 40:
                    score += 6
                else:
                    improve.append("Low promoter holding")

            score = round((score / 80) * 100)
            score = max(0, min(100, score))

            grade = "Strong" if score >= 70 else "Moderate" if score >= 50 else "Weak"

            comment = ""
            if remarks:
                comment += "; ".join(remarks) + "; "
            if improve:
                comment += "Needs improvement: " + ", ".join(improve)

            scores.append(score)
            grades.append(grade)
            comments.append(comment)
            continue

        # ================= ORIGINAL LOGIC =================
        score = 0
        remarks = []
        improve = []

        if pe is not None and indpe is not None:
            if pe <= indpe * 0.8:
                score += 7
                remarks.append("Undervalued vs Industry")
            elif pe <= indpe * 1.1:
                score += 4
                remarks.append("Fair vs Industry")
            else:
                improve.append("High P/E vs Industry")

        if pb is not None and pb < 3:
            score += 4
            remarks.append("Low P/B")
        elif pb is not None:
            improve.append("High P/B")

        if cmp_val is not None and iv is not None:
            if cmp_val < iv:
                score += 4
                remarks.append("Trading below IV")
            else:
                improve.append("CMP > IV")

        if peg is not None:
            if peg <= 1:
                score += 5
                remarks.append("Reasonable PEG")
            elif peg > 2:
                improve.append("High PEG ratio")

        if roe is not None:
            if roe >= 20:
                score += 10
            elif roe >= 15:
                score += 6
            else:
                improve.append("Low ROE")

        if roce is not None:
            if roce >= 20:
                score += 8
            elif roce >= 12:
                score += 5
            else:
                improve.append("Low ROCE")

        if opm is not None:
            if opm >= 20:
                score += 7
            elif opm >= 12:
                score += 4
            else:
                improve.append("Weak OPM margins")

        if sales is not None:
            if sales >= 20:
                score += 6
            elif sales >= 10:
                score += 4
            else:
                improve.append("Weak Sales growth")

        if profit is not None:
            if profit >= 20:
                score += 6
            elif profit >= 10:
                score += 4
            else:
                improve.append("Weak Profit growth")

        if eps_var is not None:
            if eps_var < 20:
                score += 3
            elif eps_var > 50:
                improve.append("Volatile EPS growth")

        if debt is not None:
            if debt < 0.2:
                score += 6
            elif debt < 0.5:
                score += 4
            else:
                improve.append("High leverage")

        if ic is not None:
            if ic >= 5:
                score += 5
            elif ic >= 3:
                score += 3
            else:
                improve.append("Low Interest coverage")

        if cr is not None:
            if cr >= 2:
                score += 4
            elif cr >= 1.5:
                score += 2
            else:
                improve.append("Low Current Ratio")

        if prom is not None:
            if prom >= 60:
                score += 3
            elif prom >= 40:
                score += 2
            else:
                improve.append("Low Promoter Holding")

        if pledge is not None and pledge > 5:
            improve.append("High Promoter Pledge")

        if alt is not None:
            if alt >= 3:
                score += 5
            else:
                improve.append("Weak Altman Z")

        if fcf is not None:
            if fcf > 0:
                score += 5
            else:
                improve.append("Negative FCF")

        if ev is not None:
            if ev < 8:
                score += 3
            elif ev < 12:
                score += 2
            else:
                improve.append("High EV/EBITDA")

        if payout is not None and payout >= 20:
            score += 3

        if divy is not None and divy >= 2:
            score += 2

        score = max(0, min(100, round(score)))
        grade = "Strong" if score >= 70 else "Moderate" if score >= 50 else "Weak"

        comment = ""
        if remarks:
            comment += "; ".join(remarks) + "; "
        if improve:
            comment += "Needs improvement: " + ", ".join(improve)

        scores.append(score)
        grades.append(grade)
        comments.append(comment)

    # ================= WRITE =================
    start_row = 2
    end_row = num_rows + 1

    sh.update(f"{column_letter(score_col+1)}{start_row}:{column_letter(score_col+1)}{end_row}", [[s] for s in scores])
    sh.update(f"{column_letter(grade_col+1)}{start_row}:{column_letter(grade_col+1)}{end_row}", [[g] for g in grades])
    sh.update(f"{column_letter(comment_col+1)}{start_row}:{column_letter(comment_col+1)}{end_row}", [[c] for c in comments])

    print("🎉 Fundamentals scoring COMPLETE with detailed comments")

# ================= RUN =================
if __name__ == "__main__":
    update_fundamentals_scores_exact()