from __future__ import annotations

import os
import pickle
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple

import numpy as np

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / 'data'
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'

_WORD_RE = re.compile(r"[a-zA-Z0-9']+")


def _tokenize(text: str) -> List[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text or "")]


def _pdf_link_for_standard(standard: str, page: int) -> str | None:
    standard_key = (standard or "").upper()
    if 'PMBOK' in standard_key:
        pdf_endpoint = '/pdf/PMBOK'
    elif 'PRINCE' in standard_key:
        pdf_endpoint = '/pdf/PRINCE2'
    elif 'ISO21500' in standard_key:
        pdf_endpoint = '/pdf/ISO21500'
    elif 'ISO21502' in standard_key:
        pdf_endpoint = '/pdf/ISO21502'
    else:
        pdf_endpoint = ''
    return f"{pdf_endpoint}#page={page}" if pdf_endpoint else None


class LightSemanticSearch:
    """Vercel-safe fallback search (no torch/transformers/faiss/sentence-transformers).

    Uses `data/meta.pkl` and a simple keyword-based relevance score.
    This keeps the deployed bundle small enough for Vercel Lambda limits.
    """

    def __init__(self) -> None:
        with open(DATA_DIR / 'meta.pkl', 'rb') as f:
            self.meta = pickle.load(f)

    def query(self, q: str, k: int = 10, standard_filter: str | None = None) -> List[Dict[str, Any]]:
        q_tokens = _tokenize(q)
        q_set = set(q_tokens)
        if not q_set:
            # Empty query -> return first k snippets (stable demo behavior)
            q_set = set()

        results: List[Dict[str, Any]] = []
        for meta in self.meta:
            if isinstance(meta, dict):
                standard = meta.get('standard')
                text = meta.get('text') or ''
                page = int(meta.get('page') or 0)
            else:
                standard, text, page = meta
                text = text or ''
                page = int(page or 0)

            standard_key = str(standard or '').upper()
            if standard_filter and str(standard_filter).upper() not in standard_key:
                continue

            text_tokens = _tokenize(text)
            if q_set:
                # simple term frequency score
                score = float(sum(1 for t in text_tokens if t in q_set))
                if score <= 0:
                    continue
            else:
                score = 0.0

            results.append({
                'standard': standard,
                'text': text[:500],
                'page': page,
                'score': score,
                'link': _pdf_link_for_standard(str(standard or ''), page),
            })

        results.sort(key=lambda r: (r.get('score', 0.0), -(r.get('page', 0) or 0)), reverse=True)
        return results[:k]

    def _encode_texts(self, texts: List[str]) -> np.ndarray:
        # Not available in light mode (kept for API compatibility)
        raise RuntimeError("Embeddings disabled in light mode")

    def compare_detailed(self, topic: str, k: int = 30) -> Dict[str, Any]:
        hits = self.query(topic, k=k)
        buckets: Dict[str, List[Dict[str, Any]]] = {'PMBOK': [], 'PRINCE2': [], 'ISO21500': [], 'ISO21502': []}
        for r in hits:
            sk = str(r.get('standard') or '').upper()
            if 'PMBOK' in sk:
                buckets['PMBOK'].append(r)
            elif 'PRINCE' in sk:
                buckets['PRINCE2'].append(r)
            elif 'ISO21500' in sk:
                buckets['ISO21500'].append(r)
            elif 'ISO21502' in sk:
                buckets['ISO21502'].append(r)

        summaries = {k: (v[0] if v else None) for k, v in buckets.items()}
        return {
            'summaries': summaries,
            'similarities': [],
            'differences': [],
            'uniques': [],
            'note': 'Light mode (keyword search). Similarity/unique analytics are disabled on Vercel.'
        }

    def analyze_two_books(self, *args, **kwargs) -> Dict[str, Any]:
        return {'bookA': {'key': '', 'points': []}, 'bookB': {'key': '', 'points': []}, 'threshold': kwargs.get('threshold', 0.6), 'disabled': True}

    def analyze_all_books_auto(self, *args, **kwargs) -> Dict[str, Any]:
        return {'points': [], 'unique_points': [], 'similar_pairs': [], 'dissimilar_pairs': [], 'book_stats': {}, 'threshold': kwargs.get('threshold', 0.6), 'unique_threshold': kwargs.get('unique_threshold', 0.35), 'disabled': True}

    def get_all_snippets_for_standard(self, standard: str) -> List[Dict[str, Any]]:
        std_key = str(standard or '').upper()
        snippets: List[Dict[str, Any]] = []
        for meta_item in self.meta:
            if isinstance(meta_item, dict):
                item_standard = str(meta_item.get('standard', '')).upper()
                if std_key in item_standard:
                    snippets.append({'standard': meta_item.get('standard'), 'text': meta_item.get('text', ''), 'page': meta_item.get('page', 0)})
            else:
                item_standard, text, page = meta_item
                if std_key in str(item_standard).upper():
                    snippets.append({'standard': item_standard, 'text': text, 'page': page})
        snippets.sort(key=lambda s: s.get('page', 0))
        return snippets


