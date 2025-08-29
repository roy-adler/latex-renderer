import io, os, shutil, tempfile, zipfile, subprocess, pathlib, json, uuid, time
from datetime import datetime, timedelta
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import threading

# FastAPI app
app = FastAPI(title="LaTeX Render API")

# File storage configuration
STORAGE_DIR = "/tmp/latex_storage"
STORAGE_URL = "/files"
FILE_EXPIRY_HOURS = 48

# Ensure storage directory exists
os.makedirs(STORAGE_DIR, exist_ok=True)

# In-memory storage for file metadata (in production, use a database)
file_metadata = {}

def _extract_zip_to_tmp(zip_bytes: bytes) -> str:
    workdir = tempfile.mkdtemp(prefix="latexapi_")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        z.extractall(workdir)
    return workdir

def _detect_entrypoint(workdir: str, explicit: str | None) -> str:
    if explicit:
        ep = pathlib.Path(workdir, explicit)
        if not ep.exists():
            raise HTTPException(400, f"Entrypoint '{explicit}' not found.")
        return str(ep)
    tex_files = list(pathlib.Path(workdir).rglob("*.tex"))
    if not tex_files:
        raise HTTPException(400, "No .tex files found in project.")
    # Prefer main.tex if present
    for cand in tex_files:
        if cand.name.lower() == "main.tex":
            return str(cand)
    if len(tex_files) == 1:
        return str(tex_files[0])
    raise HTTPException(400, "Multiple .tex files found; provide 'entrypoint'.")

def _run(cmd: list[str], cwd: str, timeout: int = 180) -> subprocess.CompletedProcess:
    # resource limits can be added via prlimit/ulimit in Docker
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
    )

def _compile_latexmk(entry: str, allow_shell_escape: bool, runs: int) -> tuple[str, str]:
    # latexmk will call pdflatex/xelatex/lualatex/bibtex/biber as needed
    # default to pdf mode; nonstop to produce logs even on errors
    shell = "-shell-escape" if allow_shell_escape else "-no-shell-escape"
    cmd = ["latexmk", "-pdf", "-interaction=nonstopmode", shell, "-halt-on-error", "-file-line-error", "-silent", "-f"]
    # Force pdflatex instead of XeLaTeX/LuaLaTeX
    cmd += ["-pdflatex=pdflatex %O %S"]
    # Limit passes
    os.environ["LATEXMK_MAX_REPEAT"] = str(max(1, min(10, runs)))
    
    print(f"DEBUG: Compiling with command: {' '.join(cmd)}")
    print(f"DEBUG: Working directory: {str(pathlib.Path(entry).parent)}")
    print(f"DEBUG: Entry point: {entry}")
    
    # First attempt: try normal compilation
    result = subprocess.run(cmd + [pathlib.Path(entry).name], cwd=pathlib.Path(entry).parent, capture_output=True, text=True)
    
    # If compilation fails, try to install missing packages with tlmgr
    if result.returncode != 0:
        print(f"DEBUG: First compilation failed with return code {result.returncode}")
        print(f"DEBUG: Attempting to install missing packages with tlmgr...")
        
        # Try to use tlmgr to install missing packages
        try:
            # Create user texmf directory
            user_texmf = pathlib.Path.home() / "texmf"
            user_texmf.mkdir(exist_ok=True)
            
            # Try to install common missing packages
            common_packages = ["tracklang", "glossaries", "biblatex", "biber"]
            for package in common_packages:
                try:
                    tlmgr_cmd = ["tlmgr", "--usermode", "install", package]
                    tlmgr_result = subprocess.run(tlmgr_cmd, cwd=pathlib.Path(entry).parent, 
                                                capture_output=True, text=True, timeout=60)
                    if tlmgr_result.returncode == 0:
                        print(f"DEBUG: Successfully installed {package}")
                    else:
                        print(f"DEBUG: Failed to install {package}: {tlmgr_result.stderr}")
                except Exception as e:
                    print(f"DEBUG: Error installing {package}: {e}")
            
            # Try compilation again after installing packages
            print(f"DEBUG: Retrying compilation after package installation...")
            result = subprocess.run(cmd + [pathlib.Path(entry).name], cwd=pathlib.Path(entry).parent, capture_output=True, text=True)
            
        except Exception as e:
            print(f"DEBUG: Package installation failed: {e}")
    
    # Read log file for detailed error information
    log_file = pathlib.Path(entry).with_suffix('.log')
    log_content = ""
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()
        except Exception as e:
            log_content = f"Error reading log file: {e}"
    
    # Return the expected values: pdf_path and log
    pdf_path = str(pathlib.Path(entry).with_suffix('.pdf'))
    log = (result.stdout or "") + "\n" + (result.stderr or "") + "\n\n=== LaTeX Log File ===\n" + log_content
    
    return pdf_path, log

