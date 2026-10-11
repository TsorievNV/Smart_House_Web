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

@asynccontextmanager
async def lifespan(app):
    yield
    await engine.dispose()

app = FastAPI(title="SMART TRAFFIC", lifespan=lifespan, redirect_slashes=False, exception_handlers={
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
error_responses = {403: {"description": "Forbidden"}, 404: {"description": "Not Found"}}
app.include_router(router, responses=error_responses)
app.include_router(users_router, responses=error_responses)
app.include_router(pages_router)

# FastAPI автоматически добавляет ответ валидации; контракт ЛР разрешает
# только 200/201/403/404, поэтому синхронизируем с ним документацию.
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        for path in schema["paths"].values():
            for operation in path.values():
                if isinstance(operation, dict) and "responses" in operation:
                    operation["responses"] = {code: value for code, value in operation["responses"].items()
                                              if code in {"200", "201", "403", "404"}}
        app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
