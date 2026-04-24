#!/usr/bin/env python3
"""
Comprehensive Test Runner
========================

Run all tests for the PM Standards Comparator application.
"""

import os
import subprocess
import sys
import time
from pathlib import Path
import requests

def run_command(command, description):
    """Run a command and return success status."""
    try:
        print(f"\n🔍 {description}")
    except Exception:
        print(f"\n{description}")
    print("-" * 50)
    
    try:
        # Force UTF-8 to avoid Windows cp1252 decoding issues
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            env=env,
        )
        if result.returncode == 0:
            try:
                print(f"✅ {description} - PASSED")
            except Exception:
                print(f"{description} - PASSED")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            try:
                print(f"❌ {description} - FAILED")
            except Exception:
                print(f"{description} - FAILED")
            if result.stderr:
                print("Error output:")
                print(result.stderr)
            if result.stdout:
                print("Standard output:")
                print(result.stdout)
            return False
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False

def check_server_running():
    """Check if the server is running."""
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def start_server():
    """Start the server in the background."""
    try:
        print("🚀 Starting server...")
    except Exception:
        print("Starting server...")
    try:
        # Start server in background
        # Inherit console to avoid Unicode decode on pipes
        process = subprocess.Popen(["python", "run.py"])
        
        # Wait for server to start
        for i in range(30):  # Wait up to 30 seconds
            if check_server_running():
                try:
                    print("✅ Server started successfully")
                except Exception:
                    print("Server started successfully")
                return process
            time.sleep(1)
        
        try:
            print("❌ Server failed to start within 30 seconds")
        except Exception:
            print("Server failed to start within 30 seconds")
        return None
    except Exception as e:
        try:
            print(f"❌ Failed to start server: {e}")
        except Exception:
            print(f"Failed to start server: {e}")
        return None

def stop_server(process):
    """Stop the server."""
    if process:
        try:
            process.terminate()
            process.wait(timeout=5)
            print("✅ Server stopped")
        except:
            process.kill()
            print("⚠️  Server force-stopped")

def run_all_tests():
    """Run all tests."""
    try:
        print("🧪 PM Standards Comparator - Comprehensive Test Suite")
    except Exception:
        print("PM Standards Comparator - Comprehensive Test Suite")
    print("=" * 60)
    
    # Check if server is already running
    if check_server_running():
        print("✅ Server is already running")
        server_process = None
    else:
        server_process = start_server()
        if not server_process:
            print("❌ Cannot run tests without server")
            return False
    
    try:
        # Test results
        test_results = []
        
        # 1. Search functionality tests
        print("\n📋 Running Search Functionality Tests")
        success = run_command(
            "python tests/test_search_functionality.py",
            "Search Functionality Tests"
        )
        test_results.append(("Search Functionality", success))
        
        # 2. API endpoint tests
        print("\n📋 Running API Endpoint Tests")
        success = run_command(
            "python tests/test_api_endpoints.py",
            "API Endpoint Tests"
        )
        test_results.append(("API Endpoints", success))
        
        # 3. Process recommendation tests
        print("\n📋 Running Process Recommendation Tests")
        success = run_command(
            "python tests/test_process_recommendations.py",
            "Process Recommendation Tests"
        )
        test_results.append(("Process Recommendations", success))
        
        # 4. Page number verification
        print("\n📋 Running Page Number Verification")
        success = run_command(
            "python ingest/verify_page_numbers.py",
            "Page Number Verification"
        )
        test_results.append(("Page Number Verification", success))
        
        # 5. Data integrity check
        print("\n📋 Running Data Integrity Check")
        success = run_command(
            "python -c \"from app.services.search import get_engine; engine = get_engine(); results = engine.query('test', k=1); print('✅ Data integrity verified' if results else '❌ No data found')\"",
            "Data Integrity Check"
        )
        test_results.append(("Data Integrity", success))
        
        # Summary
        print("\n📊 Test Results Summary")
        print("=" * 40)
        
        passed = 0
        total = len(test_results)
        
        for test_name, success in test_results:
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"{test_name:.<30} {status}")
            if success:
                passed += 1
        
        print(f"\nOverall Results: {passed}/{total} test suites passed")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if passed == total:
            print("\n🎉 All tests passed! The application is working correctly.")
            return True
        else:
            print(f"\n⚠️  {total - passed} test suites failed.")
            return False
            
    finally:
        # Stop server if we started it
        if server_process:
            stop_server(server_process)

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
