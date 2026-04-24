#!/usr/bin/env python3
"""
Search Functionality Tests
==========================

Test the core search functionality and semantic search engine.
"""

import sys
from pathlib import Path

# Add the parent directory to the path
sys.path.append(str(Path(__file__).resolve().parents[1]))

def test_search_engine_import():
    """Test that the search engine can be imported."""
    print("🔍 Testing search engine import...")
    try:
        from app.services.search import get_engine, SemanticSearch
        print("✅ Search engine import successful")
        return True
    except Exception as e:
        print(f"❌ Search engine import failed: {e}")
        return False

def test_search_engine_initialization():
    """Test that the search engine initializes correctly."""
    print("🔍 Testing search engine initialization...")
    try:
        from app.services.search import get_engine
        engine = get_engine()
        assert engine is not None
        assert hasattr(engine, 'query')
        assert hasattr(engine, 'compare_detailed')
        assert hasattr(engine, 'analyze_all_books_auto')
        print("✅ Search engine initialization successful")
        return True
    except Exception as e:
        print(f"❌ Search engine initialization failed: {e}")
        return False

def test_basic_search():
    """Test basic search functionality."""
    print("🔍 Testing basic search...")
    try:
        from app.services.search import get_engine
        engine = get_engine()
        
        # Test basic query
        results = engine.query("project management", k=5)
        assert isinstance(results, list)
        assert len(results) > 0
        
        # Check result structure
        result = results[0]
        assert "standard" in result
        assert "text" in result
        assert "page" in result
        assert "score" in result
        assert "link" in result
        
        print(f"✅ Basic search successful: {len(results)} results")
        return True
    except Exception as e:
        print(f"❌ Basic search failed: {e}")
        return False

def test_search_with_filter():
    """Test search with standard filter."""
    print("🔍 Testing search with standard filter...")
    try:
        from app.services.search import get_engine
        engine = get_engine()
        
        # Test PMBOK filter
        results = engine.query("risk management", k=5, standard_filter="PMBOK")
        assert isinstance(results, list)
        if results:
            assert all("PMBOK" in result["standard"] for result in results)
            print("✅ PMBOK filter working")
        
        # Test PRINCE2 filter
        results = engine.query("project planning", k=5, standard_filter="PRINCE2")
        assert isinstance(results, list)
        if results:
            assert all("PRINCE" in result["standard"] for result in results)
            print("✅ PRINCE2 filter working")
        
        print("✅ Search with filter successful")
        return True
    except Exception as e:
        print(f"❌ Search with filter failed: {e}")
        return False

def test_detailed_comparison():
    """Test detailed comparison functionality."""
    print("🔍 Testing detailed comparison...")
    try:
        from app.services.search import get_engine
        engine = get_engine()
        
        result = engine.compare_detailed("stakeholder management", k=10)
        assert isinstance(result, dict)
        assert "summaries" in result
        assert "similarities" in result
        assert "differences" in result
        assert "uniques" in result
        
        print("✅ Detailed comparison successful")
        return True
    except Exception as e:
        print(f"❌ Detailed comparison failed: {e}")
        return False

def test_analysis_functionality():
    """Test analysis functionality."""
    print("🔍 Testing analysis functionality...")
    try:
        from app.services.search import get_engine
        engine = get_engine()
        
        result = engine.analyze_all_books_auto(k=20, threshold=0.5)
        assert isinstance(result, dict)
        assert "points" in result
        assert "threshold" in result
        
        if result["points"]:
            point = result["points"][0]
            assert "x" in point
            assert "y" in point
            assert "label" in point
            assert "standard" in point
        
        print("✅ Analysis functionality successful")
        return True
    except Exception as e:
        print(f"❌ Analysis functionality failed: {e}")
        return False

def test_page_number_accuracy():
    """Test that page numbers are accurate."""
    print("🔍 Testing page number accuracy...")
    try:
        from app.services.search import get_engine
        engine = get_engine()
        
        results = engine.query("project management", k=10)
        
        # Check that all page numbers are positive integers
        for result in results:
            page = result.get("page")
            assert isinstance(page, int)
            assert page > 0
            assert page <= 50  # Reasonable upper bound
        
        print("✅ Page number accuracy verified")
        return True
    except Exception as e:
        print(f"❌ Page number accuracy test failed: {e}")
        return False

def test_link_generation():
    """Test that PDF links are generated correctly."""
    print("🔍 Testing link generation...")
    try:
        from app.services.search import get_engine
        engine = get_engine()
        
        results = engine.query("risk management", k=5)
        
        for result in results:
            link = result.get("link")
            if link:
                assert link.startswith("/pdf/")
                assert "#page=" in link
                page_num = link.split("#page=")[1]
                assert page_num.isdigit()
                assert int(page_num) > 0
        
        print("✅ Link generation working correctly")
        return True
    except Exception as e:
        print(f"❌ Link generation test failed: {e}")
        return False

def test_metadata_consistency():
    """Test that metadata is consistent and complete."""
    print("🔍 Testing metadata consistency...")
    try:
        from app.services.search import get_engine
        engine = get_engine()
        
        results = engine.query("project planning", k=5)
        
        for result in results:
            # Check required fields
            assert "standard" in result
            assert "text" in result
            assert "page" in result
            assert "score" in result
            
            # Check field types
            assert isinstance(result["standard"], str)
            assert isinstance(result["text"], str)
            assert isinstance(result["page"], int)
            assert isinstance(result["score"], (int, float))
            
            # Check field values
            assert len(result["standard"]) > 0
            assert len(result["text"]) > 0
            assert result["page"] > 0
            assert 0 <= result["score"] <= 1
        
        print("✅ Metadata consistency verified")
        return True
    except Exception as e:
        print(f"❌ Metadata consistency test failed: {e}")
        return False

def run_search_tests():
    """Run all search functionality tests."""
    print("Running Search Functionality Tests")
    print("=" * 50)
    
    tests = [
        test_search_engine_import,
        test_search_engine_initialization,
        test_basic_search,
        test_search_with_filter,
        test_detailed_comparison,
        test_analysis_functionality,
        test_page_number_accuracy,
        test_link_generation,
        test_metadata_consistency
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()  # Add spacing between tests
    
    print("📊 Search Test Results Summary")
    print("=" * 40)
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    print(f"📈 Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\nAll search tests passed!")
        return True
    else:
        print(f"\n{total - passed} search tests failed.")
        return False

if __name__ == "__main__":
    success = run_search_tests()
    sys.exit(0 if success else 1)
