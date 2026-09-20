from contextlib import asynccontextmanager
from threading import BoundedSemaphore
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import ROOT, Settings
from app.db.session import make_engine
from app.repositories.place_repository import upsert_places, all_places
from app.services.demo_data import demo_places
from app.api import pages, recommendations, places, itineraries


def create_app(settings=None, engine=None):
    settings = settings or Settings.from_env()
    database = engine or make_engine(settings.database_path, memory=settings.mode == "demo")
    if settings.mode == "demo":
        upsert_places(database, demo_places())

    @asynccontextmanager
    async def lifespan(app):
        yield
        if engine is None:
            database.dispose()

    app = FastAPI(title="우리 개와 끝까지 함께", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = database
    app.state.planning_slots = BoundedSemaphore(2)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        try:
            if int(request.headers.get("content-length", "0")) > 2_000_000:
                return JSONResponse({"detail": "요청이 너무 큽니다."}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "잘못된 요청입니다."}, status_code=400)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.mount("/static", StaticFiles(directory=str(ROOT / "app/static")), name="static")
    for router in (pages.router, recommendations.router, places.router, itineraries.router):
        app.include_router(router)

    @app.get("/healthz")
    def health():
        return {"status": "ok", "version": "0.1.0", "mode": settings.mode,
                "places": len(all_places(database)), "routing_connected": bool(settings.mobility_key) or settings.mode == "demo"}

    return app


app = create_app()
