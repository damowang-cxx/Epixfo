from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.tasks.scheduler import monitor_scheduler


def create_app() -> FastAPI:
    app = FastAPI(
        title="Epixfo Waybill Monitoring API",
        version="0.1.0",
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.on_event("startup")
    async def start_scheduler() -> None:
        monitor_scheduler.start()

    @app.on_event("shutdown")
    async def stop_scheduler() -> None:
        await monitor_scheduler.stop()

    return app


app = create_app()
