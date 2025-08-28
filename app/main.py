import io, os, shutil, tempfile, zipfile, subprocess, pathlib, json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

app = FastAPI(title="LaTeX Render API")

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
    cmd = ["latexmk", "-pdf", "-interaction=nonstopmode", shell, "-halt-on-error", "-file-line-error", "-silent", "-pdfxe"]
    # Note: remove "-pdfxe" if you don't want XeLaTeX auto preference
    cmd += ["-pdflua", "-use-make"]  # harmless if engine not selected
    cmd += ["-f", "-g", "-pdflatex=pdflatex %O %S"]
    # Limit passes
    os.environ["LATEXMK_MAX_REPEAT"] = str(max(1, min(10, runs)))
    
    print(f"DEBUG: Compiling with command: {' '.join(cmd)}")
    print(f"DEBUG: Working directory: {str(pathlib.Path(entry).parent)}")
    print(f"DEBUG: Entry point: {entry}")
    
    result = _run(cmd + [pathlib.Path(entry).name], cwd=str(pathlib.Path(entry).parent))
    
    print(f"DEBUG: Command return code: {result.returncode}")
    print(f"DEBUG: Command stdout: {result.stdout[:500] if result.stdout else 'None'}")
    print(f"DEBUG: Command stderr: {result.stderr[:500] if result.stderr else 'None'}")
    
    log = (result.stdout or "") + "\n" + (result.stderr or "")
    pdf = str(pathlib.Path(entry).with_suffix(".pdf"))
    
    print(f"DEBUG: Expected PDF path: {pdf}")
    print(f"DEBUG: PDF file exists: {pathlib.Path(pdf).exists()}")
    
    return pdf, log

@app.get("/health")
async def health_check():
    """Health check endpoint for container monitoring"""
    return {"status": "healthy", "service": "latex-renderer"}

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "LaTeX Render API",
        "version": "1.0.0",
        "endpoints": {
            "render": "/render - POST endpoint for rendering LaTeX projects",
            "health": "/health - Health check endpoint"
        },
        "supported_engines": ["latexmk"]
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
        
        # Clean up the working directory
        print(f"DEBUG: Cleaning up working directory: {workdir}")
        shutil.rmtree(workdir, ignore_errors=True)
        
        # Return the PDF content directly
        return StreamingResponse(
            iter([pdf_content]),
            media_type="application/pdf",
            headers={"Content-Disposition": 'inline; filename="output.pdf"'},
        )
        
    except Exception as e:
        print(f"DEBUG: Error during processing: {e}")
        # Clean up on error
        shutil.rmtree(workdir, ignore_errors=True)
        raise
