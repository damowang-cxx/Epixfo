from app.core.database import SessionLocal
from app.services.monitor_service import MonitorService


async def run_due_waybills(limit: int = 50) -> int:
    db = SessionLocal()
    try:
        return await MonitorService(db).run_due_waybills(limit=limit)
    finally:
        db.close()
