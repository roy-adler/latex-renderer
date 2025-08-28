# PowerShell script to test the LaTeX rendering service

Write-Host "🚀 Testing LaTeX Rendering Service" -ForegroundColor Green
Write-Host "=" * 40 -ForegroundColor Green

# Test health endpoint
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health"
    Write-Host "✅ Health check: $($response.StatusCode) - $($response.Content)" -ForegroundColor Green
} catch {
    Write-Host "❌ Health check failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test root endpoint
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/"
    Write-Host "✅ Root endpoint: $($response.StatusCode) - $($response.Content)" -ForegroundColor Green
} catch {
    Write-Host "❌ Root endpoint failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test rendering
Write-Host "`n🔄 Testing LaTeX rendering with latexmk..." -ForegroundColor Yellow

try {
    # Use a simpler approach with Invoke-RestMethod
    $form = @{
        project = Get-Item "test-project.zip"
        engine = "latexmk"
        runs = "3"
    }
    
    $response = Invoke-RestMethod -Uri "http://localhost:8000/render" -Method Post -Form $form -OutFile "test-output.pdf"
    
    Write-Host "✅ Success! PDF saved as: test-output.pdf" -ForegroundColor Green
    $pdfSize = (Get-Item "test-output.pdf").Length
    Write-Host "📄 PDF size: $pdfSize bytes" -ForegroundColor Green
    
} catch {
    Write-Host "❌ Error during rendering: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        try {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $responseBody = $reader.ReadToEnd()
            Write-Host "Error response: $responseBody" -ForegroundColor Red
        } catch {
            Write-Host "Could not read error response" -ForegroundColor Red
        }
    }
}

Write-Host "`n🧹 Test completed!" -ForegroundColor Green
