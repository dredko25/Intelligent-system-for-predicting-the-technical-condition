# from fastapi import FastAPI
# from fastapi.staticfiles import StaticFiles
# from backend.app.routers import auth, web, live, export
# from backend.app.services.auth import NotAuthenticatedException

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from backend.app.database import engine, Base
from backend.app.routers import web, live, auth, export
from backend.app.services.auth import NotAuthenticatedException
import os

app = FastAPI(title="Система прогнозування технічного стану обладнання")

# підключаємо routers
app.include_router(auth.router)
app.include_router(live.router) 
app.include_router(web.router)
app.include_router(export.router)

# статичні файли
# app.mount("/static", StaticFiles(directory="backend/app/templates/static"), name="static")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.exception_handler(NotAuthenticatedException)
async def auth_exception_handler(request: Request, exc: NotAuthenticatedException):
    """
    Якщо користувач не авторизований:
    1. Для API запитів -> Повертаємо 401 JSON.
    2. Для звичайних сторінок -> Перенаправляємо на /login.
    """
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=401, 
            content={"detail": "Not authenticated"}
        )
    
    # Редірект на логін
    return RedirectResponse(url="/login")

