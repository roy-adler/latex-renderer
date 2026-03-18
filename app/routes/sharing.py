"""Share link management and shared project access."""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from database import (
    get_project, get_share_link, create_share_link, list_share_links, delete_share_link,
    list_project_files, get_project_file, update_project_file, update_project,
)
from auth import require_user

router = APIRouter(tags=["sharing"])


class ShareBody(BaseModel):
    access_level: str


class SharedUpdateBody(BaseModel):
    source: str


class FileUpdateBody(BaseModel):
    filename: str | None = None
    content: str | None = None


# ─── Owner share management ───

@router.post("/api/projects/{project_id}/share")
async def create_share(project_id: str, request: Request, body: ShareBody):
    user = require_user(request)
    project = get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(404, "Project not found")
    if body.access_level not in ("readonly", "contributor"):
        raise HTTPException(400, "access_level must be 'readonly' or 'contributor'")
    link = create_share_link(project_id, body.access_level)
    return {"link_id": link["id"], "access_level": link["access_level"], "created_at": link["created_at"]}


@router.delete("/api/share/{link_id}")
async def delete_share(link_id: str, request: Request):
    user = require_user(request)
    link = get_share_link(link_id)
    if not link or link["user_id"] != user["id"]:
        raise HTTPException(404, "Share link not found")
    delete_share_link(link_id)
    return {"ok": True}


# ─── Public shared access ───

@router.get("/api/shared/{link_id}")
async def get_shared(link_id: str):
    link = get_share_link(link_id)
    if not link:
        raise HTTPException(404, "Share link not found or expired")
    files = list_project_files(link["project_id"])
    project = get_project(link["project_id"])
    main_file = project["main_file"] if project else "main.tex"
    return {
        "project": {"id": link["project_id"], "title": link["title"], "source": link["source"], "main_file": main_file},
        "access_level": link["access_level"],
        "files": files,
    }


@router.get("/api/shared/{link_id}/files/{file_id}")
async def get_shared_file(link_id: str, file_id: str):
    link = get_share_link(link_id)
    if not link:
        raise HTTPException(404, "Share link not found")
    f = get_project_file(file_id)
    if not f or f["project_id"] != link["project_id"]:
        raise HTTPException(404, "File not found")
    return f


@router.put("/api/shared/{link_id}/files/{file_id}")
async def update_shared_file(link_id: str, file_id: str, body: FileUpdateBody):
    link = get_share_link(link_id)
    if not link:
        raise HTTPException(404, "Share link not found")
    if link["access_level"] != "contributor":
        raise HTTPException(403, "This link is readonly")
    f = get_project_file(file_id)
    if not f or f["project_id"] != link["project_id"]:
        raise HTTPException(404, "File not found")
    return update_project_file(file_id, content=body.content)


@router.put("/api/shared/{link_id}")
async def update_shared(link_id: str, body: SharedUpdateBody):
    link = get_share_link(link_id)
    if not link:
        raise HTTPException(404, "Share link not found")
    if link["access_level"] != "contributor":
        raise HTTPException(403, "This link is readonly")
    update_project(link["project_id"], source=body.source)
    return {"ok": True}
