import gspread
from oauth2client.service_account import ServiceAccountCredentials
import yfinance as yf

def get_client():
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)

def run():
    client = get_client()
    ss = client.open("PortfolioAutomation")
    sheet = ss.worksheet("ETF_Portfolio")
    data = sheet.get_all_values()

    for i in range(1, len(data)):
        try:
            etf = data[i][0]
            units = float(data[i][1])
            avg = float(data[i][2])

            df = yf.download(etf + ".NS", period="1d", progress=False)

            if df.empty or "Close" not in df:
                print(f"⚠️ No data for {etf}")
                continue

            price = df["Close"].iloc[-1]

            # 🔥 FIX: ensure scalar
            if hasattr(price, "item"):
                price = price.item()

            invested = units * avg
            current = units * price
            pnl = current - invested

            sheet.update(range_name=f"D{i+1}", values=[[round(invested, 2)]])
            sheet.update(range_name=f"E{i+1}", values=[[round(current, 2)]])
            sheet.update(range_name=f"F{i+1}", values=[[round(pnl, 2)]])

        except Exception as e:
            print(f"⚠️ Skipping row {i+1}: {e}")

    print("✅ ETF Portfolio Updated")

if __name__ == "__main__":
    run()