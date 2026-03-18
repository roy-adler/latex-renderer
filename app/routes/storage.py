"""Legacy render endpoint (ZIP upload → PDF) and file storage/download."""

import base64, io, os, shutil, pathlib, uuid, time, threading
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from latex import extract_zip_to_tmp, detect_entrypoint, compile_latexmk
from ratelimit import limiter

router = APIRouter(tags=["storage"])

# File storage configuration
STORAGE_DIR = "/tmp/latex_storage"
STORAGE_URL = "/files"
FILE_EXPIRY_HOURS = 48

os.makedirs(STORAGE_DIR, exist_ok=True)

# In-memory storage for file metadata
file_metadata = {}


def _generate_unique_id() -> str:
    return str(uuid.uuid4())


def _cleanup_expired_files():
    current_time = datetime.now()
    expired_ids = [fid for fid, meta in file_metadata.items() if current_time > meta["expires_at"]]
    for file_id in expired_ids:
        try:
            meta = file_metadata[file_id]
            if os.path.exists(meta["storage_path"]):
                os.remove(meta["storage_path"])
            del file_metadata[file_id]
        except Exception as e:
            print(f"Error cleaning up file {file_id}: {e}")


def start_cleanup_scheduler():
    def run():
        while True:
            _cleanup_expired_files()
            time.sleep(3600)
    threading.Thread(target=run, daemon=True).start()


@router.post("/render")
@limiter.limit("10/minute")
async def render(
    request: Request,
    project: UploadFile = File(...),
    engine: str = Form("latexmk"),
    entrypoint: str | None = Form(None),
    runs: int = Form(3),
):
    if engine != "latexmk":
        raise HTTPException(400, "engine must be 'latexmk'.")

    zip_bytes = await project.read()
    workdir = extract_zip_to_tmp(zip_bytes)

    try:
        entry = detect_entrypoint(workdir, entrypoint)
        pdf_path, log = compile_latexmk(entry, runs)

        if not pathlib.Path(pdf_path).exists():
            return JSONResponse(
                status_code=422,
                content={"error": "Compilation failed", "log": log[-20000:]},
            )

        with open(pdf_path, "rb") as f:
            pdf_content = f.read()

        file_id = _generate_unique_id()
        storage_path = os.path.join(STORAGE_DIR, f"{file_id}.pdf")
        shutil.copy2(pdf_path, storage_path)

        file_metadata[file_id] = {
            "filename": f"latex-{file_id}.pdf",
            "storage_path": storage_path,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(hours=FILE_EXPIRY_HOURS),
            "size": os.path.getsize(storage_path),
        }

        return {
            "success": True,
            "message": "LaTeX compilation successful",
            "file_id": file_id,
            "filename": file_metadata[file_id]["filename"],
            "download_url": f"{STORAGE_URL}/{file_id}",
            "expires_at": file_metadata[file_id]["expires_at"].isoformat(),
            "size_bytes": len(pdf_content),
        }
    except Exception as e:
        shutil.rmtree(workdir, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@router.get(f"{STORAGE_URL}/{{file_id}}")
async def download_file(file_id: str):
    if file_id not in file_metadata:
        raise HTTPException(404, "File not found or expired")

    meta = file_metadata[file_id]

    if datetime.now() > meta["expires_at"]:
        try:
            if os.path.exists(meta["storage_path"]):
                os.remove(meta["storage_path"])
            del file_metadata[file_id]
        except Exception:
            pass
        raise HTTPException(410, "File has expired and been removed")

    if not os.path.exists(meta["storage_path"]):
        del file_metadata[file_id]
        raise HTTPException(404, "File not found on disk")

    return StreamingResponse(
        open(meta["storage_path"], "rb"),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{meta["filename"]}"',
            "Content-Length": str(meta["size"]),
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )
