"""Trade Quest v2 - FastAPI application entry point.

Strictly local-first: launch scripts always bind uvicorn to 127.0.0.1 (see
HOST in config.py).  No cloud services, no accounts, no telemetry, no
broker/market-data integration, no automatic P&L calculation, no Excel
auto-seeding (the v1 importer is intentionally NOT part of this app).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .config import CORS_ORIGINS, HOST
from .db import initialize_db
from .routers import checkins, dashboard, emotional, gamification, reviews
from .routers import settings as settings_router
from .routers import trades


@asynccontextmanager
async def lifespan(app: FastAPI):
    fresh = initialize_db()  # deterministic; never drops or overwrites data
    if fresh:
        import sys
        print("[tradequest-v2] created fresh empty database", file=sys.stderr)
    yield


app = FastAPI(
    title="Trade Quest v2 API",
    version="2.0.0",
    description="Gamified trading journal - local-first RPG progression",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=None,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trades.router)
app.include_router(reviews.router)
app.include_router(emotional.router)
app.include_router(checkins.router)
app.include_router(settings_router.router)
app.include_router(settings_router.preferences_router)
app.include_router(gamification.router)
app.include_router(dashboard.router)
app.include_router(dashboard.system_router)


# --- optional SPA static serving (Phase 3, additive and guarded) -----------------
# When the built frontend exists (frontend_v2/dist after `npm run build`),
# serve it from the same local port so a single .bat launches the whole app.
# Registered AFTER all API routes, so /api/* always wins.  When the build
# directory is absent the app behaves exactly as before (JSON API only).
def _mount_spa(application: FastAPI) -> None:
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

    spa = config.static_dir()
    if not (spa / "index.html").is_file():
        return
    assets = spa / "assets"
    if assets.is_dir():
        application.mount("/assets", StaticFiles(directory=assets), name="assets")

    @application.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        # Never shadow the API namespace: an unknown /api/* path must stay a
        # JSON 404 (a typo in a fetch URL should not silently return HTML).
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        # Serve real files only; everything else falls back to index.html
        # (client-side routing).  Resolve strictly inside the SPA dir.
        if full_path:
            candidate = (spa / full_path).resolve()
            try:
                candidate.relative_to(spa.resolve())
            except ValueError:
                return FileResponse(spa / "index.html")
            if candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(spa / "index.html")


_mount_spa(app)


if __name__ == "__main__":  # pragma: no cover - manual launch helper
    import uvicorn

    uvicorn.run("app2.main:app", host=HOST, port=8001, reload=False)
