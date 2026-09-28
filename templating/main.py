from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse
from core.config import ROOT
from db.session import engine
from api.handlers import router

@asynccontextmanager
async def lifespan(app):
    yield
    await engine.dispose()

app = FastAPI(title="SMART TRAFFIC", lifespan=lifespan)
# Корень — техническое перенаправление; бизнес-контроллеров ровно шесть.
@app.middleware("http")
async def root_redirect(request, call_next):
    if request.url.path == "/":
        return RedirectResponse("/feed", status_code=307)
    return await call_next(request)

app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