class SemanticSearch:
    def __init__(self) -> None:
        # Heavy dependencies (FAISS + SentenceTransformers). Not suitable for Vercel bundle limits.
        import faiss  # type: ignore
        from sentence_transformers import SentenceTransformer  # type: ignore

        self.model = SentenceTransformer(MODEL_NAME)
        self.index = faiss.read_index(str(DATA_DIR / 'faiss.index'))
        with open(DATA_DIR / 'meta.pkl', 'rb') as f:
            self.meta = pickle.load(f)

    def query(self, q: str, k: int = 10, standard_filter: str | None = None) -> List[Dict[str, Any]]:
        qv = self.model.encode([q], normalize_embeddings=True)
        scores, ids = self.index.search(qv, k)
        results: List[Dict[str, Any]] = []
        for idx, score in zip(ids[0], scores[0]):
            if idx == -1:
                continue
            
            # Handle new metadata format
            meta = self.meta[idx]
            if isinstance(meta, dict):
                # New format with enhanced metadata
                standard = meta['standard']
                text = meta['text']
                page = meta['page']
            else:
                # Old format (tuple)
                standard, text, page = meta
            
            link = _pdf_link_for_standard(str(standard), int(page))
            if standard_filter and standard_filter.upper() not in standard_key:
                continue
            results.append({
                'standard': standard,
                'text': text[:500],
                'page': page,
                'score': float(score),
                'link': link
            })
        return results

    def _encode_texts(self, texts: List[str]) -> np.ndarray:
        return self.model.encode(texts, normalize_embeddings=True)

    def compare_detailed(self, topic: str, k: int = 30) -> Dict[str, Any]:
        # Retrieve top-k, then bucket by standard
        hits = self.query(topic, k=k)
        buckets: Dict[str, List[Dict[str, Any]]] = {'PMBOK': [], 'PRINCE2': [], 'ISO21500': [], 'ISO21502': []}
        for r in hits:
            sk = r['standard'].upper()
            if 'PMBOK' in sk:
                buckets['PMBOK'].append(r)
            elif 'PRINCE' in sk:
                buckets['PRINCE2'].append(r)
            elif 'ISO21500' in sk:
                buckets['ISO21500'].append(r)
            elif 'ISO21502' in sk:
                buckets['ISO21502'].append(r)

        def top_summary(lst: List[Dict[str, Any]]) -> Dict[str, Any] | None:
            return lst[0] if lst else None

        summaries = {k: top_summary(v) for k, v in buckets.items()}

        # Build similarity matrix across top N per standard (use up to 5 each)
        selections: List[Tuple[str, Dict[str, Any]]] = []
        for std, items in buckets.items():
            for r in items[:5]:
                selections.append((std, r))
        if not selections:
            return {'summaries': summaries, 'similarities': [], 'differences': [], 'uniques': []}

        texts = [r['text'] for _, r in selections]
        vecs = self._encode_texts(texts)
        sim_matrix = np.matmul(vecs, vecs.T)

        # Identify pairs across different standards with high similarity
        pairs = []
        n = len(selections)
        for i in range(n):
            for j in range(i+1, n):
                si, ri = selections[i]
                sj, rj = selections[j]
                if si == sj:
                    continue
                sim = float(sim_matrix[i, j])
                pairs.append({'a': {'standard': si, 'text': ri['text'], 'link': ri['link']},
                              'b': {'standard': sj, 'text': rj['text'], 'link': rj['link']},
                              'similarity': sim})

        # Thresholds for labeling
        high = 0.6
        low = 0.35
        similarities = [p for p in pairs if p['similarity'] >= high]
        differences = [p for p in pairs if low <= p['similarity'] < high]

        # Unique: items that have no pair above low similarity
        indices_with_match = set()
        for p in similarities + differences:
            # Reconstruct indices by matching text; approximate via link+standard
            for idx, (std, r) in enumerate(selections):
                if (r['link'] == p['a']['link'] and std == p['a']['standard']) or (r['link'] == p['b']['link'] and std == p['b']['standard']):
                    indices_with_match.add(idx)
        uniques = []
        for idx, (std, r) in enumerate(selections):
            if idx not in indices_with_match:
                uniques.append({'standard': std, 'text': r['text'], 'link': r['link']})

        return {
            'summaries': summaries,
            'similarities': sorted(similarities, key=lambda x: -x['similarity'])[:10],
            'differences': sorted(differences, key=lambda x: -x['similarity'])[:10],
            'uniques': uniques[:10]
        }

    def analyze_two_books(self, topic: str, book_a: str, book_b: str, k: int = 50, threshold: float = 0.6) -> Dict[str, Any]:
        # Normalize book keys
        def norm_key(s: str) -> str:
            s = s.upper()
            if s.startswith('ISO21500'):
                return 'ISO21500'
            if s.startswith('ISO21502'):
                return 'ISO21502'
            if 'PRINCE' in s:
                return 'PRINCE2'
            if 'PMBOK' in s:
                return 'PMBOK'
            return s

        a_key = norm_key(book_a)
        b_key = norm_key(book_b)

        # Retrieve top-k for each book
        a_hits = self.query(topic, k=k, standard_filter=a_key)
        b_hits = self.query(topic, k=k, standard_filter=b_key)

        a_texts = [h['text'] for h in a_hits]
        b_texts = [h['text'] for h in b_hits]
        if not a_texts or not b_texts:
            return {'bookA': {'key': a_key, 'points': []}, 'bookB': {'key': b_key, 'points': []}, 'threshold': threshold}

        a_vecs = self._encode_texts(a_texts)
        b_vecs = self._encode_texts(b_texts)

        # Similarity matrix A x B
        sim = np.matmul(a_vecs, b_vecs.T)
        a_similar = (sim.max(axis=1) >= threshold)
        b_similar = (sim.max(axis=0) >= threshold)

        # PCA to 2D on combined vectors
        combined = np.vstack([a_vecs, b_vecs])
        # Center
        mean = combined.mean(axis=0, keepdims=True)
        X = combined - mean
        # Covariance via SVD
        U, S, Vt = np.linalg.svd(X, full_matrices=False)
        components = Vt[:2].T  # d x 2
        proj = X @ components   # n x 2
        a_proj = proj[:len(a_vecs)]
        b_proj = proj[len(a_vecs):]

        def to_points(proj2d: np.ndarray, hits: List[Dict[str, Any]], mask_similar: np.ndarray) -> List[Dict[str, Any]]:
            pts: List[Dict[str, Any]] = []
            for (x, y), h, simf in zip(proj2d, hits, mask_similar):
                pts.append({
                    'x': float(x),
                    'y': float(y),
                    'label': 'similar' if bool(simf) else 'dissimilar',
                    'text': h['text'],
                    'link': h['link'],
                    'page': h['page']
                })
            return pts

        return {
            'bookA': {'key': a_key, 'points': to_points(a_proj, a_hits, a_similar)},
            'bookB': {'key': b_key, 'points': to_points(b_proj, b_hits, b_similar)},
            'threshold': threshold
        }

    def analyze_all_books_auto(self, k: int = 100, threshold: float = 0.6, unique_threshold: float = 0.35) -> Dict[str, Any]:
        """Automatically analyze all books using cross-book similarity for unique detection.
        
        Algorithm:
        1. For each point, calculate max similarity to points from OTHER books
        2. If max_cross_book_similarity < unique_threshold: UNIQUE to that book
        3. Else if avg_similarity >= median: SIMILAR (shared across books)
        4. Else: DISSIMILAR
        
        Args:
            k: Number of chunks per book
            threshold: Similarity threshold for similar pairs
            unique_threshold: Cross-book similarity threshold for uniqueness (default 0.35)
        """
        books = ['PMBOK', 'PRINCE2', 'ISO21500', 'ISO21502']
        all_hits: List[Dict[str, Any]] = []
        book_to_hits: Dict[str, List[Dict[str, Any]]] = {}
        
        # Get all chunks from all books
        for b in books:
            hits = self.query("", k=k, standard_filter=b)  # Empty query gets diverse results
            book_to_hits[b] = hits
            all_hits.extend(hits)

        if not all_hits:
            return {'points': [], 'threshold': threshold, 'unique_threshold': unique_threshold}

        # Encode all texts
        texts = [h['text'] for h in all_hits]
        vecs = self._encode_texts(texts)
        
        # Compute pairwise cosine similarity (vectors are already normalized)
        similarity_matrix = vecs @ vecs.T
        
        # Build index mapping: point_index -> book
        point_to_book: Dict[int, str] = {}
        idx = 0
        for book, hits in book_to_hits.items():
            for _ in hits:
                point_to_book[idx] = book
                idx += 1
        
        # Enhanced unique detection: check cross-book similarity
        book_unique_indices: Dict[str, set] = {b: set() for b in books}
        all_similarities = []
        cross_book_max_similarities = []
        
        for i, hit in enumerate(all_hits):
            current_book = point_to_book[i]
            
            # Calculate similarities to all other points
            similarities_to_all = []
            similarities_to_other_books = []
            
            for j, other_hit in enumerate(all_hits):
                if i != j:
                    sim = float(similarity_matrix[i, j])
                    similarities_to_all.append(sim)
                    
                    # Track cross-book similarities
                    other_book = point_to_book[j]
                    if current_book != other_book:
                        similarities_to_other_books.append(sim)
            
            # Average similarity to all points
            avg_similarity = np.mean(similarities_to_all) if similarities_to_all else 0
            all_similarities.append(avg_similarity)
            
            # Maximum similarity to OTHER books
            max_cross_book_sim = max(similarities_to_other_books) if similarities_to_other_books else 0
            cross_book_max_similarities.append(max_cross_book_sim)
            
            # Unique detection: low similarity to ALL other books
            if max_cross_book_sim < unique_threshold:
                book_unique_indices[current_book].add(i)
        
        # Find similar and dissimilar pairs
        similar_pairs = []
        dissimilar_pairs = []
        
        for i in range(len(all_hits)):
            for j in range(i+1, len(all_hits)):
                similarity = float(similarity_matrix[i, j])
                
                pair = {
                    'a': all_hits[i],
                    'b': all_hits[j],
                    'similarity': similarity
                }
                
                if similarity >= threshold:
                    similar_pairs.append(pair)
                else:
                    dissimilar_pairs.append(pair)

        # PCA to 2D for visualization
        mean = vecs.mean(axis=0, keepdims=True)
        X = vecs - mean
        U, S, Vt = np.linalg.svd(X, full_matrices=False)
        components = Vt[:2].T
        proj = X @ components

        # Sort similarities for median calculation
        sorted_similarities = sorted(all_similarities)
        n = len(sorted_similarities)
        median_similarity = sorted_similarities[n // 2] if n > 0 else 0.5
        
        # Create points for visualization with book-specific unique classification
        points: List[Dict[str, Any]] = []
        unique_indices_all = set()
        for indices in book_unique_indices.values():
            unique_indices_all.update(indices)
        
        for i, hit in enumerate(all_hits):
            x, y = float(proj[i, 0]), float(proj[i, 1])
            avg_similarity = all_similarities[i]
            cross_book_sim = cross_book_max_similarities[i]
            current_book = point_to_book[i]
            
            # Enhanced classification: UNIQUE -> SIMILAR -> DISSIMILAR
            if i in unique_indices_all:
                label = 'unique'
            elif avg_similarity >= median_similarity:
                label = 'similar'
            else:
                label = 'dissimilar'
            
            # Handle metadata for link generation
            standard = hit.get('standard', current_book)
            page = hit.get('page', 0)
            
            # Generate link
            standard_key = standard.upper()
            if 'PMBOK' in standard_key:
                pdf_endpoint = '/pdf/PMBOK'
            elif 'PRINCE' in standard_key:
                pdf_endpoint = '/pdf/PRINCE2'
            elif 'ISO21500' in standard_key:
                pdf_endpoint = '/pdf/ISO21500'
            elif 'ISO21502' in standard_key:
                pdf_endpoint = '/pdf/ISO21502'
            else:
                pdf_endpoint = ''
            link = f"{pdf_endpoint}#page={page}" if pdf_endpoint else None
            
            points.append({
                'x': x,
                'y': y,
                'label': label,
                'standard': standard,
                'text': hit['text'],
                'link': link,
                'page': page,
                'chunk_id': i,
                'avg_similarity': float(avg_similarity),
                'cross_book_similarity': float(cross_book_sim),
                'is_unique': i in unique_indices_all,
                'unique_to_book': current_book if i in unique_indices_all else None
            })

        # Calculate statistics per book
        book_stats = {}
        for book in books:
            book_points = [p for p in points if p['standard'].upper().replace(' ', '').replace('-', '') in book.replace('-', '')]
            unique_count = len([p for p in book_points if p['label'] == 'unique'])
            similar_count = len([p for p in book_points if p['label'] == 'similar'])
            dissimilar_count = len([p for p in book_points if p['label'] == 'dissimilar'])
            
            book_stats[book] = {
                'total': len(book_points),
                'unique': unique_count,
                'similar': similar_count,
                'dissimilar': dissimilar_count,
                'unique_percentage': (unique_count / len(book_points) * 100) if book_points else 0
            }

        return {
            'points': points,
            'similar_pairs': sorted(similar_pairs, key=lambda x: -x['similarity'])[:20],
            'dissimilar_pairs': sorted(dissimilar_pairs, key=lambda x: -x['similarity'])[:20],
            'unique_points': [p for p in points if p['label'] == 'unique'],
            'book_stats': book_stats,
            'threshold': threshold,
            'unique_threshold': unique_threshold,
            'algorithm': 'cross_book_similarity',
            'description': f'Unique: cross-book similarity < {unique_threshold}, Similar: avg >= median, Dissimilar: avg < median'
        }

    def get_all_snippets_for_standard(self, standard: str) -> List[Dict[str, Any]]:
        """Return all stored chunks/snippets for a given standard.

        Iterates over the stored metadata and filters items that belong to the
        requested standard. Sorting by page ensures a coherent reading order.
        """
        std_key = standard.upper()
        snippets: List[Dict[str, Any]] = []
        for meta_item in self.meta:
            if isinstance(meta_item, dict):
                item_standard = str(meta_item.get('standard', '')).upper()
                if std_key in item_standard:
                    snippets.append({
                        'standard': meta_item.get('standard'),
                        'text': meta_item.get('text', ''),
                        'page': meta_item.get('page', 0),
                    })
            else:
                # Old tuple format: (standard, text, page)
                item_standard, text, page = meta_item
                if std_key in str(item_standard).upper():
                    snippets.append({
                        'standard': item_standard,
                        'text': text,
                        'page': page,
                    })
        # Sort by page number for better coherence
        snippets.sort(key=lambda s: s.get('page', 0))
        return snippets

search_engine: SemanticSearch | None = None

def get_engine() -> SemanticSearch | LightSemanticSearch:
    global search_engine
    if search_engine is None:
        # Use light mode on Vercel (or when heavy deps are missing).
        is_vercel = bool(os.getenv("VERCEL")) or (os.getenv("DEPLOY_TARGET", "").lower() == "vercel")
        if is_vercel:
            return LightSemanticSearch()
        try:
            search_engine = SemanticSearch()
        except Exception:
            return LightSemanticSearch()
    return search_engine


