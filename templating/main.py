# main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import uvicorn
from api.handlers import router

app = FastAPI(title="SMART TRAFFIC — smart_devices")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/feed")


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
