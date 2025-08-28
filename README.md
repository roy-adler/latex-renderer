# LaTeX Renderer

A Docker-based LaTeX rendering service that accepts ZIP files of LaTeX projects and returns compiled PDFs with unique download links that expire after 48 hours.

## Features

- **LaTeXmk Engine**: Uses the comprehensive latexmk engine for reliable LaTeX compilation
- **ZIP Upload**: Accepts complete LaTeX projects as ZIP files
- **Smart Entrypoint Detection**: Automatically finds main.tex or detects single .tex files
- **File Storage System**: Generates unique download links for each PDF
- **Automatic Expiry**: Files are automatically deleted after 48 hours
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

### Using Docker Compose

```bash
# Start the service
docker-compose up -d

# Stop the service
docker-compose down
```

### API Endpoints

- `GET /` - Service information and available endpoints
- `GET /health` - Health check for monitoring
- `POST /render` - Main rendering endpoint (returns file storage info)
- `GET /files` - List all stored files with metadata
- `GET /files/{file_id}` - Download a specific file by ID

## Usage

### Render a LaTeX Project

```bash
curl -X POST "http://localhost:8000/render" \
  -F "project=@your-project.zip" \
  -F "engine=latexmk" \
  -F "entrypoint=main.tex" \
  -F "allow_shell_escape=false" \
  -F "runs=3"
```

### Response Format

Instead of returning the PDF directly, the service now returns file storage information:

```json
{
  "success": true,
  "message": "LaTeX compilation successful",
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "main.pdf",
  "download_url": "/files/550e8400-e29b-41d4-a716-446655440000",
  "expires_at": "2025-08-30T14:06:09.123456",
  "size_bytes": 96082
}
```

### Download the Generated PDF

```bash
# Download using the unique file ID
curl "http://localhost:8000/files/550e8400-e29b-41d4-a716-446655440000" \
  --output main.pdf

# Or use the full download URL
curl "http://localhost:8000/files/550e8400-e29b-41d4-a716-446655440000" \
  --output main.pdf
```

### List All Stored Files

```bash
curl "http://localhost:8000/files"
```

### Parameters

- `project` (required): ZIP file containing your LaTeX project
- `engine` (optional): Must be "latexmk" (default)
- `entrypoint` (optional): Specific .tex file to compile (auto-detected if not provided)
- `allow_shell_escape` (optional): Allow shell escape commands (default: false)
- `runs` (optional): Number of compilation passes for latexmk (default: 3)

### LaTeXmk Engine

The service uses **latexmk** which provides:
- Multiple compilation passes for references, citations, and cross-references
- Automatic detection of required compilation steps
- Support for complex LaTeX projects with bibliographies, indices, etc.
- Reliable compilation with proper error handling

## File Storage System

### How It Works

1. **Upload**: Send your LaTeX project ZIP to `/render`
2. **Compilation**: Service compiles your LaTeX and generates a PDF
3. **Storage**: PDF is saved with a unique UUID and 48-hour expiry
4. **Link Generation**: You receive a unique download link
5. **Sharing**: Share the link with others (valid for 48 hours)
6. **Automatic Cleanup**: Files are automatically deleted after expiry

### Benefits

- **Shareable Links**: Send unique URLs to colleagues or clients
- **No File Storage**: Files are automatically managed and cleaned up
- **Secure**: Each file has a unique, unguessable identifier
- **Temporary**: Perfect for temporary document sharing
- **Scalable**: No accumulation of old files

### File Management

- **Listing**: View all stored files with metadata
- **Download**: Access files via their unique IDs
- **Expiry Tracking**: See when each file will be automatically deleted
- **Size Information**: Know the size of each stored file

## Project Structure

Your ZIP file should contain a complete LaTeX project with:
- Main `.tex` file(s)
- Supporting files (images, bibliography, etc.)
- Any required packages and dependencies

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
- Unique file IDs prevent unauthorized access
- Automatic file expiry and cleanup

## Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing

The project includes a comprehensive test suite in the `tests/` folder:

```bash
# Start test service
docker-compose -f tests/docker-compose.test.yml up -d --build

# Run tests
cd tests
python test-service.py
python test-unzip-summary.py
python test-file-storage.py  # NEW: Test file storage functionality

# Stop test service
docker-compose -f tests/docker-compose.test.yml down
```

See `tests/README.md` for detailed testing instructions.

## Troubleshooting

### Common Issues

1. **No .tex files found**: Ensure your ZIP contains .tex files
2. **Multiple .tex files**: Specify the entrypoint parameter
3. **Compilation errors**: Check the returned error log
4. **Missing packages**: Ensure all required LaTeX packages are available in the container
5. **File not found**: Check if the file has expired (48-hour limit)

### Logs

The service returns compilation logs in case of errors, helping debug LaTeX compilation issues.

### File Storage Issues

- **Expired files**: Files are automatically deleted after 48 hours
- **Invalid file ID**: Ensure you're using the correct UUID from the render response
- **Storage full**: The service automatically manages storage and cleans up expired files

## License

See LICENSE file for details.
