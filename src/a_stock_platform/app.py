from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

templates = Jinja2Templates(directory=Path("templates"))

app = FastAPI(title="China A-Share Analysis Platform")

@app.get("/")
def landing(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html", context={"title": "Home"})

@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
