"""Rendering endpoints: project render, shared render, single-file render, cached render, SyncTeX lookups."""

import base64, json, os, shutil, tempfile, pathlib, time, uuid, threading
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from database import (
    get_project, list_project_files, get_project_file,
    get_share_link, save_cached_render, get_cached_render,
)
from auth import require_user
from ratelimit import limiter
from latex import (
    compile_latexmk, detect_entrypoint,
    write_project_files_to_workdir, synctex_forward, synctex_inverse,
    has_synctex_file,
)

router = APIRouter(tags=["render"])

# ── SyncTeX workdir registry ──
# Maps synctex_token → {workdir, entry_name, created_at}
# Workdirs are kept alive for synctex lookups and cleaned up after MAX_AGE.
_synctex_sessions: dict[str, dict] = {}
_synctex_lock = threading.Lock()
_SYNCTEX_MAX_AGE = 600  # 10 minutes


def _cleanup_old_sessions():
    """Remove synctex sessions older than MAX_AGE."""
    now = time.monotonic()
    with _synctex_lock:
        expired = [k for k, v in _synctex_sessions.items() if now - v["created_at"] > _SYNCTEX_MAX_AGE]
        for k in expired:
            session = _synctex_sessions.pop(k)
            shutil.rmtree(session["workdir"], ignore_errors=True)


def _register_synctex_session(workdir: str, entry_name: str) -> str | None:
    """Register a workdir for synctex lookups. Returns a token, or None if no synctex data."""
    if not has_synctex_file(workdir, entry_name):
        shutil.rmtree(workdir, ignore_errors=True)
        return None
    _cleanup_old_sessions()
    token = uuid.uuid4().hex[:16]
    with _synctex_lock:
        _synctex_sessions[token] = {
            "workdir": workdir,
            "entry_name": entry_name,
            "created_at": time.monotonic(),
        }
    return token


def _get_synctex_session(token: str) -> dict | None:
    with _synctex_lock:
        session = _synctex_sessions.get(token)
    if not session:
        return None
    # Refresh timestamp on access
    session["created_at"] = time.monotonic()
    return session


def _render_project_files(files_meta: list[dict], main_file: str, workdir_prefix: str) -> JSONResponse:
    """Shared logic: write files to tmp, compile, return PDF + synctex token."""
    t_start = time.monotonic()
    workdir = tempfile.mkdtemp(prefix=workdir_prefix)
    try:
        all_files = [get_project_file(f["id"]) for f in files_meta]
        write_project_files_to_workdir(all_files, workdir)

        t_compile_start = time.monotonic()
        entry = detect_entrypoint(workdir, main_file)
        pdf_path, log = compile_latexmk(entry, 3)
        t_compile_end = time.monotonic()

        if not pathlib.Path(pdf_path).exists():
            shutil.rmtree(workdir, ignore_errors=True)
            return JSONResponse(
                status_code=422,
                content={"error": "Compilation failed", "log": log[-20000:]},
            )
        with open(pdf_path, "rb") as f:
            pdf_content = f.read()
        pdf_b64 = base64.b64encode(pdf_content).decode('ascii')

        # Register workdir for on-demand synctex lookups instead of parsing
        entry_name = pathlib.Path(entry).name
        synctex_token = _register_synctex_session(workdir, entry_name)
        # If no synctex file, workdir was already cleaned up by _register_synctex_session

        t_end = time.monotonic()
        return JSONResponse(content={
            "pdf_base64": pdf_b64,
            "synctex_token": synctex_token,
            "timing": {
                "total": round(t_end - t_start, 2),
                "compile": round(t_compile_end - t_compile_start, 2),
                "postprocess": round(t_end - t_compile_end, 2),
            },
        })
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise


