from fastapi import APIRouter

from app.api.routes import alerts, auth, bulk_import, dashboard, employees, health, platforms, queue, requests, allocation_cleanup


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(employees.router, prefix="/employees", tags=["employees"])
api_router.include_router(platforms.router, prefix="/platforms", tags=["platforms"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(requests.router, prefix="/requests", tags=["requests"])
api_router.include_router(queue.router, prefix="/queue", tags=["queue"])
api_router.include_router(bulk_import.router, prefix="/bulk-import", tags=["bulk-import"])
api_router.include_router(allocation_cleanup.router, prefix="/allocation-cleanup", tags=["allocation-cleanup"])
