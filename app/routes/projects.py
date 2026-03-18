"""Project CRUD, title update, and main-file selection."""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from database import (
    create_project, list_projects, get_project, update_project, delete_project,
    list_share_links, list_project_files, get_project_file_by_name, get_db,
)
from auth import require_user

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectBody(BaseModel):
    title: str | None = None
    source: str | None = None


class TitleBody(BaseModel):
    title: str


class MainFileBody(BaseModel):
    main_file: str


@router.get("")
async def list_(request: Request):
    user = require_user(request)
    return list_projects(user["id"])


@router.post("")
async def create(request: Request, body: ProjectBody):
    user = require_user(request)
    title = body.title or "Untitled Project"
    source = body.source or ""
    return create_project(user["id"], title, source)


@router.get("/{project_id}")
async def get(project_id: str, request: Request):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")
    links = list_share_links(project_id)
    files = list_project_files(project_id)
    return {**project, "share_links": links, "files": files}


@router.put("/{project_id}")
async def update(project_id: str, request: Request, body: ProjectBody):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")
    return update_project(project_id, title=body.title, source=body.source)


@router.delete("/{project_id}")
async def delete(project_id: str, request: Request):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")
    delete_project(project_id)
    return {"ok": True}


@router.patch("/{project_id}/title")
async def update_title(project_id: str, request: Request, body: TitleBody):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")
    updated = update_project(project_id, title=body.title)
    return {"ok": True, "title": updated["title"]}


@router.patch("/{project_id}/main-file")
async def set_main_file(project_id: str, request: Request, body: MainFileBody):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")
    f = get_project_file_by_name(project_id, body.main_file)
    if not f:
        raise HTTPException(404, f"File '{body.main_file}' not found in project")
    db = get_db()
    db.execute("UPDATE projects SET main_file = ? WHERE id = ?", (body.main_file, project_id))
    db.commit()
    db.close()
    return {"ok": True, "main_file": body.main_file}
