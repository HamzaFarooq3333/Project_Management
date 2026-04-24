#!/usr/bin/env python3
"""
Process Recommendation Tests
============================

Test the process recommendation functionality.
"""

import sys
import requests
from pathlib import Path

# Add the parent directory to the path
sys.path.append(str(Path(__file__).resolve().parents[1]))

BASE_URL = "http://localhost:8000"

def test_process_recommendation_software():
    """Test process recommendation for software projects."""
    print("🔍 Testing software project recommendations...")
    try:
        response = requests.get(f"{BASE_URL}/api/process-recommendation?project_type=software&project_size=medium&industry=IT&methodology_preference=any")
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "recommendations" in data
        assert "tailored_approach" in data
        assert "evidence_base" in data
        
        # Check tailored approach
        tailored = data["tailored_approach"]
        assert "project_characteristics" in tailored
        assert "recommended_approach" in tailored
        assert "process_phases" in tailored
        assert "key_activities" in tailored
        assert "critical_deliverables" in tailored
        assert "tailoring_guidance" in tailored
        
        # Check project characteristics
        characteristics = tailored["project_characteristics"]
        assert characteristics["type"] == "software"
        assert characteristics["size"] == "medium"
        assert characteristics["industry"] == "IT"
        
        print("✅ Software project recommendations working")
        return True
    except Exception as e:
        print(f"❌ Software project recommendations failed: {e}")
        return False

def test_process_recommendation_construction():
    """Test process recommendation for construction projects."""
    print("🔍 Testing construction project recommendations...")
    try:
        response = requests.get(f"{BASE_URL}/api/process-recommendation?project_type=construction&project_size=large&industry=construction&methodology_preference=PMBOK")
        assert response.status_code == 200
        data = response.json()
        
        tailored = data["tailored_approach"]
        characteristics = tailored["project_characteristics"]
        assert characteristics["type"] == "construction"
        assert characteristics["size"] == "large"
        assert characteristics["methodology_preference"] == "PMBOK"
        
        # Check that process phases are appropriate for construction
        phases = tailored["process_phases"]
        assert len(phases) > 0
        
        print("✅ Construction project recommendations working")
        return True
    except Exception as e:
        print(f"❌ Construction project recommendations failed: {e}")
        return False

def test_process_recommendation_small_project():
    """Test process recommendation for small projects."""
    print("🔍 Testing small project recommendations...")
    try:
        response = requests.get(f"{BASE_URL}/api/process-recommendation?project_type=research&project_size=small&industry=education&methodology_preference=any")
        assert response.status_code == 200
        data = response.json()
        
        tailored = data["tailored_approach"]
        characteristics = tailored["project_characteristics"]
        assert characteristics["size"] == "small"
        
        # Check that recommendations are appropriate for small projects
        activities = tailored["key_activities"]
        deliverables = tailored["critical_deliverables"]
        assert len(activities) > 0
        assert len(deliverables) > 0
        
        print("✅ Small project recommendations working")
        return True
    except Exception as e:
        print(f"❌ Small project recommendations failed: {e}")
        return False

def test_process_recommendation_validation():
    """Test that process recommendations include proper validation."""
    print("🔍 Testing process recommendation validation...")
    try:
        # Test with different project types
        project_types = ["software", "construction", "research", "marketing"]
        
        for project_type in project_types:
            response = requests.get(f"{BASE_URL}/api/process-recommendation?project_type={project_type}&project_size=medium&industry=IT&methodology_preference=any")
            assert response.status_code == 200
            data = response.json()
            
            # Check that all required fields are present
            assert "recommendations" in data
            assert "tailored_approach" in data
            assert "evidence_base" in data
            
            # Check evidence base
            evidence = data["evidence_base"]
            assert "total_sources" in evidence
            assert "standards_consulted" in evidence
            assert "confidence_level" in evidence
        
        print("✅ Process recommendation validation working")
        return True
    except Exception as e:
        print(f"❌ Process recommendation validation failed: {e}")
        return False

