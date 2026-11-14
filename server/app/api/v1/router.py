from fastapi import APIRouter
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.locations import router as locations_router
from app.api.v1.endpoints.departments import router as departments_router
from app.api.v1.endpoints.roles import router as roles_router
from app.api.v1.endpoints.employees import router as employees_router
from app.api.v1.endpoints.cameras import router as cameras_router
from app.api.v1.endpoints.zones import router as zones_router
from app.api.v1.endpoints.schedules import router as schedules_router
from app.api.v1.endpoints.face_enrollments import router as face_enrollments_router
from app.api.v1.endpoints.events import router as events_router
from app.api.v1.endpoints.alerts import router as alerts_router

api_router = APIRouter()

# Register v1 feature routers
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(locations_router, prefix="/locations", tags=["Locations"])
api_router.include_router(departments_router, prefix="/departments", tags=["Departments"])
api_router.include_router(roles_router, prefix="/roles", tags=["Roles"])
api_router.include_router(employees_router, prefix="/employees", tags=["Employees"])
api_router.include_router(cameras_router, prefix="/cameras", tags=["Cameras"])
api_router.include_router(zones_router, prefix="/zones", tags=["Workstation Zones"])
api_router.include_router(schedules_router)
api_router.include_router(face_enrollments_router)
api_router.include_router(events_router, prefix="/events", tags=["Detection Events"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["Security & Operational Alerts"])
