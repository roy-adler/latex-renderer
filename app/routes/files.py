"""Project file CRUD and ZIP upload/download."""

import base64, io, re, zipfile
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from database import (
    get_project, get_db,
    create_project_file, list_project_files, get_project_file,
    get_project_file_by_name, update_project_file, delete_project_file,
    delete_all_project_files,
)
from auth import require_user

router = APIRouter(prefix="/api/projects", tags=["files"])


class FileBody(BaseModel):
    filename: str
    content: str | None = ""


class FileUpdateBody(BaseModel):
    filename: str | None = None
    content: str | None = None


@router.get("/{project_id}/files")
async def list_files(project_id: str, request: Request):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")
    return list_project_files(project_id)


@router.post("/{project_id}/files")
async def create_file(project_id: str, request: Request, body: FileBody):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")
    existing = get_project_file_by_name(project_id, body.filename)
    if existing:
        raise HTTPException(409, f"File '{body.filename}' already exists")
    return create_project_file(project_id, body.filename, body.content or "")


@router.get("/{project_id}/files/{file_id}")
async def get_file(project_id: str, file_id: str, request: Request):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")
    f = get_project_file(file_id)
    if not f or f["project_id"] != project_id:
        raise HTTPException(404, "File not found")
    return f


@router.put("/{project_id}/files/{file_id}")
async def update_file(project_id: str, file_id: str, request: Request, body: FileUpdateBody):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")
    f = get_project_file(file_id)
    if not f or f["project_id"] != project_id:
        raise HTTPException(404, "File not found")
    if body.filename is not None and body.filename != f["filename"]:
        existing = get_project_file_by_name(project_id, body.filename)
        if existing:
            raise HTTPException(409, f"File '{body.filename}' already exists")
    return update_project_file(file_id, filename=body.filename, content=body.content)


@router.delete("/{project_id}/files/{file_id}")
async def delete_file(project_id: str, file_id: str, request: Request):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")
    f = get_project_file(file_id)
    if not f or f["project_id"] != project_id:
        raise HTTPException(404, "File not found")
    delete_project_file(file_id)
    return {"ok": True}


@router.post("/{project_id}/upload-zip")
async def upload_zip(project_id: str, request: Request, file: UploadFile = File(...)):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")

    zip_bytes = await file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            delete_all_project_files(project_id)
            for member in z.namelist():
                if member.endswith('/') or member.startswith('__MACOSX') or member.startswith('.'):
                    continue
                raw = z.read(member)
                try:
                    content = raw.decode('utf-8')
                    is_binary = False
                except UnicodeDecodeError:
                    content = base64.b64encode(raw).decode('ascii')
                    is_binary = True
                create_project_file(project_id, member, content, is_binary=is_binary)
    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid ZIP file")

    files = list_project_files(project_id)
    filenames = [f["filename"] for f in files]
    main_candidates = [fn for fn in filenames if fn.lower().endswith("main.tex") or fn.lower() == "main.tex"]
    if main_candidates:
        db = get_db()
        db.execute("UPDATE projects SET main_file = ? WHERE id = ?", (main_candidates[0], project_id))
        db.commit()
        db.close()

    return {"ok": True, "files": files}


@router.get("/{project_id}/download-zip")
async def download_zip(project_id: str, request: Request):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")

    files = list_project_files(project_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for fmeta in files:
            full_file = get_project_file(fmeta["id"])
            if full_file.get("is_binary"):
                z.writestr(full_file["filename"], base64.b64decode(full_file["content"]))
            else:
                z.writestr(full_file["filename"], full_file["content"])
    buf.seek(0)

    safe_title = re.sub(r'[^\w\-. ]', '_', project["title"])
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.zip"'},
    )
