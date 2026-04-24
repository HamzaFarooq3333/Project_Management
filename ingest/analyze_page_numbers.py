#!/usr/bin/env python3
"""
Page Number Analysis Script
==========================

This script analyzes PDF files to understand page numbering issues and provides
recommendations for correct page mapping between PDF viewer and embedding storage.

Usage:
    python ingest/analyze_page_numbers.py
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from pypdf import PdfReader
import json

BASE_DIR = Path(__file__).resolve().parents[1]
BOOKS_DIR = BASE_DIR / 'Books'

# Standard to filename mapping
STANDARD_MAPPING = {
    'PMBOK': '02 Project Management - PMBOK.pptx.pdf',
    'PRINCE2': '03 Project Management - Prince2.pptx.pdf',
    'ISO21500': 'ISO-21500-2021.pdf',
    'ISO21502': 'ISO-21502-2020.pdf',
}

def analyze_pdf_structure(pdf_path: Path, standard: str) -> Dict[str, Any]:
    """
    Analyze PDF structure to understand page numbering.
    """
    print(f"\n=== Analyzing {standard} ===")
    print(f"File: {pdf_path.name}")
    
    if not pdf_path.exists():
        print(f"❌ File not found: {pdf_path}")
        return {}
    
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    
    analysis = {
        'standard': standard,
        'filename': pdf_path.name,
        'total_pages': total_pages,
        'page_analysis': [],
        'recommendations': []
    }
    
    print(f"Total PDF pages: {total_pages}")
    
    # Analyze first few pages and last few pages
    sample_pages = [0, 1, 2, total_pages-3, total_pages-2, total_pages-1] if total_pages > 6 else list(range(total_pages))
    
    for i in sample_pages:
        try:
            page = reader.pages[i]
            text = page.extract_text() or ''
            
            # Clean text for analysis
            clean_text = ' '.join(text.split())[:200]  # First 200 chars
            
            # Look for page numbers in text
            page_numbers = re.findall(r'\b(\d+)\b', text)
            potential_page_nums = [int(n) for n in page_numbers if 1 <= int(n) <= total_pages + 10]
            
            page_info = {
                'pdf_index': i,  # 0-based PDF index
                'viewer_page': i + 1,  # What user sees (1-based)
                'text_preview': clean_text,
                'found_page_numbers': potential_page_nums,
                'text_length': len(text)
            }
            
            analysis['page_analysis'].append(page_info)
            
            print(f"  Page {i+1} (index {i}): {len(text)} chars, found numbers: {potential_page_nums[:3]}")
            
        except Exception as e:
            print(f"  Error reading page {i}: {e}")
    
    # Generate recommendations
    recommendations = []
    
    # Check if PDF has consistent page numbering
    found_page_nums = []
    for page_info in analysis['page_analysis']:
        found_page_nums.extend(page_info['found_page_numbers'])
    
    if found_page_nums:
        recommendations.append(f"Found page numbers in text: {sorted(set(found_page_nums))[:10]}")
    
    # Check for common PDF issues
    if total_pages > 100:
        recommendations.append("Large document - consider chunking strategy")
    
    # Check first page content
    first_page = analysis['page_analysis'][0] if analysis['page_analysis'] else None
    if first_page and 'cover' in first_page['text_preview'].lower():
        recommendations.append("First page appears to be cover page")
    
    analysis['recommendations'] = recommendations
    
    return analysis

def generate_page_mapping_strategy(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a strategy for correct page mapping.
    """
    strategy = {
        'approach': 'viewer_page_based',
        'explanation': 'Use 1-based page numbers that match PDF viewer',
        'mapping_rules': [],
        'implementation_notes': []
    }
    
    strategy['mapping_rules'] = [
        "PDF index (0-based) + 1 = Viewer page (1-based)",
        "Store viewer_page in embeddings for user display",
        "Use viewer_page for PDF links (#page=N)",
        "Keep pdf_index for internal reference if needed"
    ]
    
    strategy['implementation_notes'] = [
        "When creating embeddings: page = pdf_index + 1",
        "When generating PDF links: /pdf/{standard}#page={viewer_page}",
        "When displaying results: show viewer_page to user",
        "Ensure consistency between stored page numbers and PDF viewer"
    ]
    
    return strategy

def main():
    """
    Main analysis function.
    """
    print("🔍 PDF Page Number Analysis")
    print("=" * 50)
    
    if not BOOKS_DIR.exists():
        print(f"❌ Books directory not found: {BOOKS_DIR}")
        return
    
    all_analyses = []
    
    # Analyze each PDF
    for standard, filename in STANDARD_MAPPING.items():
        pdf_path = BOOKS_DIR / filename
        analysis = analyze_pdf_structure(pdf_path, standard)
        if analysis:
            all_analyses.append(analysis)
    
    # Generate strategy
    strategy = generate_page_mapping_strategy(all_analyses)
    
    # Save analysis results
    results = {
        'analyses': all_analyses,
        'strategy': strategy,
        'summary': {
            'total_standards': len(all_analyses),
            'total_pages': sum(a['total_pages'] for a in all_analyses),
            'issues_found': []
        }
    }
    
    # Save to file
    output_file = BASE_DIR / 'ingest' / 'page_analysis_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📊 Analysis Summary:")
    print(f"  Standards analyzed: {len(all_analyses)}")
    print(f"  Total pages: {sum(a['total_pages'] for a in all_analyses)}")
    print(f"  Results saved to: {output_file}")
    
    print(f"\n💡 Recommended Strategy:")
    for rule in strategy['mapping_rules']:
        print(f"  • {rule}")
    
    print(f"\n🔧 Implementation Notes:")
    for note in strategy['implementation_notes']:
        print(f"  • {note}")
    
    print(f"\n✅ Analysis complete! Use these recommendations to fix build_index_final.py")

if __name__ == '__main__':
    main()
