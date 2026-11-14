from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.location_schedule import (
    LocationScheduleCreate,
    LocationScheduleUpdate,
    LocationScheduleResponse,
    LocationScheduleListResponse,
)
from app.api.deps import (
    require_viewer,
    require_location_admin,
)
from app.services import location_schedule_service

router = APIRouter(prefix="/locations/{location_id}/schedules", tags=["Location Schedules"])


@router.get(
    "",
    response_model=LocationScheduleListResponse,
    summary="Retrieve weekly schedules for a location",
    description="Retrieve all weekly operational schedules configured for a location. Timezone-aware.",
)
def get_location_schedules(
    location_id: int,
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
) -> LocationScheduleListResponse:
    return location_schedule_service.get_location_schedules(
        db=db, user=current_user, location_id=location_id
    )


@router.post(
    "",
    response_model=LocationScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or configure a daily schedule",
    description="Configure daily operating hours for a location. Enforces unique day per location.",
)
def create_schedule(
    location_id: int,
    data: LocationScheduleCreate,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> LocationScheduleResponse:
    return location_schedule_service.create_location_schedule(
        db=db, user=current_user, location_id=location_id, data=data
    )


@router.get(
    "/{day}",
    response_model=LocationScheduleResponse,
    summary="Retrieve a single day's schedule",
    description="Retrieve schedule for a given day (0-6 or name like 'Monday').",
)
def get_day_schedule(
    location_id: int,
    day: str,
    current_user: Annotated[User, Depends(require_viewer)],
    db: Annotated[Session, Depends(get_db)],
) -> LocationScheduleResponse:
    return location_schedule_service.get_day_schedule(
        db=db, user=current_user, location_id=location_id, day_spec=day
    )


@router.patch(
    "/{day}",
    response_model=LocationScheduleResponse,
    summary="Update a single day's schedule",
    description="Update open time, close time, working day flag, or grace minutes for a given day.",
)
def update_day_schedule(
    location_id: int,
    day: str,
    data: LocationScheduleUpdate,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> LocationScheduleResponse:
    return location_schedule_service.update_day_schedule(
        db=db, user=current_user, location_id=location_id, day_spec=day, data=data
    )


@router.delete(
    "/{day}",
    summary="Delete a daily schedule",
    description="Remove a configured daily schedule entry.",
)
def delete_day_schedule(
    location_id: int,
    day: str,
    current_user: Annotated[User, Depends(require_location_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return location_schedule_service.delete_day_schedule(
        db=db, user=current_user, location_id=location_id, day_spec=day
    )

