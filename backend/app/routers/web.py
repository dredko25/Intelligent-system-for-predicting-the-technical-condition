# backend/app/routers/web.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from backend.app.services.auth import allow_any_staff
import os

router = APIRouter(tags=["Web"])

current_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(current_dir, "..", "templates")
templates = Jinja2Templates(directory=templates_dir)

@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    user = Depends(allow_any_staff) # Авторизація
):
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request, 
            "message": "Система моніторингу",
            "user": user
        }
    )

@router.get("/charts", response_class=HTMLResponse)
async def charts_page(
    request: Request,
    user = Depends(allow_any_staff) # Авторизація
):
    return templates.TemplateResponse(
        "charts.html", 
        {
            "request": request,
            "message": "Графіки",
            "user": user
        }
    )