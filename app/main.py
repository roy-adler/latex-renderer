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

def _compile_tectonic(entry: str, allow_shell_escape: bool) -> tuple[str, str]:
    cmd = [
        "tectonic",
        "--keep-logs",
        "--keep-intermediates",
        "--synctex",
        "--print",
    ]
    if not allow_shell_escape:
        cmd += ["--no-shell-escape"]
    cmd += [entry]
    result = _run(cmd, cwd=str(pathlib.Path(entry).parent))
    log = (result.stdout or "") + "\n" + (result.stderr or "")
    pdf = str(pathlib.Path(entry).with_suffix(".pdf"))
    return pdf, log

def _compile_latexmk(entry: str, allow_shell_escape: bool, runs: int) -> tuple[str, str]:
    # latexmk will call pdflatex/xelatex/lualatex/bibtex/biber as needed
    # default to pdf mode; nonstop to produce logs even on errors
    shell = "-shell-escape" if allow_shell_escape else "-no-shell-escape"
    cmd = ["latexmk", "-pdf", "-interaction=nonstopmode", shell, f"-halt-on-error", f"-file-line-error", f"-silent", f"-pdfxe"]
    # Note: remove "-pdfxe" if you don't want XeLaTeX auto preference
    cmd += [f"-pdflua", f"-use-make"]  # harmless if engine not selected
    cmd += [f"-f", f"-g", f"-pdflatex=pdflatex %O %S"]
    # Limit passes
    os.environ["LATEXMK_MAX_REPEAT"] = str(max(1, min(10, runs)))
    result = _run(cmd + [pathlib.Path(entry).name], cwd=str(pathlib.Path(entry).parent))
    log = (result.stdout or "") + "\n" + (result.stderr or "")
    pdf = str(pathlib.Path(entry).with_suffix(".pdf"))
    return pdf, log

@app.post("/render")
async def render(
    project: UploadFile = File(...),
    engine: str = Form("tectonic"),
    entrypoint: str | None = Form(None),
    allow_shell_escape: bool = Form(False),
    runs: int = Form(3),
):
    if engine not in {"tectonic", "latexmk"}:
        raise HTTPException(400, "engine must be 'tectonic' or 'latexmk'.")

    zip_bytes = await project.read()
    workdir = _extract_zip_to_tmp(zip_bytes)
    try:
        entry = _detect_entrypoint(workdir, entrypoint)
        if engine == "tectonic":
            pdf_path, log = _compile_tectonic(entry, allow_shell_escape)
        else:
            pdf_path, log = _compile_latexmk(entry, allow_shell_escape, runs)

        if not pathlib.Path(pdf_path).exists():
            return JSONResponse(
                status_code=422,
                content={"error": "Compilation failed", "log": log[-20000:]},
            )

        def _stream():
            with open(pdf_path, "rb") as f:
                yield from f

        return StreamingResponse(
            _stream(),
            media_type="application/pdf",
            headers={"Content-Disposition": 'inline; filename="output.pdf"'},
        )
    finally:
        # Clean up the working tree
        shutil.rmtree(workdir, ignore_errors=True)
