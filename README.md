# LaTeX Renderer

A FastAPI-based service for rendering LaTeX projects into PDFs.

## Features

- **Web Interface**: Simple drag & drop interface for uploading LaTeX projects
- **API Endpoints**: RESTful API for programmatic access
- **Multiple Engines**: Support for latexmk compilation engine
- **File Management**: Automatic cleanup of generated files after 48 hours
- **Error Handling**: Comprehensive error reporting and logging

## Quick Start

### Web Interface

1. Start the server:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. Open your browser and navigate to `http://localhost:8000`

3. Drag & drop a ZIP file containing your LaTeX project, or click to browse

4. Wait for compilation to complete

5. Download the generated PDF

### API Usage

#### Render a LaTeX Project

```bash
curl -X POST "http://localhost:8000/render" \
  -F "project=@your-project.zip" \
  -F "engine=latexmk" \
  -F "runs=3"
```

#### Download Generated File

```bash
curl "http://localhost:8000/files/{file_id}" -o output.pdf
```

#### API Information

```bash
curl "http://localhost:8000/api"
```

## Project Structure

Your ZIP file should contain:
- `.tex` files (main document)
- Supporting files (images, bibliography, etc.)
- The service will automatically detect `main.tex` if present

## Requirements

- Python 3.8+
- LaTeX distribution (pdflatex, latexmk)
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Ensure LaTeX is installed on your system
4. Start the server

## Docker

```bash
docker-compose up
```

## API Endpoints

- `GET /` - Web interface
- `POST /render` - Render LaTeX project
- `GET /files/{file_id}` - Download generated file
- `GET /api` - API information
- `GET /health` - Health check

## Configuration

- File storage: `/tmp/latex_storage`
- File expiry: 48 hours
- Default compilation runs: 3
- Supported engines: latexmk
