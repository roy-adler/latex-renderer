"""Rendering endpoints: project render, shared render, single-file render, cached render."""

import base64, json, os, shutil, tempfile, pathlib, time
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import JSONResponse
from database import (
    get_project, list_project_files, get_project_file,
    get_share_link, save_cached_render, get_cached_render,
)
from auth import require_user
from ratelimit import limiter
from latex import compile_latexmk, detect_entrypoint, parse_synctex, write_project_files_to_workdir

router = APIRouter(tags=["render"])


def _render_project_files(files_meta: list[dict], main_file: str, workdir_prefix: str) -> JSONResponse:
    """Shared logic: write files to tmp, compile, return PDF+synctex JSON."""
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
            return JSONResponse(
                status_code=422,
                content={"error": "Compilation failed", "log": log[-20000:]},
            )
        with open(pdf_path, "rb") as f:
            pdf_content = f.read()
        synctex_data = parse_synctex(entry, workdir)
        pdf_b64 = base64.b64encode(pdf_content).decode('ascii')
        t_end = time.monotonic()
        return JSONResponse(content={
            "pdf_base64": pdf_b64,
            "synctex": synctex_data,
            "timing": {
                "total": round(t_end - t_start, 2),
                "compile": round(t_compile_end - t_compile_start, 2),
                "postprocess": round(t_end - t_compile_end, 2),
            },
        })
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


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
            save_cached_render(
                project_id,
                body["pdf_base64"],
                json.dumps(body["synctex"]) if body.get("synctex") else None,
            )
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
    synctex = None
    if cached["synctex_json"]:
        try:
            synctex = json.loads(cached["synctex_json"])
        except (json.JSONDecodeError, TypeError):
            pass
    return JSONResponse(content={"pdf_base64": cached["pdf_base64"], "synctex": synctex})


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
    """Compile raw LaTeX source text and return PDF + synctex (used by Live Mode)."""
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
            return JSONResponse(
                status_code=422,
                content={"error": "Compilation failed", "log": log[-20000:]},
            )
        with open(pdf_path, "rb") as f:
            pdf_content = f.read()
        synctex_data = parse_synctex(entry, workdir)
        pdf_b64 = base64.b64encode(pdf_content).decode('ascii')
        t_end = time.monotonic()
        return JSONResponse(content={
            "pdf_base64": pdf_b64,
            "synctex": synctex_data,
            "timing": {
                "total": round(t_end - t_start, 2),
                "compile": round(t_compile_end - t_compile_start, 2),
                "postprocess": round(t_end - t_compile_end, 2),
            },
        })
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