def _generate_unique_id() -> str:
    """Generate a unique ID for file storage"""
    return str(uuid.uuid4())

def _cleanup_expired_files():
    """Remove expired files from storage"""
    current_time = datetime.now()
    expired_ids = []
    
    for file_id, metadata in file_metadata.items():
        if current_time > metadata["expires_at"]:
            expired_ids.append(file_id)
    
    for file_id in expired_ids:
        try:
            metadata = file_metadata[file_id]
            if os.path.exists(metadata["storage_path"]):
                os.remove(metadata["storage_path"])
            del file_metadata[file_id]
            print(f"Cleaned up expired file: {file_id}")
        except Exception as e:
            print(f"Error cleaning up file {file_id}: {e}")

def _schedule_cleanup():
    """Schedule periodic cleanup of expired files"""
    def run_cleanup():
        while True:
            _cleanup_expired_files()
            time.sleep(3600)  # Run every hour
    
    cleanup_thread = threading.Thread(target=run_cleanup, daemon=True)
    cleanup_thread.start()

# Start cleanup scheduler
_schedule_cleanup()

@app.get("/health")
async def health_check():
    """Health check endpoint for container monitoring"""
    return {"status": "healthy", "service": "latex-renderer"}

@app.get("/")
async def root():
    """Serve the web interface"""
    try:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(script_dir, "static", "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        # Fallback to API info if HTML file not found
        return {
            "service": "LaTeX Render API",
            "version": "1.0.0",
            "endpoints": {
                "render": "/render - POST endpoint for rendering LaTeX projects",
                "files": f"{STORAGE_URL}/{{file_id}} - GET endpoint for downloading generated files",
                "health": "/health - Health check endpoint"
            },
            "supported_engines": ["latexmk"],
            "file_expiry": f"{FILE_EXPIRY_HOURS} hours"
        }

@app.post("/render")
async def render(
    project: UploadFile = File(...),
    engine: str = Form("latexmk"),
    entrypoint: str | None = Form(None),
    allow_shell_escape: bool = Form(False),
    runs: int = Form(3),
):
    print(f"DEBUG: Render request received - engine: {engine}, entrypoint: {entrypoint}")
    
    if engine != "latexmk":
        raise HTTPException(400, "engine must be 'latexmk'.")

    print("DEBUG: Reading project file...")
    zip_bytes = await project.read()
    print(f"DEBUG: ZIP file size: {len(zip_bytes)} bytes")
    
    print("DEBUG: Extracting ZIP to temporary directory...")
    workdir = _extract_zip_to_tmp(zip_bytes)
    print(f"DEBUG: Extracted to: {workdir}")
    
    try:
        print("DEBUG: Detecting entrypoint...")
        entry = _detect_entrypoint(workdir, entrypoint)
        print(f"DEBUG: Entrypoint detected: {entry}")
        
        print("DEBUG: Starting LaTeX compilation...")
        pdf_path, log = _compile_latexmk(entry, allow_shell_escape, runs)
        print(f"DEBUG: Compilation completed, PDF path: {pdf_path}")

        if not pathlib.Path(pdf_path).exists():
            print(f"DEBUG: PDF file not found at {pdf_path}")
            return JSONResponse(
                status_code=422,
                content={"error": "Compilation failed", "log": log[-20000:]},
            )

        print(f"DEBUG: PDF file found, size: {pathlib.Path(pdf_path).stat().st_size} bytes")
        print("DEBUG: Starting PDF streaming...")

        # Read the PDF content into memory before cleanup
        with open(pdf_path, "rb") as f:
            pdf_content = f.read()
        
        print(f"DEBUG: PDF content loaded into memory: {len(pdf_content)} bytes")
        
        # Save file to storage
        # Generate a descriptive filename using the file ID
        file_id = _generate_unique_id()
        file_extension = ".pdf"
        descriptive_filename = f"latex-{file_id}{file_extension}"
        storage_path = os.path.join(STORAGE_DIR, f"{file_id}{file_extension}")
        
        # Copy file to storage
        shutil.copy2(pdf_path, storage_path)
        
        # Store metadata
        file_metadata[file_id] = {
            "filename": descriptive_filename,
            "storage_path": storage_path,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(hours=FILE_EXPIRY_HOURS),
            "size": os.path.getsize(storage_path)
        }
        
        # Clean up the working directory
        print(f"DEBUG: Cleaning up working directory: {workdir}")
        shutil.rmtree(workdir, ignore_errors=True)
        
        # Return file information with download link
        download_url = f"{STORAGE_URL}/{file_id}"
        return {
            "success": True,
            "message": "LaTeX compilation successful",
            "file_id": file_id,
            "filename": descriptive_filename,
            "download_url": download_url,
            "expires_at": file_metadata[file_id]["expires_at"].isoformat(),
            "size_bytes": len(pdf_content)
        }
        
    except Exception as e:
        print(f"DEBUG: Error during processing: {e}")
        # Clean up on error
        shutil.rmtree(workdir, ignore_errors=True)
        raise

@app.get(f"{STORAGE_URL}/{{file_id}}")
async def download_file(file_id: str):
    """Download a file by its unique ID"""
    if file_id not in file_metadata:
        raise HTTPException(404, "File not found or expired")
    
    metadata = file_metadata[file_id]
    
    # Check if file has expired
    if datetime.now() > metadata["expires_at"]:
        # Clean up expired file
        try:
            if os.path.exists(metadata["storage_path"]):
                os.remove(metadata["storage_path"])
            del file_metadata[file_id]
        except Exception as e:
            print(f"Error cleaning up expired file {file_id}: {e}")
        
        raise HTTPException(410, "File has expired and been removed")
    
    # Check if file still exists on disk
    if not os.path.exists(metadata["storage_path"]):
        del file_metadata[file_id]
        raise HTTPException(404, "File not found on disk")
    
    # Return file for inline display (not download)
    return StreamingResponse(
        open(metadata["storage_path"], "rb"),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{metadata["filename"]}"',
            "Content-Length": str(metadata["size"]),
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff"
        }
    )

