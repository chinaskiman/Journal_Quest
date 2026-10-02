"""TradeQuest API - FastAPI application entry point."""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS, PROJECT_ROOT
from .db import Base, SessionLocal, engine
from .importer import ensure_imported_on_startup
from .routers import analytics, io, options, trades


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        report = ensure_imported_on_startup(db)
        if report:
            print(
                f"[tradequest] seeded {report.trades_imported} trades and "
                f"{report.options_imported} option values from the workbook",
                file=sys.stderr,
            )
    yield


app = FastAPI(
    title="TradeQuest API",
    version="1.0.0",
    description="Trading journal - reaction based strategy",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_origin_regex=None,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trades.router)
app.include_router(options.router)
app.include_router(analytics.router)
app.include_router(io.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "TradeQuest API"}


# Serve the built frontend (after `npm run build` in /frontend) in one go.
_dist = PROJECT_ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
