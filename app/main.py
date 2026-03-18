"""LaTeX Render API — application entry point."""

import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from database import init_db
from ratelimit import limiter
from routes import auth, projects, files, render, sharing, storage

# ─── App setup ───

app = FastAPI(title="LaTeX Render API")
init_db()
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"error": "Rate limit exceeded. Try again later."})

# ─── Register routers ───

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(files.router)
app.include_router(render.router)
app.include_router(sharing.router)
app.include_router(storage.router)

# ─── Start background tasks ───

storage.start_cleanup_scheduler()

# ─── Core routes ───

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "latex-renderer"}


@app.get("/")
async def root():
    """Serve the web interface."""
    return HTMLResponse(content=_get_index_html())


@app.get("/api")
async def api_info():
    return {"service": "LaTeX Render API", "version": "1.0.0"}


# ─── SPA catch-all: serve index.html for frontend routes ───

_html_cache = None

def _get_index_html():
    global _html_cache
    if _html_cache is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(script_dir, "static", "index.html"), "r", encoding="utf-8") as f:
            _html_cache = f.read()
    return _html_cache

@app.get("/projects")
@app.get("/projects/{path:path}")
@app.get("/shared/{path:path}")
async def spa_catch_all(path: str = ""):
    return HTMLResponse(content=_get_index_html())


# ─── Static files ───

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
