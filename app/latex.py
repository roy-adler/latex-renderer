"""LaTeX compilation utilities: extraction, entrypoint detection, compilation, and SyncTeX parsing."""

import base64, gzip, os, pathlib, shutil, subprocess, tempfile, zipfile, io
from fastapi import HTTPException


def extract_zip_to_tmp(zip_bytes: bytes) -> str:
    """Extract a ZIP archive to a temporary directory, validating paths."""
    workdir = tempfile.mkdtemp(prefix="latexapi_")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for member in z.namelist():
            target = os.path.realpath(os.path.join(workdir, member))
            if not target.startswith(os.path.realpath(workdir)):
                shutil.rmtree(workdir, ignore_errors=True)
                raise HTTPException(400, f"Invalid path in zip: {member}")
        z.extractall(workdir)
    return workdir


def detect_entrypoint(workdir: str, explicit: str | None) -> str:
    """Find the main .tex entrypoint in a working directory."""
    if explicit:
        ep = pathlib.Path(workdir, explicit)
        if not ep.exists():
            raise HTTPException(400, f"Entrypoint '{explicit}' not found.")
        return str(ep)
    tex_files = list(pathlib.Path(workdir).rglob("*.tex"))
    if not tex_files:
        raise HTTPException(400, "No .tex files found in project.")
    for cand in tex_files:
        if cand.name.lower() == "main.tex":
            return str(cand)
    if len(tex_files) == 1:
        return str(tex_files[0])
    raise HTTPException(400, "Multiple .tex files found; provide 'entrypoint'.")


def compile_latexmk(entry: str, runs: int) -> tuple[str, str]:
    """Compile a LaTeX file with latexmk, returning (pdf_path, log)."""
    shell = "-no-shell-escape"
    cmd = [
        "latexmk", "-pdf", "-interaction=nonstopmode", shell,
        "-halt-on-error", "-file-line-error", "-silent", "-f",
        "-pdflatex=pdflatex -synctex=1 %O %S",
    ]
    os.environ["LATEXMK_MAX_REPEAT"] = str(max(1, min(10, runs)))

    result = subprocess.run(
        cmd + [pathlib.Path(entry).name],
        cwd=str(pathlib.Path(entry).parent),
        capture_output=True, text=True,
    )

    # If compilation fails, try to install missing packages
    if result.returncode != 0:
        try:
            user_texmf = pathlib.Path.home() / "texmf"
            user_texmf.mkdir(exist_ok=True)
            common_packages = ["tracklang", "glossaries", "biblatex", "biber"]
            for pkg in common_packages:
                subprocess.run(
                    ["tlmgr", "--usermode", "install", pkg],
                    capture_output=True, timeout=30,
                )
            # Retry compilation
            result = subprocess.run(
                cmd + [pathlib.Path(entry).name],
                cwd=str(pathlib.Path(entry).parent),
                capture_output=True, text=True,
            )
        except Exception:
            pass

    # Read log file
    log_file = pathlib.Path(entry).with_suffix('.log')
    log_content = ""
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()
        except Exception as e:
            log_content = f"Error reading log file: {e}"

    pdf_path = str(pathlib.Path(entry).with_suffix('.pdf'))
    log = (result.stdout or "") + "\n" + (result.stderr or "") + "\n\n=== LaTeX Log File ===\n" + log_content
    return pdf_path, log


