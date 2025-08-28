# LaTeX Renderer

A Docker-based LaTeX rendering service that accepts ZIP files of LaTeX projects and returns compiled PDFs.

## Features

- **Multiple Engines**: Supports both Tectonic (fast, modern) and latexmk (traditional, comprehensive)
- **ZIP Upload**: Accepts complete LaTeX projects as ZIP files
- **Smart Entrypoint Detection**: Automatically finds main.tex or detects single .tex files
- **Security**: Runs as non-root user with configurable shell escape options
- **RESTful API**: Clean HTTP endpoints with proper error handling

## Quick Start

### Build and Run

```bash
# Build the Docker image
docker build -t latex-renderer .

# Run the container
docker run -p 8000:8000 latex-renderer
```

The service will be available at `http://localhost:8000`

### API Endpoints

- `GET /` - Service information and available endpoints
- `GET /health` - Health check for monitoring
- `POST /render` - Main rendering endpoint

## Usage

### Render a LaTeX Project

```bash
curl -X POST "http://localhost:8000/render" \
  -F "project=@your-project.zip" \
  -F "engine=tectonic" \
  -F "entrypoint=main.tex" \
  -F "allow_shell_escape=false" \
  -F "runs=3" \
  --output output.pdf
```

### Parameters

- `project` (required): ZIP file containing your LaTeX project
- `engine` (optional): Either "tectonic" (default) or "latexmk"
- `entrypoint` (optional): Specific .tex file to compile (auto-detected if not provided)
- `allow_shell_escape` (optional): Allow shell escape commands (default: false)
- `runs` (optional): Number of compilation passes for latexmk (default: 3)

### Supported LaTeX Engines

1. **Tectonic** (default)
   - Fast, modern LaTeX engine
   - Automatic dependency resolution
   - Good for most projects

2. **latexmk**
   - Traditional LaTeX compilation
   - Multiple passes for references, citations
   - More comprehensive but slower

## Project Structure

Your ZIP file should contain a complete LaTeX project with:
- Main `.tex` file(s)
- Supporting files (images, bibliography, etc.)
- Any required packages (though Tectonic handles most automatically)

## Examples

### Simple Document
```
project.zip
├── main.tex
└── images/
    └── logo.png
```

### Academic Paper
```
project.zip
├── paper.tex
├── references.bib
├── figures/
│   ├── diagram.tex
│   └── chart.pdf
└── sections/
    ├── introduction.tex
    ├── methods.tex
    └── conclusion.tex
```

## Security Features

- Non-root container execution
- Configurable shell escape restrictions
- Temporary working directory cleanup
- Timeout limits on compilation

## Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing

```bash
# Test with a sample LaTeX project
curl -X POST "http://localhost:8000/render" \
  -F "project=@test-project.zip" \
  --output test-output.pdf
```

## Troubleshooting

### Common Issues

1. **No .tex files found**: Ensure your ZIP contains .tex files
2. **Multiple .tex files**: Specify the entrypoint parameter
3. **Compilation errors**: Check the returned error log
4. **Missing packages**: Tectonic handles most automatically; latexmk may need manual package installation

### Logs

The service returns compilation logs in case of errors, helping debug LaTeX compilation issues.

## License

See LICENSE file for details.
