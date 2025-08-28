#!/usr/bin/env python3
"""
Comprehensive test summary for the unzip functionality of the main application
"""

import io
import os
import shutil
import tempfile
import zipfile
import pathlib
import sys
import time

# Add the app directory to the path so we can import the main module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from main import _extract_zip_to_tmp, _detect_entrypoint

def run_comprehensive_test():
    """Run a comprehensive test of all unzip functionality"""
    print("🚀 COMPREHENSIVE UNZIP FUNCTIONALITY TEST")
    print("=" * 60)
    
    test_results = []
    
    # Test 1: Basic unzip functionality
    print("\n1️⃣  Testing Basic Unzip Functionality")
    print("-" * 40)
    try:
        # Create a simple test ZIP
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            with zipfile.ZipFile(tmp_file.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write('test-project/main.tex', 'main.tex')
            zip_path = tmp_file.name
        
        # Test unzip
        with open(zip_path, 'rb') as f:
            zip_bytes = f.read()
        
        workdir = _extract_zip_to_tmp(zip_bytes)
        
        # Verify extraction
        if os.path.exists(workdir) and os.path.exists(os.path.join(workdir, 'main.tex')):
            print("✅ Basic unzip: SUCCESS")
            test_results.append(("Basic unzip", "SUCCESS"))
        else:
            print("❌ Basic unzip: FAILED")
            test_results.append(("Basic unzip", "FAILED"))
        
        # Clean up
        shutil.rmtree(workdir, ignore_errors=True)
        os.unlink(zip_path)
        
    except Exception as e:
        print(f"❌ Basic unzip: ERROR - {e}")
        test_results.append(("Basic unzip", f"ERROR: {e}"))
    
    # Test 2: Entrypoint detection
    print("\n2️⃣  Testing Entrypoint Detection")
    print("-" * 40)
    try:
        # Create test ZIP with main.tex
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            with zipfile.ZipFile(tmp_file.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write('test-project/main.tex', 'main.tex')
            zip_path = tmp_file.name
        
        with open(zip_path, 'rb') as f:
            zip_bytes = f.read()
        
        workdir = _extract_zip_to_tmp(zip_bytes)
        
        # Test entrypoint detection
        entry = _detect_entrypoint(workdir, None)
        if entry and 'main.tex' in entry:
            print("✅ Entrypoint detection: SUCCESS")
            test_results.append(("Entrypoint detection", "SUCCESS"))
        else:
            print("❌ Entrypoint detection: FAILED")
            test_results.append(("Entrypoint detection", "FAILED"))
        
        # Clean up
        shutil.rmtree(workdir, ignore_errors=True)
        os.unlink(zip_path)
        
    except Exception as e:
        print(f"❌ Entrypoint detection: ERROR - {e}")
        test_results.append(("Entrypoint detection", f"ERROR: {e}"))
    
    # Test 3: Multiple .tex files handling
    print("\n3️⃣  Testing Multiple .tex Files Handling")
    print("-" * 40)
    try:
        # Create test ZIP with multiple .tex files
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            with zipfile.ZipFile(tmp_file.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write('test-project/main.tex', 'main.tex')
                zipf.writestr('second.tex', '\\documentclass{article}\\begin{document}Second\\end{document}')
            zip_path = tmp_file.name
        
        with open(zip_path, 'rb') as f:
            zip_bytes = f.read()
        
        workdir = _extract_zip_to_tmp(zip_bytes)
        
        # Test that it correctly fails with multiple .tex files
        try:
            entry = _detect_entrypoint(workdir, None)
            print("❌ Multiple .tex files: Should have failed but didn't")
            test_results.append(("Multiple .tex files", "FAILED - Should have failed"))
        except Exception as e:
            if "Multiple .tex files found" in str(e):
                print("✅ Multiple .tex files: SUCCESS (correctly failed)")
                test_results.append(("Multiple .tex files", "SUCCESS"))
            else:
                print(f"❌ Multiple .tex files: Unexpected error - {e}")
                test_results.append(("Multiple .tex files", f"ERROR: {e}"))
        
        # Clean up
        shutil.rmtree(workdir, ignore_errors=True)
        os.unlink(zip_path)
        
    except Exception as e:
        print(f"❌ Multiple .tex files: ERROR - {e}")
        test_results.append(("Multiple .tex files", f"ERROR: {e}"))
    
    # Test 4: Explicit entrypoint
    print("\n4️⃣  Testing Explicit Entrypoint")
    print("-" * 40)
    try:
        # Create test ZIP with multiple .tex files
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            with zipfile.ZipFile(tmp_file.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write('test-project/main.tex', 'main.tex')
                zipf.writestr('second.tex', '\\documentclass{article}\\begin{document}Second\\end{document}')
            zip_path = tmp_file.name
        
        with open(zip_path, 'rb') as f:
            zip_bytes = f.read()
        
        workdir = _extract_zip_to_tmp(zip_bytes)
        
        # Test explicit entrypoint
        entry = _detect_entrypoint(workdir, 'second.tex')
        if entry and 'second.tex' in entry:
            print("✅ Explicit entrypoint: SUCCESS")
            test_results.append(("Explicit entrypoint", "SUCCESS"))
        else:
            print("❌ Explicit entrypoint: FAILED")
            test_results.append(("Explicit entrypoint", "FAILED"))
        
        # Clean up
        shutil.rmtree(workdir, ignore_errors=True)
        os.unlink(zip_path)
        
    except Exception as e:
        print(f"❌ Explicit entrypoint: ERROR - {e}")
        test_results.append(("Explicit entrypoint", f"ERROR: {e}"))
    
    # Test 5: Error handling
    print("\n5️⃣  Testing Error Handling")
    print("-" * 40)
    try:
        # Test with invalid ZIP data
        invalid_bytes = b"this is not a zip file"
        try:
            workdir = _extract_zip_to_tmp(invalid_bytes)
            print("❌ Invalid ZIP: Should have failed but didn't")
            test_results.append(("Invalid ZIP handling", "FAILED - Should have failed"))
        except Exception as e:
            print(f"✅ Invalid ZIP: SUCCESS (correctly failed with {type(e).__name__})")
            test_results.append(("Invalid ZIP handling", "SUCCESS"))
        
        # Test with empty ZIP
        empty_zip = io.BytesIO()
        with zipfile.ZipFile(empty_zip, 'w') as z:
            pass
        empty_zip.seek(0)
        empty_bytes = empty_zip.read()
        
        try:
            workdir = _extract_zip_to_tmp(empty_bytes)
            print("✅ Empty ZIP: SUCCESS")
            test_results.append(("Empty ZIP handling", "SUCCESS"))
            shutil.rmtree(workdir, ignore_errors=True)
        except Exception as e:
            print(f"❌ Empty ZIP: FAILED - {e}")
            test_results.append(("Empty ZIP handling", f"FAILED: {e}"))
        
    except Exception as e:
        print(f"❌ Error handling: ERROR - {e}")
        test_results.append(("Error handling", f"ERROR: {e}"))
    
    # Test 6: Performance
    print("\n6️⃣  Testing Performance")
    print("-" * 40)
    try:
        # Create a larger test ZIP
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            with zipfile.ZipFile(tmp_file.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write('test-project/main.tex', 'main.tex')
                # Add some dummy files to make it larger
                for i in range(10):
                    large_content = f"Large file {i}\n" * 1000
                    zipf.writestr(f'large_file_{i}.txt', large_content)
            zip_path = tmp_file.name
        
        with open(zip_path, 'rb') as f:
            zip_bytes = f.read()
        
        print(f"📦 Testing with {len(zip_bytes)} byte ZIP file")
        
        start_time = time.time()
        workdir = _extract_zip_to_tmp(zip_bytes)
        end_time = time.time()
        
        extraction_time = end_time - start_time
        print(f"⏱️  Extraction time: {extraction_time:.3f} seconds")
        
        if extraction_time < 1.0:  # Should be very fast
            print("✅ Performance: SUCCESS (fast extraction)")
            test_results.append(("Performance", "SUCCESS"))
        else:
            print("⚠️  Performance: SLOW (but functional)")
            test_results.append(("Performance", "SLOW"))
        
        # Clean up
        shutil.rmtree(workdir, ignore_errors=True)
        os.unlink(zip_path)
        
    except Exception as e:
        print(f"❌ Performance test: ERROR - {e}")
        test_results.append(("Performance", f"ERROR: {e}"))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    success_count = sum(1 for _, result in test_results if "SUCCESS" in result)
    total_count = len(test_results)
    
    for test_name, result in test_results:
        status_icon = "✅" if "SUCCESS" in result else "❌" if "FAILED" in result else "⚠️"
        print(f"{status_icon} {test_name}: {result}")
    
    print(f"\n🎯 Overall Result: {success_count}/{total_count} tests passed")
    
    if success_count == total_count:
        print("🎉 All tests passed! The unzip functionality is working perfectly.")
    elif success_count >= total_count * 0.8:
        print("👍 Most tests passed. The unzip functionality is working well.")
    else:
        print("⚠️  Several tests failed. The unzip functionality needs attention.")

if __name__ == "__main__":
    run_comprehensive_test()
