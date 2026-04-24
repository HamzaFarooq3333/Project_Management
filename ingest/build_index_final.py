import os
import re
from pathlib import Path
from typing import List, Tuple, Dict, Any
import faiss
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
from bs4 import BeautifulSoup  # type: ignore
try:
    from ebooklib import epub  # type: ignore
except Exception:
    epub = None
import pickle
import numpy as np
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parents[1]
BOOKS_DIR = BASE_DIR / 'Books'
INDEX_DIR = BASE_DIR / 'data'
INDEX_DIR.mkdir(exist_ok=True, parents=True)

MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'

def clean_text(text: str) -> str:
    """Clean and normalize text for better processing."""
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters but keep important punctuation
    text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)]', '', text)
    # Remove page numbers and headers/footers
    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
    # Remove very short lines (likely headers/footers)
    lines = text.split('\n')
    lines = [line.strip() for line in lines if len(line.strip()) > 10]
    return ' '.join(lines).strip()


def _read_html_file(path: Path) -> str:
    try:
        html = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        html = path.read_text(errors='ignore')
    soup = BeautifulSoup(html, 'lxml')
    # Remove scripts/styles
    for tag in soup(['script','style','noscript']):
        tag.decompose()
    text = soup.get_text(separator=' ')
    return clean_text(text)


def _read_epub_file(path: Path) -> str:
    if epub is None:
        raise RuntimeError('ebooklib not installed; cannot read EPUB')
    book = epub.read_epub(str(path))
    texts: List[str] = []
    for item in book.get_items():
        if item.get_type() == 9:  # DOCUMENT
            soup = BeautifulSoup(item.get_content(), 'lxml')
            for t in soup(['script','style','noscript']):
                t.decompose()
            texts.append(soup.get_text(separator=' '))
    return clean_text(' '.join(texts))

