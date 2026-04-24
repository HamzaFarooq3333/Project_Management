#!/usr/bin/env python3
"""
Page Number Verification Script
==============================

This script verifies that the page numbers in the embeddings match the PDF viewer pages.

Usage:
    python ingest/verify_page_numbers.py
"""

import sys
import pickle
from pathlib import Path
from typing import List, Dict, Any

# Add the parent directory to the path to import the search module
sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from app.services.search import get_engine
    print("✅ Successfully imported search engine")
except ImportError as e:
    print(f"❌ Failed to import search engine: {e}")
    sys.exit(1)

def verify_page_numbers():
    """
    Verify that page numbers in embeddings match PDF viewer pages.
    """
    print("🔍 Verifying Page Numbers in Embeddings")
    print("=" * 50)
    
    try:
        # Load the search engine
        engine = get_engine()
        print("✅ Search engine loaded successfully")
        
        # Test search to get some results
        print("\n📊 Testing search functionality...")
        results = engine.query("project management", k=5)
        
        if not results:
            print("❌ No search results found")
            return False
        
        print(f"✅ Found {len(results)} search results")
        
        # Verify page numbers
        print("\n🔍 Verifying page numbers...")
        page_issues = []
        
        for i, result in enumerate(results):
            page = result.get('page', 'Unknown')
            standard = result.get('standard', 'Unknown')
            link = result.get('link', '')
            
            print(f"  Result {i+1}: {standard} page {page}")
            
            # Check if page number is valid (should be >= 1)
            if isinstance(page, (int, float)) and page < 1:
                page_issues.append(f"Result {i+1}: Page {page} is not 1-based")
            
            # Check if link contains correct page number
            if link and f"#page={page}" not in link:
                page_issues.append(f"Result {i+1}: Link {link} doesn't match page {page}")
        
        if page_issues:
            print(f"\n❌ Found {len(page_issues)} page number issues:")
            for issue in page_issues:
                print(f"  • {issue}")
            return False
        else:
            print(f"\n✅ All page numbers verified correctly!")
            return True
            
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pdf_links():
    """
    Test that PDF links are correctly formatted.
    """
    print("\n🔗 Testing PDF Link Generation")
    print("=" * 40)
    
    try:
        engine = get_engine()
        results = engine.query("risk management", k=3)
        
        for i, result in enumerate(results):
            standard = result.get('standard', 'Unknown')
            page = result.get('page', 'Unknown')
            link = result.get('link', '')
            
            print(f"\nResult {i+1}:")
            print(f"  Standard: {standard}")
            print(f"  Page: {page}")
            print(f"  Link: {link}")
            
            # Verify link format
            if link:
                if f"#page={page}" in link:
                    print(f"  ✅ Link correctly formatted")
                else:
                    print(f"  ❌ Link format issue: expected #page={page}")
            else:
                print(f"  ⚠️  No link generated")
                
    except Exception as e:
        print(f"❌ Error testing PDF links: {e}")

def main():
    """
    Main verification function.
    """
    print("🔍 Page Number Verification")
    print("=" * 50)
    
    # Verify page numbers
    page_verification = verify_page_numbers()
    
    # Test PDF links
    test_pdf_links()
    
    # Summary
    print(f"\n📋 Verification Summary")
    print("=" * 30)
    if page_verification:
        print("✅ Page numbers are correctly formatted")
        print("✅ Embeddings should work with PDF viewer")
        print("✅ PDF links should navigate to correct pages")
    else:
        print("❌ Page number issues detected")
        print("❌ PDF links may not work correctly")
    
    return page_verification

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