def test_process_recommendation_content_quality():
    """Test that process recommendations provide meaningful content."""
    print("🔍 Testing process recommendation content quality...")
    try:
        response = requests.get(f"{BASE_URL}/api/process-recommendation?project_type=software&project_size=large&industry=IT&methodology_preference=PRINCE2")
        assert response.status_code == 200
        data = response.json()
        
        tailored = data["tailored_approach"]
        
        # Check that recommendations are not empty
        assert len(tailored["process_phases"]) > 0
        assert len(tailored["key_activities"]) > 0
        assert len(tailored["critical_deliverables"]) > 0
        assert len(tailored["tailoring_guidance"]) > 0
        
        # Check that content is meaningful (not just empty strings)
        for phase in tailored["process_phases"]:
            assert len(phase.strip()) > 0
        
        for activity in tailored["key_activities"]:
            assert len(activity.strip()) > 0
        
        for deliverable in tailored["critical_deliverables"]:
            assert len(deliverable.strip()) > 0
        
        print("✅ Process recommendation content quality verified")
        return True
    except Exception as e:
        print(f"❌ Process recommendation content quality test failed: {e}")
        return False


def test_process_recommendation_blacklist_and_steps():
    """Ensure output avoids blacklisted tech terms and has sufficient numbered steps."""
    print("🔍 Testing blacklist filtering and minimum steps...")
    try:
        response = requests.get(f"{BASE_URL}/api/process-recommendation?project_type=research&project_size=large&industry=healthcare&methodology_preference=PMBOK")
        assert response.status_code == 200
        data = response.json()

        # The API returns HTML content for recommendations; inspect the text
        html = data.get("recommendations") or data.get("tailored_approach", {}).get("html", "")
        assert isinstance(html, str) and len(html) > 0

        lowered = html.lower()
        for term in ["postgres", "postgresql", "mysql", "sqlite", "postgis"]:
            assert term not in lowered

        # Count numbered steps at the beginning of lines
        lines = [ln for ln in html.splitlines() if ln.strip()]
        step_lines = [ln for ln in lines if ln.strip().startswith(tuple(str(i)+'.' for i in range(1, 10)))]
        assert len(step_lines) >= 8

        print("✅ Blacklist filtering and minimum steps verified")
        return True
    except Exception as e:
        print(f"❌ Blacklist/steps test failed: {e}")
        return False

def test_process_recommendation_error_handling():
    """Test error handling for invalid parameters."""
    print("🔍 Testing process recommendation error handling...")
    try:
        # Test with missing parameters (should still work with defaults)
        response = requests.get(f"{BASE_URL}/api/process-recommendation?project_type=software")
        # This should still work as other parameters have defaults
        assert response.status_code == 200
        
        # Test with invalid project type (should still work)
        response = requests.get(f"{BASE_URL}/api/process-recommendation?project_type=invalid&project_size=medium&industry=IT")
        assert response.status_code == 200
        
        print("✅ Process recommendation error handling working")
        return True
    except Exception as e:
        print(f"❌ Process recommendation error handling failed: {e}")
        return False

def run_process_recommendation_tests():
    """Run all process recommendation tests."""
    print("🧪 Running Process Recommendation Tests")
    print("=" * 50)
    
    tests = [
        test_process_recommendation_software,
        test_process_recommendation_construction,
        test_process_recommendation_small_project,
        test_process_recommendation_validation,
        test_process_recommendation_content_quality,
        test_process_recommendation_error_handling,
        test_process_recommendation_blacklist_and_steps
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()  # Add spacing between tests
    
    print("📊 Process Recommendation Test Results")
    print("=" * 45)
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    print(f"📈 Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🎉 All process recommendation tests passed!")
        return True
    else:
        print(f"\n⚠️  {total - passed} process recommendation tests failed.")
        return False

if __name__ == "__main__":
    success = run_process_recommendation_tests()
    sys.exit(0 if success else 1)