@router.post("/api/projects/{project_id}/render")
@limiter.limit("10/minute")
async def render_project(project_id: str, request: Request):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")
    files = list_project_files(project_id)
    if not files:
        raise HTTPException(400, "Project has no files")

    main_file = project.get("main_file", "main.tex")
    response = _render_project_files(files, main_file, "latexapi_project_")

    # Cache the render for instant loading on next open
    if response.status_code == 200:
        try:
            body = json.loads(response.body)
            save_cached_render(project_id, body["pdf_base64"], None)
        except Exception:
            pass

    return response


@router.get("/api/projects/{project_id}/cached-render")
async def get_cached(project_id: str, request: Request):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")
    cached = get_cached_render(project_id)
    if not cached:
        return JSONResponse(status_code=204, content=None)
    return JSONResponse(content={"pdf_base64": cached["pdf_base64"], "synctex_token": None})


@router.post("/api/shared/{link_id}/render")
@limiter.limit("10/minute")
async def render_shared(link_id: str, request: Request):
    link = get_share_link(link_id)
    if not link:
        raise HTTPException(404, "Share link not found")
    project = get_project(link["project_id"])
    if not project:
        raise HTTPException(404, "Project not found")
    files = list_project_files(project["id"])
    if not files:
        raise HTTPException(400, "Project has no files")

    main_file = project.get("main_file", "main.tex")
    return _render_project_files(files, main_file, "latexapi_shared_")


@router.post("/render-source")
@limiter.limit("10/minute")
async def render_source(
    request: Request,
    source: str = Form(...),
    filename: str = Form("main.tex"),
    runs: int = Form(3),
):
    """Compile raw LaTeX source text and return PDF + synctex token (used by Live Mode)."""
    t_start = time.monotonic()
    workdir = tempfile.mkdtemp(prefix="latexapi_live_")
    entry = os.path.join(workdir, filename)
    try:
        with open(entry, "w", encoding="utf-8") as f:
            f.write(source)
        t_compile_start = time.monotonic()
        pdf_path, log = compile_latexmk(entry, runs)
        t_compile_end = time.monotonic()
        if not pathlib.Path(pdf_path).exists():
            shutil.rmtree(workdir, ignore_errors=True)
            return JSONResponse(
                status_code=422,
                content={"error": "Compilation failed", "log": log[-20000:]},
            )
        with open(pdf_path, "rb") as f:
            pdf_content = f.read()
        pdf_b64 = base64.b64encode(pdf_content).decode('ascii')

        entry_name = pathlib.Path(entry).name
        synctex_token = _register_synctex_session(workdir, entry_name)

        t_end = time.monotonic()
        return JSONResponse(content={
            "pdf_base64": pdf_b64,
            "synctex_token": synctex_token,
            "timing": {
                "total": round(t_end - t_start, 2),
                "compile": round(t_compile_end - t_compile_start, 2),
                "postprocess": round(t_end - t_compile_end, 2),
            },
        })
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise


# ── On-demand SyncTeX lookup endpoints ──

class SynctexForwardRequest(BaseModel):
    token: str
    file: str
    line: int

class SynctexInverseRequest(BaseModel):
    token: str
    page: int
    x: float
    y: float


@router.post("/api/synctex/forward")
async def synctex_forward_endpoint(req: SynctexForwardRequest):
    session = _get_synctex_session(req.token)
    if not session:
        raise HTTPException(404, "SyncTeX session expired or not found")

    result = synctex_forward(session["workdir"], session["entry_name"], req.file, req.line)
    if not result:
        return JSONResponse(content={"found": False})
    return JSONResponse(content={"found": True, **result})


@router.post("/api/synctex/inverse")
async def synctex_inverse_endpoint(req: SynctexInverseRequest):
    session = _get_synctex_session(req.token)
    if not session:
        raise HTTPException(404, "SyncTeX session expired or not found")

    result = synctex_inverse(session["workdir"], session["entry_name"], req.page, req.x, req.y)
    if not result:
        return JSONResponse(content={"found": False})
    return JSONResponse(content={"found": True, **result})
