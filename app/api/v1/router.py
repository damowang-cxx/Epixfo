from fastapi import APIRouter

from app.api.v1 import (
    alerts,
    audit,
    auth,
    boards,
    boxes,
    carriers,
    consignees,
    monitor,
    prebookings,
    presence,
    user_preferences,
    users,
    warehouse_planner,
    warehouse_receipts,
    waybills,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(user_preferences.router)
api_router.include_router(waybills.router)
api_router.include_router(prebookings.router)
api_router.include_router(warehouse_planner.router)
api_router.include_router(boards.router)
api_router.include_router(boxes.router)
api_router.include_router(warehouse_receipts.router)
api_router.include_router(carriers.router)
api_router.include_router(consignees.router)
api_router.include_router(alerts.router)
api_router.include_router(audit.router)
api_router.include_router(presence.router)
api_router.include_router(monitor.router)
