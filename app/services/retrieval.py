import time
from typing import List, Dict, Any
import requests

_cache: Dict[str, Dict[str, Any]] = {}
_TTL = 300.0  # seconds


def _get_cached(key: str):
    ent = _cache.get(key)
    if ent and (time.time() - ent['t'] < _TTL):
        return ent['v']
    return None


def _set_cached(key: str, value: Any):
    _cache[key] = {'t': time.time(), 'v': value}


def fetch_wikipedia(topic: str, limit: int = 3) -> List[Dict[str, Any]]:
    key = f"wiki::{topic}::{limit}"
    hit = _get_cached(key)
    if hit is not None:
        return hit
    try:
        params = {
            'action': 'query',
            'list': 'search',
            'srsearch': topic,
            'format': 'json',
        }
        r = requests.get('https://en.wikipedia.org/w/api.php', params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        out: List[Dict[str, Any]] = []
        for item in (data.get('query', {}).get('search', [])[:limit]):
            title = item.get('title')
            snippet = item.get('snippet', '').replace('<span class="searchmatch">', '').replace('</span>', '')
            url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            out.append({'source': 'Wikipedia', 'title': title, 'url': url, 'snippet': snippet})
        _set_cached(key, out)
        return out
    except Exception:
        return []


def fetch_openalex(topic: str, limit: int = 3) -> List[Dict[str, Any]]:
    key = f"openalex::{topic}::{limit}"
    hit = _get_cached(key)
    if hit is not None:
        return hit
    try:
        params = {
            'search': topic,
            'per_page': limit,
        }
        r = requests.get('https://api.openalex.org/works', params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        out: List[Dict[str, Any]] = []
        for w in data.get('results', [])[:limit]:
            title = w.get('title')
            url = w.get('id')
            abstract = (w.get('abstract_inverted_index') or {})
            # Reconstruct a short snippet if possible
            words = []
            for token, positions in abstract.items():
                # simple collect first 20 tokens
                words.append(token)
                if len(words) > 20:
                    break
            snippet = ' '.join(words)
            out.append({'source': 'OpenAlex', 'title': title, 'url': url, 'snippet': snippet})
        _set_cached(key, out)
        return out
    except Exception:
        return []


def fetch_arxiv(topic: str, limit: int = 2) -> List[Dict[str, Any]]:
    key = f"arxiv::{topic}::{limit}"
    hit = _get_cached(key)
    if hit is not None:
        return hit
    try:
        params = {
            'search_query': f"all:{topic}",
            'start': 0,
            'max_results': limit,
        }
        r = requests.get('http://export.arxiv.org/api/query', params=params, timeout=10)
        r.raise_for_status()
        text = r.text
        # Very light parse to extract titles/links
        out: List[Dict[str, Any]] = []
        for chunk in text.split('<entry>')[1:limit+1]:
            try:
                t0 = chunk.split('<title>')[1].split('</title>')[0].strip()
                l0 = chunk.split('<id>')[1].split('</id>')[0].strip()
                s0 = chunk.split('<summary>')[1].split('</summary>')[0].strip()
                out.append({'source': 'arXiv', 'title': t0, 'url': l0, 'snippet': s0[:240]})
            except Exception:
                continue
        _set_cached(key, out)
        return out
    except Exception:
        return []


def retrieve_external_context(topic: str, limit_total: int = 6) -> List[Dict[str, Any]]:
    items = []
    items.extend(fetch_wikipedia(topic, limit=3))
    if len(items) < limit_total:
        items.extend(fetch_openalex(topic, limit=limit_total - len(items)))
    if len(items) < limit_total:
        items.extend(fetch_arxiv(topic, limit=limit_total - len(items)))
    return items[:limit_total]


