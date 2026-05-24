from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from backend.app.api.routes import api_router
from backend.app.database import init_database

app = FastAPI(title="Portfolio Manager API")

default_origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://portfolio-ai-assistant-20260524.netlify.app",
]
origins_env = os.getenv("CORS_ORIGINS", "").strip()
allow_origins = [o.strip() for o in origins_env.split(",") if o.strip()] if origins_env else default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.on_event("startup")
def on_startup() -> None:
    init_database()


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "portfolio-manager-api"}
