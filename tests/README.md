# Testing Setup for LaTeX Renderer

This folder contains all testing-related files and configurations for the LaTeX Renderer service.

## Contents

### Test Scripts
- `test-unzip-summary.py` - Tests for ZIP extraction and entrypoint detection
- `test-service.py` - Tests for the FastAPI service endpoints
- `test-file-storage.py` - **NEW** Tests for file storage with unique links and expiry
- `test-powershell.ps1` - PowerShell test script for Windows environments

### Test Data
- `test-project/` - Sample LaTeX project directory containing `main.tex`
- `test-project.zip` - Zipped version of the test project for testing uploads
- `test-output.pdf` - Generated PDF output from test runs

### Test Docker Configuration
- `Dockerfile.test` - Test Docker image (runs as root for testing)
- `docker-compose.test.yml` - Test Docker Compose configuration (port 8001)

## New Features (File Storage)

The LaTeX renderer now includes a file storage system with:

- **Unique File IDs**: Each generated PDF gets a unique UUID
- **48-Hour Expiry**: Files automatically expire and are deleted after 48 hours
- **Download Links**: Shareable links in format `/files/{file_id}`
- **File Management**: List and manage all stored files
- **Automatic Cleanup**: Background process removes expired files

### New API Endpoints

- `GET /files` - List all stored files with metadata
- `GET /files/{file_id}` - Download a specific file by ID
- `POST /render` - Now returns file storage information instead of direct PDF

## Running Tests

### 1. Start Test Service
```bash
# From the project root directory
docker-compose -f tests/docker-compose.test.yml up -d --build
```

### 2. Run Python Tests
```bash
# From the tests directory
cd tests
python test-service.py
python test-unzip-summary.py
python test-file-storage.py  # NEW: Test file storage functionality
```

### 3. Run PowerShell Tests (Windows)
```powershell
# From the tests directory
cd tests
.\test-powershell.ps1
```

## Test Service Details

- **Port**: 8001 (to avoid conflicts with production service on 8000)
- **User**: Runs as root for testing (not recommended for production)
- **Features**: Full LaTeX compilation with LaTeXmk + File storage system
- **Health Check**: `http://localhost:8001/health`

## File Storage Testing

### Test the Complete Workflow

1. **Upload LaTeX Project**: Send ZIP file to `/render`
2. **Get Storage Info**: Receive file ID, download URL, and expiry time
3. **List Files**: Check `/files` to see all stored files
4. **Download File**: Use the unique link to download the PDF
5. **Monitor Expiry**: Watch files get automatically cleaned up

### Example Response from /render
```json
{
  "success": true,
  "message": "LaTeX compilation successful",
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "latex-550e8400-e29b-41d4-a716-446655440000.pdf",
  "download_url": "/files/550e8400-e29b-41d4-a716-446655440000",
  "expires_at": "2025-08-30T14:06:09.123456",
  "size_bytes": 96082
}
```

## Cleanup

```bash
# Stop test service
docker-compose -f tests/docker-compose.test.yml down

# Remove test containers and images
docker-compose -f tests/docker-compose.test.yml down --rmi all --volumes
```

## Notes

- The test service is configured to run as root to avoid permission issues during testing
- Test files are automatically cleaned up after each test run
- The test project contains a simple LaTeX document with mathematical equations and formatting
- All test outputs are saved in this directory for inspection
- **NEW**: Generated PDFs are now stored with unique links that expire after 48 hours
- **NEW**: Files can be shared via their unique download links
- **NEW**: Automatic cleanup runs every hour to remove expired files
