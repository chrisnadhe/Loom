"""
View (page) routes — render full HTML pages.
"""

import io
import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.models.config import Configuration
from app.models.database import engine as engine_db

router = APIRouter()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.get("/history", response_class=HTMLResponse)
async def list_history(request: Request):
    with Session(engine_db) as session:
        statement = (
            select(Configuration)
            .order_by(Configuration.created_at.desc())
            .limit(100)
        )
        history = session.exec(statement).all()
    return templates.TemplateResponse(request, "history.html", {"history": history})


@router.get("/templates", response_class=HTMLResponse)
async def list_templates(request: Request):
    return templates.TemplateResponse(request, "templates.html")


@router.get("/download", response_class=HTMLResponse)
async def download_page(request: Request):
    return templates.TemplateResponse(request, "download.html")


@router.get("/history/{config_id}/download")
async def download_history_config(config_id: int):
    """Download a single config from history as a .txt file."""
    with Session(engine_db) as session:
        config = session.get(Configuration, config_id)
    if not config:
        return HTMLResponse('<div class="p-4 text-red-500">Config not found.</div>', status_code=404)

    content_bytes = config.generated_content.encode("utf-8")
    return StreamingResponse(
        io.BytesIO(content_bytes),
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename={config.device_name}.txt"
        },
    )