@app.get("/files")
async def list_files():
    """List all available files with their metadata"""
    files = []
    for file_id, metadata in file_metadata.items():
        files.append({
            "file_id": file_id,
            "filename": metadata["filename"],
            "original_filename": metadata.get("original_filename", metadata["filename"]),
            "project_name": metadata.get("project_name", "Unknown"),
            "created_at": metadata["created_at"].isoformat(),
            "expires_at": metadata["expires_at"].isoformat(),
            "size_bytes": metadata["size"],
            "download_url": f"{STORAGE_URL}/{file_id}"
        })
    
    return {
        "files": files,
        "total_files": len(files),
        "storage_directory": STORAGE_DIR
    }

# Note: Files are served through the custom endpoint above, not through static file mounting
# This allows us to control Content-Disposition headers for inline PDF display

# Mount static files for the web interface
# Use absolute path for Docker compatibility
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/api")
async def api_info():
    """API information endpoint"""
    return {
        "service": "LaTeX Render API",
        "version": "1.0.0",
        "endpoints": {
            "render": "/render - POST endpoint for rendering LaTeX projects",
            "files": f"{STORAGE_URL}/{{file_id}} - GET endpoint for downloading generated files",
            "health": "/health - Health check endpoint"
        },
        "supported_engines": ["latexmk"],
        "file_expiry": f"{FILE_EXPIRY_HOURS} hours"
    }
