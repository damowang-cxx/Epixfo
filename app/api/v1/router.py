from fastapi import APIRouter

from app.api.v1 import alerts, audit, auth, boxes, carriers, consignees, monitor, presence, users, waybills

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(waybills.router)
api_router.include_router(boxes.router)
api_router.include_router(carriers.router)
api_router.include_router(consignees.router)
api_router.include_router(alerts.router)
api_router.include_router(audit.router)
api_router.include_router(presence.router)
api_router.include_router(monitor.router)
