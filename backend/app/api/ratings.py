from fastapi import APIRouter, HTTPException, status

from backend.app.models.rating import (
    Rating,
    RatingBulkCreate,
    RatingBulkResult,
    RatingCreate,
    RatingImportPayload,
    RatingImportResult,
    RatingSummary,
    RatingWorkflow,
)
from backend.app.services import rating_service


router = APIRouter(prefix="/ratings", tags=["ratings"])


@router.get("", response_model=list[Rating])
def list_ratings() -> list[Rating]:
    return rating_service.list_ratings()


@router.post("", response_model=Rating, status_code=status.HTTP_201_CREATED)
def add_rating(payload: RatingCreate) -> Rating:
    return rating_service.add_rating(payload)


@router.post("/bulk", response_model=RatingBulkResult, status_code=status.HTTP_201_CREATED)
def add_bulk_ratings(payload: RatingBulkCreate) -> RatingBulkResult:
    return rating_service.add_bulk_ratings(payload)


@router.post("/import", response_model=RatingImportResult, status_code=status.HTTP_201_CREATED)
def import_ratings(payload: RatingImportPayload) -> RatingImportResult:
    return rating_service.import_ratings(payload)


@router.get("/summary", response_model=RatingSummary)
def get_rating_summary() -> RatingSummary:
    return rating_service.get_rating_summary()


@router.get("/workflow", response_model=RatingWorkflow)
def get_rating_workflow() -> RatingWorkflow:
    return rating_service.get_rating_workflow()


@router.get("/{symbol}", response_model=Rating)
def get_rating_by_symbol(symbol: str) -> Rating:
    rating = rating_service.get_rating_by_symbol(symbol)
    if rating is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")
    return rating


@router.delete("/{rating_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rating(rating_id: str) -> None:
    deleted = rating_service.delete_rating(rating_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")
