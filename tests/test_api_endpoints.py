#!/usr/bin/env python3
"""
Comprehensive API Tests
======================

Test suite for all API endpoints to ensure functionality works correctly.
"""

import sys
import requests
import json
from pathlib import Path

# Add the parent directory to the path
sys.path.append(str(Path(__file__).resolve().parents[1]))

BASE_URL = "http://localhost:8000"

def test_health_endpoint():
    """Test the health endpoint."""
    print("🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        print("✅ Health endpoint working")
        return True
    except Exception as e:
        print(f"❌ Health endpoint failed: {e}")
        return False

def test_search_endpoint():
    """Test the search endpoint."""
    print("🔍 Testing search endpoint...")
    try:
        # Test basic search
        response = requests.get(f"{BASE_URL}/api/search?q=project management")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "query" in data
        assert "total_results" in data
        assert len(data["results"]) > 0
        
        # Test search with standard filter
        response = requests.get(f"{BASE_URL}/api/search?q=risk&standard=PMBOK")
        assert response.status_code == 200
        data = response.json()
        assert all("PMBOK" in result["standard"] for result in data["results"])
        
        print("✅ Search endpoint working")
        return True
    except Exception as e:
        print(f"❌ Search endpoint failed: {e}")
        return False

def test_compare_endpoint():
    """Test the comparison endpoint."""
    print("🔍 Testing compare endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/compare?topic=stakeholder management")
        assert response.status_code == 200
        data = response.json()
        assert "topic" in data
        assert "standards" in data
        assert "insights" in data
        assert "comparison_metadata" in data
        
        # Check that insights are present
        assert "similarities" in data["insights"]
        assert "differences" in data["insights"]
        assert "uniques" in data["insights"]
        
        print("✅ Compare endpoint working")
        return True
    except Exception as e:
        print(f"❌ Compare endpoint failed: {e}")
        return False

def test_detailed_compare_endpoint():
    """Test the detailed comparison endpoint."""
    print("🔍 Testing detailed compare endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/compare/detailed?topic=risk management")
        assert response.status_code == 200
        data = response.json()
        assert "summaries" in data
        assert "similarities" in data
        assert "differences" in data
        assert "uniques" in data
        
        print("✅ Detailed compare endpoint working")
        return True
    except Exception as e:
        print(f"❌ Detailed compare endpoint failed: {e}")
        return False

def test_analysis_endpoint():
    """Test the analysis endpoint."""
    print("🔍 Testing analysis endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/analysis")
        assert response.status_code == 200
        data = response.json()
        assert "points" in data
        assert "threshold" in data
        assert len(data["points"]) > 0
        
        # Check that points have required fields
        point = data["points"][0]
        assert "x" in point
        assert "y" in point
        assert "label" in point
        assert "standard" in point
        
        print("✅ Analysis endpoint working")
        return True
    except Exception as e:
        print(f"❌ Analysis endpoint failed: {e}")
        return False

def test_graphs_endpoint():
    """Test the graphs endpoint."""
    print("🔍 Testing graphs endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/graphs?topic=project planning")
        assert response.status_code == 200
        data = response.json()
        assert "points" in data
        assert "threshold" in data
        
        print("✅ Graphs endpoint working")
        return True
    except Exception as e:
        print(f"❌ Graphs endpoint failed: {e}")
        return False

def test_process_recommendation_endpoint():
    """Test the process recommendation endpoint."""
    print("🔍 Testing process recommendation endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/process-recommendation?project_type=software&project_size=medium&industry=IT&methodology_preference=any")
        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data
        assert "tailored_approach" in data
        assert "evidence_base" in data
        
        # Check tailored approach structure
        tailored = data["tailored_approach"]
        assert "project_characteristics" in tailored
        assert "recommended_approach" in tailored
        assert "process_phases" in tailored
        assert "key_activities" in tailored
        assert "critical_deliverables" in tailored
        assert "tailoring_guidance" in tailored
        
        print("✅ Process recommendation endpoint working")
        return True
    except Exception as e:
        print(f"❌ Process recommendation endpoint failed: {e}")
        return False

def test_pdf_serving():
    """Test PDF serving functionality."""
    print("🔍 Testing PDF serving...")
    try:
        # Test PMBOK PDF
        response = requests.get(f"{BASE_URL}/pdf/PMBOK")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        
        # Test PRINCE2 PDF
        response = requests.get(f"{BASE_URL}/pdf/PRINCE2")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        
        print("✅ PDF serving working")
        return True
    except Exception as e:
        print(f"❌ PDF serving failed: {e}")
        return False

def test_view_endpoint():
    """Test the view endpoint for PDF navigation."""
    print("🔍 Testing view endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/view?standard=PMBOK&page=1&text=project management")
        assert response.status_code == 200
        # Should return HTML content
        assert "text/html" in response.headers.get("content-type", "")
        
        print("✅ View endpoint working")
        return True
    except Exception as e:
        print(f"❌ View endpoint failed: {e}")
        return False

def run_all_tests():
    """Run all tests and report results."""
    print("🧪 Running Comprehensive API Tests")
    print("=" * 50)
    
    tests = [
        test_health_endpoint,
        test_search_endpoint,
        test_compare_endpoint,
        test_detailed_compare_endpoint,
        test_analysis_endpoint,
        test_graphs_endpoint,
        test_process_recommendation_endpoint,
        test_pdf_serving,
        test_view_endpoint
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()  # Add spacing between tests
    
    print("📊 Test Results Summary")
    print("=" * 30)
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    print(f"📈 Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🎉 All tests passed! The application is working correctly.")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
