from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from api.errors import http_error, validation_error, server_error
from fastapi.staticfiles import StaticFiles
from core.config import ROOT
from db.session import engine
from api.smart_devices import router
from api.users import router as users_router
from api.smart_devices_pages import router as pages_router
from core.current_user import get_sessions

@asynccontextmanager
async def lifespan(app):
    try:
        yield
    finally:
        await get_sessions().aclose()
        await engine.dispose()

app = FastAPI(title="SMART TRAFFIC", version="4.0", description="ЛР4: услуги (умные устройства), регистрация и cookie-сессии Redis.", lifespan=lifespan, redirect_slashes=False, exception_handlers={
    HTTPException: http_error,
    RequestValidationError: validation_error,
    Exception: server_error,
})
# Корень показывает ленту без HTTP-перенаправления.
@app.middleware("http")
async def root_redirect(request, call_next):
    if request.url.path == "/":
        request.scope["path"] = "/smart_devices/feed"
        request.scope["raw_path"] = b"/smart_devices/feed"
    return await call_next(request)

app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
# OpenAPI также не обещает JSON-тело для ошибок.
error_responses = {401: {"description": "Требуется сессия"}, 403: {"description": "Действие запрещено"}, 404: {"description": "Не найдено или некорректный запрос"}, 503: {"description": "Redis недоступен"}}
app.include_router(router, responses=error_responses)
app.include_router(users_router, responses=error_responses)
app.include_router(pages_router)

# FastAPI автоматически добавляет ответ валидации; контракт ЛР разрешает
# пустой 404 вместо 422; ЛР4 также использует 401/503.
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
        for path in schema["paths"].values():
            for operation in path.values():
                if isinstance(operation, dict) and "responses" in operation:
                    operation["responses"] = {code: value for code, value in operation["responses"].items()
                                              if code in {"200", "201", "401", "403", "404", "503"}}
        for path in ("/api/smart_devices", "/api/smart_devices/feed"):
            operation = schema["paths"][path]["get"]
            operation["security"].append({})
            operation["responses"].pop("401", None)
            operation["responses"].pop("503", None)
        for path in ("/api/users", "/api/users/login", "/api/users/logout"):
            schema["paths"][path]["post"].pop("security", None)
        app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
