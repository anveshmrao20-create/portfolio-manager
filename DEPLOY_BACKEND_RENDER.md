# Deploy Backend to Render (Beginner Guide)

This replaces the temporary Cloudflare tunnel with a stable public API URL.

## 1) Push project to GitHub

1. Open terminal in `C:\investment\portfolio-manager`
2. Run:

```powershell
git add .
git commit -m "Prepare backend for Render deployment"
git push
```

## 2) Create Render web service

1. Open [Render Dashboard](https://dashboard.render.com)
2. Click `New +` -> `Web Service`
3. Connect your GitHub repo and select `portfolio-manager`
4. Render should detect `render.yaml` automatically
5. Click `Create Web Service`

## 3) Set required environment variables

In Render service -> `Environment` add:

1. `TELEGRAM_API_ID` = your Telegram API ID
2. `TELEGRAM_API_HASH` = your Telegram API hash
3. `CORS_ORIGINS` = `https://portfolio-ai-assistant-20260524.netlify.app`

Then click `Save, Rebuild and Deploy`.

## 4) Verify backend is live

After deploy, open:

```text
https://<your-render-service>.onrender.com/health
```

You should see:

```json
{"status":"ok","service":"portfolio-manager-api"}
```

## 5) Connect Netlify frontend to Render backend

1. Open `https://portfolio-ai-assistant-20260524.netlify.app`
2. Click `API`
3. Enter:

```text
https://<your-render-service>.onrender.com/api
```

4. Click `OK`
5. Hard refresh (`Ctrl + F5`)

## 6) Final check

Click quick prompts:
- `Today Update`
- `Weak Fundamentals`
- `ETF Rationale`

If all respond without fetch/CORS errors, deployment is complete.
