import logging
from zoneinfo import ZoneInfo
from datetime import datetime, time
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.location_schedule import LocationSchedule
from app.models.location import Location
from app.models.user import User
from app.schemas.location_schedule import (
    LocationScheduleCreate,
    LocationScheduleUpdate,
    LocationScheduleResponse,
    LocationScheduleListResponse,
    INT_TO_DAY_NAME,
    parse_day_of_week,
)
from app.core.permissions import SystemRole, has_minimum_role
from app.api.deps import has_location_access

logger = logging.getLogger(__name__)


def format_schedule_response(schedule: LocationSchedule) -> LocationScheduleResponse:
    """Format LocationSchedule into LocationScheduleResponse with day name and overnight flag."""
    is_overnight = False
    if schedule.open_time and schedule.close_time:
        is_overnight = schedule.close_time < schedule.open_time

    return LocationScheduleResponse(
        id=schedule.id,
        location_id=schedule.location_id,
        day_of_week=schedule.day_of_week,
        day_name=INT_TO_DAY_NAME.get(schedule.day_of_week, f"Day {schedule.day_of_week}"),
        is_working_day=schedule.is_working_day,
        open_time=schedule.open_time,
        close_time=schedule.close_time,
        after_hours_grace_minutes=schedule.after_hours_grace_minutes,
        is_overnight=is_overnight,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


def get_location_schedules(
    db: Session,
    user: User,
    location_id: int,
) -> LocationScheduleListResponse:
    """
    Retrieve all weekly schedules configured for a location.
    Requires viewer access or higher to the location.
    """
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID {location_id} not found.",
        )

    if not has_location_access(db=db, user=user, location_id=location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for location ID {location_id}.",
        )

    schedules = (
        db.query(LocationSchedule)
        .filter(LocationSchedule.location_id == location_id)
        .order_by(LocationSchedule.day_of_week.asc())
        .all()
    )

    return LocationScheduleListResponse(
        location_id=location.id,
        location_name=location.name,
        timezone=location.timezone,
        schedules=[format_schedule_response(s) for s in schedules],
    )


def get_day_schedule(
    db: Session,
    user: User,
    location_id: int,
    day_spec: str | int,
) -> LocationScheduleResponse:
    """
    Retrieve one day's schedule for a location.
    Accepts day_spec as integer (0-6) or day name (e.g. 'Monday').
    """
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID {location_id} not found.",
        )

    if not has_location_access(db=db, user=user, location_id=location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for location ID {location_id}.",
        )

    day_num = parse_day_of_week(day_spec)
    schedule = (
        db.query(LocationSchedule)
        .filter(
            LocationSchedule.location_id == location_id,
            LocationSchedule.day_of_week == day_num,
        )
        .first()
    )
    if not schedule:
        day_str = INT_TO_DAY_NAME.get(day_num, str(day_num))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule for {day_str} (day {day_num}) is not configured for location ID {location_id}.",
        )

    return format_schedule_response(schedule)


def create_location_schedule(
    db: Session,
    user: User,
    location_id: int,
    data: LocationScheduleCreate,
) -> LocationScheduleResponse:
    """
    Create a daily operational schedule entry for a location.
    - Requires location_admin authority for this location or super_admin.
    - Rejects duplicate schedule for the same location and day (HTTP 409).
    - Enforces grace period >= 0.
    """
    if not has_minimum_role(user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to manage schedules.",
        )

    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID {location_id} not found.",
        )

    if not has_location_access(db=db, user=user, location_id=location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized to manage schedules for location ID {location_id}.",
        )

    # Check duplicate
    existing = (
        db.query(LocationSchedule)
        .filter(
            LocationSchedule.location_id == location_id,
            LocationSchedule.day_of_week == data.day_of_week,
        )
        .first()
    )
    if existing:
        day_str = INT_TO_DAY_NAME.get(data.day_of_week, str(data.day_of_week))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Schedule for {day_str} (day {data.day_of_week}) is already configured for location ID {location_id}. Use PATCH to update.",
        )

    if data.after_hours_grace_minutes < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="after_hours_grace_minutes must be greater than or equal to 0.",
        )

    schedule = LocationSchedule(
        location_id=location_id,
        day_of_week=data.day_of_week,
        is_working_day=data.is_working_day,
        open_time=data.open_time,
        close_time=data.close_time,
        after_hours_grace_minutes=data.after_hours_grace_minutes,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    logger.info("Created schedule for location ID %d, day %d", location_id, schedule.day_of_week)
    return format_schedule_response(schedule)


def update_day_schedule(
    db: Session,
    user: User,
    location_id: int,
    day_spec: str | int,
    data: LocationScheduleUpdate,
) -> LocationScheduleResponse:
    """
    Update a daily operational schedule entry for a location.
    - Requires location_admin authority for this location or super_admin.
    - Validates grace minutes >= 0.
    """
    if not has_minimum_role(user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to update schedules.",
        )

    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID {location_id} not found.",
        )

    if not has_location_access(db=db, user=user, location_id=location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for location ID {location_id}.",
        )

    day_num = parse_day_of_week(day_spec)
    schedule = (
        db.query(LocationSchedule)
        .filter(
            LocationSchedule.location_id == location_id,
            LocationSchedule.day_of_week == day_num,
        )
        .first()
    )
    if not schedule:
        day_str = INT_TO_DAY_NAME.get(day_num, str(day_num))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule for {day_str} (day {day_num}) not found for location ID {location_id}.",
        )

    if data.is_working_day is not None:
        schedule.is_working_day = data.is_working_day

    if data.open_time is not None:
        schedule.open_time = data.open_time

    if data.close_time is not None:
        schedule.close_time = data.close_time

    if data.after_hours_grace_minutes is not None:
        if data.after_hours_grace_minutes < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="after_hours_grace_minutes must be greater than or equal to 0.",
            )
        schedule.after_hours_grace_minutes = data.after_hours_grace_minutes

    if schedule.open_time is not None and schedule.close_time is not None:
        if schedule.open_time == schedule.close_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="open_time and close_time cannot be identical.",
            )

    db.commit()
    db.refresh(schedule)
    logger.info("Updated schedule for location ID %d, day %d", location_id, schedule.day_of_week)
    return format_schedule_response(schedule)


def delete_day_schedule(
    db: Session,
    user: User,
    location_id: int,
    day_spec: str | int,
) -> dict:
    """
    Delete a daily schedule entry for a location.
    - Requires location_admin authority for this location or super_admin.
    """
    if not has_minimum_role(user.system_role, SystemRole.LOCATION_ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location administrative privileges required to delete schedules.",
        )

    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID {location_id} not found.",
        )

    if not has_location_access(db=db, user=user, location_id=location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are not authorized for location ID {location_id}.",
        )

    day_num = parse_day_of_week(day_spec)
    schedule = (
        db.query(LocationSchedule)
        .filter(
            LocationSchedule.location_id == location_id,
            LocationSchedule.day_of_week == day_num,
        )
        .first()
    )
    if not schedule:
        day_str = INT_TO_DAY_NAME.get(day_num, str(day_num))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule for {day_str} (day {day_num}) not found for location ID {location_id}.",
        )

    db.delete(schedule)
    db.commit()
    logger.info("Deleted schedule for location ID %d, day %d", location_id, day_num)
    return {"message": f"Schedule for {INT_TO_DAY_NAME.get(day_num, str(day_num))} successfully deleted."}

