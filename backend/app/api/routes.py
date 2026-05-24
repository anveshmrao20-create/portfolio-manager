from fastapi import APIRouter

from backend.app.api import assistant, analyst, fundamental, holdings_import, portfolio, ratings, research, settings, sip, technical


api_router = APIRouter(prefix="/api")
api_router.include_router(portfolio.router)
api_router.include_router(settings.router)
api_router.include_router(ratings.router)
api_router.include_router(analyst.router)
api_router.include_router(holdings_import.router)
api_router.include_router(technical.router)
api_router.include_router(fundamental.router)
api_router.include_router(sip.router)
api_router.include_router(research.router)
api_router.include_router(assistant.router)
