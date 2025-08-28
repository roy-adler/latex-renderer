# Testing Setup for LaTeX Renderer

This folder contains all testing-related files and configurations for the LaTeX Renderer service.

## Contents

### Test Scripts
- `test-unzip-summary.py` - Tests for ZIP extraction and entrypoint detection
- `test-service.py` - Tests for the FastAPI service endpoints
- `test-powershell.ps1` - PowerShell test script for Windows environments

### Test Data
- `test-project/` - Sample LaTeX project directory containing `main.tex`
- `test-project.zip` - Zipped version of the test project for testing uploads
- `test-output.pdf` - Generated PDF output from test runs

### Test Docker Configuration
- `Dockerfile.test` - Test Docker image (runs as root for testing)
- `docker-compose.test.yml` - Test Docker Compose configuration (port 8001)

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
- **Features**: Full LaTeX compilation with LaTeXmk
- **Health Check**: `http://localhost:8001/health`

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
