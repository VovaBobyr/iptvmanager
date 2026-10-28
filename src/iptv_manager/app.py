from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from .api import playlist_router, router
from .config import settings
from .database import SessionLocal, create_schema
from .models import Channel, FavoriteGroup, HealthCheck, PlaylistSource
from .services.health_jobs import mark_interrupted_jobs

PACKAGE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_schema()
    mark_interrupted_jobs()
    yield


app = FastAPI(
    title="IPTV Manager",
    version="0.1.0",
    description="Self-hosted IPTV playlist management and health monitoring",
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(playlist_router)
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    with SessionLocal() as session:
        stats = {
            "channels": session.scalar(select(func.count()).select_from(Channel)) or 0,
            "active": session.scalar(
                select(func.count()).select_from(Channel).where(Channel.active)
            )
            or 0,
            "working": session.scalar(
                select(func.count()).select_from(Channel).where(Channel.health_status == "working")
            )
            or 0,
            "favorites": session.scalar(select(func.count()).select_from(FavoriteGroup)) or 0,
            "sources": session.scalar(select(func.count()).select_from(PlaylistSource)) or 0,
            "checks": session.scalar(select(func.count()).select_from(HealthCheck)) or 0,
        }
        recent = list(
            session.scalars(select(Channel).order_by(Channel.updated_at.desc()).limit(8))
        )
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"stats": stats, "recent": recent, "public_base_url": settings.public_base_url},
    )