def parse_synctex(entry: str, workdir: str) -> dict | None:
    """Parse a .synctex.gz file into forward/inverse lookup tables.

    SyncTeX record format (after the record-type character):
        tag,line:x,y:W,H,D
    """
    synctex_gz = pathlib.Path(entry).with_suffix('.synctex.gz')
    synctex_plain = pathlib.Path(entry).with_suffix('.synctex')

    if synctex_gz.exists():
        try:
            with gzip.open(synctex_gz, 'rt', errors='ignore') as f:
                content = f.read()
        except Exception:
            return None
    elif synctex_plain.exists():
        try:
            with open(synctex_plain, 'r', errors='ignore') as f:
                content = f.read()
        except Exception:
            return None
    else:
        return None

    magnification = 1000
    unit = 1
    inputs = {}
    forward = {}
    inverse = {}
    workdir_real = os.path.realpath(workdir)
    current_page = 0

    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue

        if line.startswith('Magnification:'):
            try: magnification = int(line.split(':', 1)[1])
            except: pass
            continue
        if line.startswith('Unit:'):
            try: unit = int(line.split(':', 1)[1])
            except: pass
            continue
        if line.startswith(('X Offset:', 'Y Offset:', 'Output:', 'SyncTeX', 'Content:', 'Postamble:', 'Count:', 'Post scriptum:')):
            continue

        if line.startswith('Input:'):
            parts = line.split(':', 2)
            if len(parts) == 3:
                tag = parts[1]
                filepath = parts[2]
                real = os.path.realpath(filepath)
                if real.startswith(workdir_real + '/'):
                    filepath = real[len(workdir_real) + 1:]
                elif real.startswith(workdir_real):
                    filepath = real[len(workdir_real):]
                if filepath.startswith('./'):
                    filepath = filepath[2:]
                inputs[tag] = filepath
            continue

        if line.startswith('{'):
            try: current_page = int(line[1:])
            except: pass
            continue

        if line[0] in ('}', '!', ')'):
            continue

        if line[0] in ('h', '[') and ':' in line:
            data = line[1:]
            colon_parts = data.split(':')
            if len(colon_parts) < 2:
                continue
            try:
                first = colon_parts[0].split(',')
                tag = first[0]
                line_num = int(first[1]) if len(first) > 1 else 0

                second = colon_parts[1].split(',')
                v = int(second[1]) if len(second) > 1 else 0

                h_val = 0
                if len(colon_parts) > 2:
                    third = colon_parts[2].split(',')
                    h_val = int(third[1]) if len(third) > 1 else 0

                if tag not in inputs or line_num <= 0:
                    continue

                filename = inputs[tag]
                scale = unit * magnification / (1000.0 * 65536.0)
                y_pt = v * scale
                h_pt = abs(h_val * scale) if h_val else 10

                if filename not in forward:
                    forward[filename] = {}
                if line_num not in forward[filename]:
                    forward[filename][line_num] = []
                existing = forward[filename][line_num]
                if not any(e['page'] == current_page and abs(e['y'] - y_pt) < 1 for e in existing):
                    existing.append({'page': current_page, 'y': round(y_pt, 2)})

                if current_page not in inverse:
                    inverse[current_page] = []
                inverse[current_page].append({
                    'y': round(y_pt, 2),
                    'h': round(h_pt, 2),
                    'file': filename,
                    'line': line_num,
                })
            except (ValueError, IndexError):
                continue

    # Deduplicate and sort inverse records
    for page in inverse:
        seen = set()
        deduped = []
        for r in inverse[page]:
            key = (r['file'], r['line'])
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        deduped.sort(key=lambda r: r['y'])
        inverse[page] = deduped

    forward_str = {fname: {str(k): v for k, v in lines.items()} for fname, lines in forward.items()}
    inverse_str = {str(k): v for k, v in inverse.items()}

    if not forward_str and not inverse_str:
        return None

    return {'forward': forward_str, 'inverse': inverse_str}


def write_project_files_to_workdir(files_with_content: list[dict], workdir: str):
    """Write a list of project file dicts (with 'filename', 'content', 'is_binary') to a working directory."""
    for full_file in files_with_content:
        fpath = os.path.join(workdir, full_file["filename"])
        os.makedirs(os.path.dirname(fpath) or workdir, exist_ok=True)
        real_path = os.path.realpath(fpath)
        if not real_path.startswith(os.path.realpath(workdir)):
            raise HTTPException(400, f"Invalid filename: {full_file['filename']}")
        if full_file.get("is_binary"):
            with open(fpath, "wb") as f:
                f.write(base64.b64decode(full_file["content"]))
        else:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(full_file["content"])
