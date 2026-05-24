# Cloud Automation Setup (GitHub Actions)

This enables cloud schedules even when your laptop is OFF.

## Workflow file

- `.github/workflows/portfolio-cloud-cron.yml`

## Schedules configured (UTC)

- Daily analysis: `15 9 * * *` (2:45 PM IST)
- Weekly ETF SIP: `30 9 * * 4` (Thursday 3:00 PM IST)
- Monthly SIP: `30 9 5 * *` (5th, 3:00 PM IST)

## 1) Add GitHub repository secrets

In GitHub repo -> `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

Required:

1. `RENDER_API_BASE`
   - Value: `https://portfolio-manager-492m.onrender.com/api`

Optional (for cloud holdings import in manual run):

2. `STOCK_HOLDINGS_FILE_URL`
   - Public/temporary download URL to latest stock holdings file
3. `ETF_HOLDINGS_FILE_URL`
   - Public/temporary download URL to latest ETF holdings CSV

Optional (for Telegram fetch endpoint in manual run):

4. `TELEGRAM_API_ID`
5. `TELEGRAM_API_HASH`
6. `TG_GROUP_IDS`
   - Example: `2088923066,1487114286,1820276185`

## 2) Push workflow to GitHub

```powershell
cd C:\investment\portfolio-manager
git add .github/workflows/portfolio-cloud-cron.yml ops/CLOUD_AUTOMATION_SETUP.md
git commit -m "Add cloud cron automation workflow"
git push
```

## 3) Validate first run (manual)

1. GitHub -> `Actions` -> `Portfolio Cloud Cron` -> `Run workflow`
2. Keep defaults first (`run_holdings_import=false`, `run_research_fetch=false`)
3. Confirm job success.

## 4) Optional: manual cloud holdings refresh

If you have URL sources configured in secrets:

1. `Run workflow`
2. Set `run_holdings_import=true`
3. Run

## Honest limitation

- Fully automatic cloud holdings import requires cloud-accessible holdings source (broker API or hosted file URL).
- Fully automatic Telegram fetch requires a durable authenticated Telegram session in cloud runtime.
- Current workflow already gives cloud scheduling for analytics + summary regeneration.
