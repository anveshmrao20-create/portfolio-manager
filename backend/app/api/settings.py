from fastapi import APIRouter

from backend.app.models.settings import GoalProjection, GoalSettings, GoalVerdict
from backend.app.services import settings_service


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/goal", response_model=GoalSettings)
def get_goal_settings() -> GoalSettings:
    return settings_service.get_goal_settings()


@router.put("/goal", response_model=GoalSettings)
def save_goal_settings(payload: GoalSettings) -> GoalSettings:
    return settings_service.save_goal_settings(payload)


@router.get("/goal/projection", response_model=GoalProjection)
def get_goal_projection() -> GoalProjection:
    return settings_service.get_goal_projection()


@router.get("/goal/verdict", response_model=GoalVerdict)
def get_goal_verdict() -> GoalVerdict:
    return settings_service.get_goal_verdict()