def smart_chunk_text(text: str, max_chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks for better context preservation."""
    if len(text) <= max_chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + max_chunk_size
        
        # Try to break at sentence boundaries
        if end < len(text):
            # Look for sentence endings within the last 200 characters
            search_start = max(start, end - 200)
            sentence_end = text.rfind('.', search_start, end)
            if sentence_end > start + max_chunk_size // 2:  # Don't make chunks too small
                end = sentence_end + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start position with overlap
        start = end - overlap
        if start >= len(text):
            break
    
    return chunks

def extract_metadata_from_text(text: str, standard: str) -> Dict[str, Any]:
    """Extract metadata like section titles, keywords, etc."""
    metadata = {
        'standard': standard,
        'has_numbers': bool(re.search(r'\d+', text)),
        'has_uppercase': bool(re.search(r'[A-Z]{3,}', text)),
        'word_count': len(text.split()),
        'sentence_count': len(re.findall(r'[.!?]+', text))
    }
    
    # Try to extract section titles (lines that are mostly uppercase or short)
    lines = text.split('\n')
    potential_titles = [line.strip() for line in lines 
                       if len(line.strip()) < 100 and 
                       (line.isupper() or line.istitle()) and 
                       len(line.strip()) > 5]
    
    if potential_titles:
        metadata['potential_titles'] = potential_titles[:3]  # Keep first 3
    
    return metadata

def read_pdf_chunks_final(pdf_path: Path, standard: str) -> List[Tuple[str, str, int, Dict[str, Any]]]:
    """
    PDF reading with CORRECTED page numbers that match PDF viewer.
    
    CRITICAL: This function ensures that the page numbers stored in embeddings
    exactly match what users see in PDF viewers (1-based numbering).
    """
    print(f"Processing {pdf_path.name}...")
    reader = PdfReader(str(pdf_path))
    chunks = []
    total_pages = len(reader.pages)
    
    print(f"Total PDF pages: {total_pages}")
    print(f"Page numbering strategy: PDF index (0-based) + 1 = Viewer page (1-based)")
    
    for i, page in enumerate(tqdm(reader.pages, desc=f"Reading {standard}"), start=0):
        try:
            text = page.extract_text() or ''
        except Exception as e:
            print(f"Error reading page {i+1} of {pdf_path.name}: {e}")
            text = ''
        
        if not text.strip():
            continue
            
        # Clean the text
        cleaned_text = clean_text(text)
        if len(cleaned_text) < 50:  # Skip very short pages
            continue
        
        # CRITICAL: Use 1-based page numbering that matches PDF viewer
        # PDF index 0 = Viewer page 1, PDF index 1 = Viewer page 2, etc.
        viewer_page = i + 1
        
        # Create smart chunks
        text_chunks = smart_chunk_text(cleaned_text, max_chunk_size=800, overlap=150)
        
        for chunk_idx, chunk in enumerate(text_chunks):
            if len(chunk.strip()) < 30:  # Skip very short chunks
                continue
                
            # Extract metadata
            metadata = extract_metadata_from_text(chunk, standard)
            metadata.update({
                'page': viewer_page,  # CRITICAL: This must match PDF viewer page number
                'pdf_page_index': i,  # Keep original PDF index for reference
                'chunk_index': chunk_idx,
                'total_chunks_page': len(text_chunks),
                'chunk_length': len(chunk),
                'page_numbering_verified': True  # Flag to indicate correct numbering
            })
            
            chunks.append((standard, chunk, viewer_page, metadata))
    
    print(f"Extracted {len(chunks)} chunks from {pdf_path.name}")
    print(f"Page numbers used: 1 to {max([chunk[2] for chunk in chunks]) if chunks else 0}")
    return chunks


def read_html_chunks(path: Path, standard: str) -> List[Tuple[str, str, int, Dict[str, Any]]]:
    """Read HTML file and produce pseudo-page chunks with anchors.
    Uses chunk index as page surrogate for deep-linking.
    """
    text = _read_html_file(path)
    chunks: List[Tuple[str, str, int, Dict[str, Any]]] = []
    text_chunks = smart_chunk_text(text, max_chunk_size=800, overlap=150)
    for i, chunk in enumerate(text_chunks, start=1):
        meta = extract_metadata_from_text(chunk, standard)
        meta.update({'page': i, 'source_file': path.name, 'format': 'html'})
        chunks.append((standard, chunk, i, meta))
    return chunks


def read_epub_chunks(path: Path, standard: str) -> List[Tuple[str, str, int, Dict[str, Any]]]:
    """Read EPUB file and chunk content. Uses spine position as page surrogate."""
    text = _read_epub_file(path)
    chunks: List[Tuple[str, str, int, Dict[str, Any]]] = []
    text_chunks = smart_chunk_text(text, max_chunk_size=800, overlap=150)
    for i, chunk in enumerate(text_chunks, start=1):
        meta = extract_metadata_from_text(chunk, standard)
        meta.update({'page': i, 'source_file': path.name, 'format': 'epub'})
        chunks.append((standard, chunk, i, meta))
    return chunks

def collect_corpus_final() -> Tuple[List[Tuple[str, str, int, Dict[str, Any]]], Dict[str, Any]]:
    """Collect corpus with final corrected page numbers."""
    corpus = []
    stats = {
        'total_chunks': 0,
        'total_pages': 0,
        'standards': {},
        'avg_chunk_length': 0,
        'total_text_length': 0
    }
    
    mapping = {
        'PMBOK': '02 Project Management - PMBOK.pptx.pdf',
        'PRINCE2': '03 Project Management - Prince2.pptx.pdf',
        'ISO21500': 'ISO-21500-2021.pdf',
        'ISO21502': 'ISO-21502-2020.pdf',
    }
    
    for standard, filename in mapping.items():
        path = BOOKS_DIR / filename
        alt_html = BOOKS_DIR / f"{standard}.html"
        alt_epub = BOOKS_DIR / f"{standard}.epub"
        if path.exists():
            print(f"\n=== Processing {standard} (PDF) ===")
            chunks = read_pdf_chunks_final(path, standard)
        elif alt_html.exists():
            print(f"\n=== Processing {standard} (HTML) ===")
            chunks = read_html_chunks(alt_html, standard)
        elif alt_epub.exists():
            print(f"\n=== Processing {standard} (EPUB) ===")
            chunks = read_epub_chunks(alt_epub, standard)
        else:
            print(f"Warning: No source found for {standard} (expected PDF/HTML/EPUB)")
            continue
        corpus.extend(chunks)
        
        # Update statistics
        standard_stats = {
            'chunks': len(chunks),
            'pages': len(set(chunk[2] for chunk in chunks)),  # Use viewer page numbers
            'avg_length': np.mean([len(chunk[1]) for chunk in chunks]) if chunks else 0
        }
        stats['standards'][standard] = standard_stats
        stats['total_chunks'] += len(chunks)
        stats['total_pages'] += standard_stats['pages']
    
    if corpus:
        stats['avg_chunk_length'] = np.mean([len(chunk[1]) for chunk in corpus])
        stats['total_text_length'] = sum([len(chunk[1]) for chunk in corpus])
    
    return corpus, stats

def create_final_index(corpus: List[Tuple[str, str, int, Dict[str, Any]]], 
                      model: SentenceTransformer) -> Tuple[faiss.Index, List[Dict[str, Any]]]:
    """Create final FAISS index with CORRECTED page numbers."""
    print(f"\n=== Creating Final Index with CORRECTED Page Numbers ===")
    print(f"Processing {len(corpus)} chunks...")
    print(f"Page numbering verification: Ensuring 1-based viewer page numbers")
    
    # Prepare texts and metadata
    texts = [chunk[1] for chunk in corpus]
    metadata_list = []
    
    # Verify page numbers are correct
    page_numbers = [chunk[2] for chunk in corpus]
    min_page, max_page = min(page_numbers), max(page_numbers)
    print(f"Page number range: {min_page} to {max_page}")
    
    for i, (standard, text, page, meta) in enumerate(corpus):
        # CRITICAL: Verify page number is 1-based (viewer page)
        if page < 1:
            print(f"WARNING: Page number {page} is not 1-based! This will cause PDF link issues.")
        
        enhanced_meta = {
            'standard': standard,
            'text': text,
            'page': page,  # CRITICAL: This must be 1-based viewer page number
            'chunk_id': i,
            'metadata': meta,
            'page_numbering_verified': True
        }
        metadata_list.append(enhanced_meta)
    
    # Create embeddings with better parameters
    print("Generating embeddings...")
    embeddings = model.encode(
        texts, 
        batch_size=16,
        show_progress_bar=True, 
        convert_to_numpy=True, 
        normalize_embeddings=True,
        device='cpu'
    )
    
    print(f"Generated embeddings shape: {embeddings.shape}")
    
    # Create FAISS index
    dim = embeddings.shape[1]
    print(f"Creating FAISS index with dimension {dim}...")
    
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype('float32'))
    
    print(f"Index created with {index.ntotal} vectors")
    return index, metadata_list

def save_final_index_and_metadata(index: faiss.Index, metadata_list: List[Dict[str, Any]], 
                                 stats: Dict[str, Any]):
    """Save final index and metadata with correct page numbers."""
    print(f"\n=== Saving Final Index and Metadata ===")
    
    # Save FAISS index
    faiss.write_index(index, str(INDEX_DIR / 'faiss.index'))
    print(f"FAISS index saved to {INDEX_DIR / 'faiss.index'}")
    
    # Save metadata
    with open(INDEX_DIR / 'meta.pkl', 'wb') as f:
        pickle.dump(metadata_list, f)
    print(f"Metadata saved to {INDEX_DIR / 'meta.pkl'}")
    
    # Save statistics
    with open(INDEX_DIR / 'stats.pkl', 'wb') as f:
        pickle.dump(stats, f)
    print(f"Statistics saved to {INDEX_DIR / 'stats.pkl'}")
    
    # Print summary with page number verification
    print(f"\n=== Final Indexing Complete ===")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Total pages: {stats['total_pages']}")
    print(f"Average chunk length: {stats['avg_chunk_length']:.1f} characters")
    print(f"Total text length: {stats['total_text_length']:,} characters")
    print(f"\nPer standard (with correct page numbers):")
    for standard, stat in stats['standards'].items():
        print(f"  {standard}: {stat['chunks']} chunks, {stat['pages']} pages, "
              f"avg length: {stat['avg_length']:.1f}")

def main():
    print("=== Final Document Indexing with CORRECTED Page Numbers ===")
    print(f"Books directory: {BOOKS_DIR}")
    print(f"Index directory: {INDEX_DIR}")
    print(f"CRITICAL: This version ensures page numbers match PDF viewer (1-based)")
    
    # Load model
    print(f"\nLoading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    
    # Collect corpus with correct page numbers
    print(f"\n=== Collecting Corpus with CORRECTED Page Numbers ===")
    corpus, stats = collect_corpus_final()
    
    if not corpus:
        raise SystemExit('No PDFs found or processed in Books/')
    
    # Verify page numbers before indexing
    print(f"\n=== Verifying Page Numbers ===")
    page_numbers = [chunk[2] for chunk in corpus]
    min_page, max_page = min(page_numbers), max(page_numbers)
    print(f"Page number range: {min_page} to {max_page}")
    
    if min_page < 1:
        print(f"[ERROR] Found page number {min_page} which is not 1-based!")
        print(f"This will cause PDF link issues. Please check the page numbering logic.")
        raise SystemExit("Page numbering error")
    
    print("[OK] Page numbers verified: All pages are 1-based (viewer pages)")
    
    # Create final index
    index, metadata_list = create_final_index(corpus, model)
    
    # Save everything
    save_final_index_and_metadata(index, metadata_list, stats)
    
    print("\nFinal indexing completed successfully!")
    print(f"Index file: {INDEX_DIR / 'faiss.index'}")
    print(f"Metadata file: {INDEX_DIR / 'meta.pkl'}")
    print(f"Statistics file: {INDEX_DIR / 'stats.pkl'}")
    print(f"\nPDF links will now work correctly with page numbers 1-{max_page}")

if __name__ == '__main__':
    main()
