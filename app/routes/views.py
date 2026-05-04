import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.models.database import engine as engine_db
from app.models.config import Configuration
from sqlmodel import Session, select

router = APIRouter()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")

@router.get("/history", response_class=HTMLResponse)
async def list_history(request: Request):
    with Session(engine_db) as session:
        statement = select(Configuration).order_by(Configuration.created_at.desc()).limit(50)
        history = session.exec(statement).all()
    return templates.TemplateResponse(request, "history.html", {"history": history})

@router.get("/templates", response_class=HTMLResponse)
async def list_templates(request: Request):
    return templates.TemplateResponse(request, "templates.html")
