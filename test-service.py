#!/usr/bin/env python3
"""
Test script for the LaTeX rendering service
"""

import requests
import zipfile
import os
import tempfile
import shutil

def create_test_zip():
    """Create a test ZIP file from the test-project directory"""
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
        with zipfile.ZipFile(tmp_file.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            test_dir = 'test-project'
            for root, dirs, files in os.walk(test_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, test_dir)
                    zipf.write(file_path, arcname)
        return tmp_file.name

def test_service():
    """Test the LaTeX rendering service"""
    service_url = "http://localhost:8000"
    
    # Test health endpoint
    try:
        response = requests.get(f"{service_url}/health")
        print(f"Health check: {response.status_code} - {response.json()}")
    except requests.exceptions.ConnectionError:
        print("❌ Service not running. Start it with: docker run -p 8000:8000 latex-renderer")
        return
    
    # Test root endpoint
    try:
        response = requests.get(f"{service_url}/")
        print(f"Root endpoint: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"❌ Error testing root endpoint: {e}")
        return
    
    # Create test ZIP
    zip_path = create_test_zip()
    print(f"✅ Created test ZIP: {zip_path}")
    
    try:
        # Test rendering
        print("\n🔄 Testing LaTeX rendering...")
        
        with open(zip_path, 'rb') as f:
            files = {'project': ('test-project.zip', f, 'application/zip')}
            data = {
                'engine': 'tectonic',
                'allow_shell_escape': 'false'
            }
            
            response = requests.post(
                f"{service_url}/render",
                files=files,
                data=data,
                timeout=60
            )
        
        if response.status_code == 200:
            # Save the PDF
            output_pdf = "test-output.pdf"
            with open(output_pdf, 'wb') as f:
                f.write(response.content)
            print(f"✅ Success! PDF saved as: {output_pdf}")
            print(f"📄 PDF size: {len(response.content)} bytes")
        else:
            print(f"❌ Rendering failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error details: {error_data}")
            except:
                print(f"Response text: {response.text[:500]}")
                
    except Exception as e:
        print(f"❌ Error during rendering: {e}")
    
    finally:
        # Cleanup
        os.unlink(zip_path)
        print(f"🧹 Cleaned up temporary ZIP file")

if __name__ == "__main__":
    print("🚀 Testing LaTeX Rendering Service")
    print("=" * 40)
    test_service()
