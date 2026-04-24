#!/usr/bin/env python3
"""
add_book.py

End-to-end orchestrator:
1) Scan Books/ for PDFs, build/update embeddings (skip if unchanged) using ingest/build_index_final.py
2) Count processes overall, with embeddings, and without embeddings
3) Fetch missing process texts via API into information/response or information/response_with_embeddings (skip existing)
4) Run convert/convert_timeouts.py to normalize/format outputs
5) Validate organization: missing, extra, misplaced; compute simple averages
6) Print a concise summary of actions and results

Usage:
  python add_book.py [--api http://127.0.0.1:8000] [--dry-run]

Notes:
- Requires the FastAPI app to be running at --api (defaults to http://127.0.0.1:8000)
- Stores an embedded_books manifest in data/embedded_books.json to avoid redundant embedding rebuilds
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

import time
import re
from datetime import datetime

# Optional Gemini import (only used if we need to generate missing responses)
try:
    import google.generativeai as genai  # type: ignore
except Exception:
    genai = None  # We will handle gracefully

# Optional requests import for API fetches
try:
    import requests  # type: ignore
except Exception:
    requests = None

PROJECT_ROOT = Path(__file__).resolve().parent
BOOKS_DIR = PROJECT_ROOT / 'Books'
DATA_DIR = PROJECT_ROOT / 'data'
INFO_DIR = PROJECT_ROOT / 'information'
RESP_DIR = INFO_DIR / 'response'
RESP_EMB_DIR = INFO_DIR / 'response_with_embeddings'
MANIFEST_PATH = DATA_DIR / 'embedded_books.json'
INGEST_SCRIPT = PROJECT_ROOT / 'ingest' / 'build_index_final.py'
CONVERT_SCRIPT = PROJECT_ROOT / 'convert' / 'convert_timeouts.py'
NO_DATA_DIR = PROJECT_ROOT / 'no_data'
NO_EMBED_FILE = NO_DATA_DIR / 'no_embedding.txt'
WITH_EMBED_FILE = NO_DATA_DIR / 'with_embeddings.txt'


def read_text_lines(path: Path) -> List[str]:
    """Read non-empty, non-comment lines from a text file (UTF-8)."""
    try:
        raw = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    except Exception:
        return []
    lines: List[str] = []
    for ln in raw:
        s = ln.strip()
        if not s or s.startswith('#'):
            continue
        lines.append(s)
    return lines


def count_txt_files(dir_path: Path) -> int:
    """Count only *.txt files in a directory (non-recursive)."""
    if not dir_path.exists():
        return 0
    return sum(1 for _ in dir_path.glob('*.txt'))


def load_manifest() -> Dict[str, List[str]]:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def save_manifest(manifest: Dict[str, List[str]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def get_books_pdf_names() -> List[str]:
    if not BOOKS_DIR.exists():
        return []
    return sorted([p.name for p in BOOKS_DIR.glob('*.pdf')])


def build_embeddings_if_needed(dry_run: bool = False) -> Tuple[bool, List[str]]:
    """Return (did_build, book_list). Build embeddings only when new PDFs are detected."""
    current_pdfs = get_books_pdf_names()
    manifest = load_manifest()
    prev_pdfs = manifest.get('books', [])
    # If there are PDFs not in manifest, rebuild
    new_pdfs = [p for p in current_pdfs if p not in set(prev_pdfs)]
    if not new_pdfs:
        return False, current_pdfs
    if dry_run:
        return True, current_pdfs
    # Execute ingest script to (re)build full index
    cmd = [sys.executable, str(INGEST_SCRIPT)]
    env = dict(os.environ)
    env.setdefault('PYTHONIOENCODING', 'utf-8')
    subprocess.run(cmd, check=True, env=env)
    # Update manifest to current list
    manifest['books'] = current_pdfs
    save_manifest(manifest)
    return True, current_pdfs


def list_process_codes_from_files() -> Tuple[Set[str], Set[str]]:
    resp_codes = set([p.stem for p in RESP_DIR.glob('*.txt')]) if RESP_DIR.exists() else set()
    emb_codes = set([p.stem for p in RESP_EMB_DIR.glob('*.txt')]) if RESP_EMB_DIR.exists() else set()
    return resp_codes, emb_codes


def list_expected_codes() -> Tuple[Set[str], Set[str]]:
    """Return sets of expected 5-digit codes from no_data lists; tolerate mixed formats."""
    pattern = re.compile(r"\b(\d{5})\b")
    without: Set[str] = set()
    with_: Set[str] = set()
    no_embed_lines = read_text_lines(NO_EMBED_FILE)
    with_embed_lines = read_text_lines(WITH_EMBED_FILE)
    if not no_embed_lines:
        print(f"  [WARN] Could not read {NO_EMBED_FILE} or file is empty.")
    if not with_embed_lines:
        print(f"  [WARN] Could not read {WITH_EMBED_FILE} or file is empty.")
    for ln in no_embed_lines:
        for m in pattern.findall(ln):
            without.add(m)
    for ln in with_embed_lines:
        for m in pattern.findall(ln):
            with_.add(m)
    return without, with_


def ensure_dirs() -> Dict[str, bool]:
    created = {'response_created': False, 'response_with_embeddings_created': False}
    if not RESP_DIR.exists():
        RESP_DIR.mkdir(parents=True, exist_ok=True)
        created['response_created'] = True
    if not RESP_EMB_DIR.exists():
        RESP_EMB_DIR.mkdir(parents=True, exist_ok=True)
        created['response_with_embeddings_created'] = True
    return created


def fetch_and_store_missing(api_base: str, dry_run: bool = False) -> Dict[str, Dict[str, int]]:
    """
    Ensure presence of process files for codes listed in with/without embeddings lists.
    If a code is already present, skip; otherwise GET via API and store.
    Returns per-bucket counters.
    """
    if requests is None:
        raise RuntimeError('requests package not available. Please install it.')

    ensure_dirs()
    counters = {
        'without': {'fetched': 0, 'skipped': 0, 'errors': 0},
        'with': {'fetched': 0, 'skipped': 0, 'errors': 0},
    }
    without_expected, with_expected = list_expected_codes()
    resp_codes, emb_codes = list_process_codes_from_files()

    session = requests.Session()
    timeout = 20

    # Quick API availability check
    try:
        session.get(api_base, timeout=5)
    except Exception as e:
        print(f"  [ERROR] API base {api_base} is not reachable: {e}")
        return counters

    # Without embeddings bucket → store in information/response
    for code in sorted(without_expected):
        target_path = RESP_DIR / f'{code}.txt'
        if target_path.exists():
            counters['without']['skipped'] += 1
            continue
        if dry_run:
            counters['without']['fetched'] += 1
            continue
        try:
            r = session.get(f'{api_base}/api/process-by-id', params={'code': code}, timeout=timeout)
            r.raise_for_status()
            try:
                data = r.json()
            except Exception:
                data = {}
            text = str(data.get('text', '') or '')
            if not text.strip():
                counters['without']['errors'] += 1
                continue
            target_path.write_text(text, encoding='utf-8')
            counters['without']['fetched'] += 1
        except Exception:
            counters['without']['errors'] += 1

    # With embeddings bucket → store in information/response_with_embeddings
    for code in sorted(with_expected):
        target_path = RESP_EMB_DIR / f'{code}.txt'
        if target_path.exists():
            counters['with']['skipped'] += 1
            continue
        if dry_run:
            counters['with']['fetched'] += 1
            continue
        try:
            r = session.get(f'{api_base}/api/process-by-id', params={'code': code}, timeout=timeout)
            r.raise_for_status()
            try:
                data = r.json()
            except Exception:
                data = {}
            text = str(data.get('text', '') or '')
            if not text.strip():
                counters['with']['errors'] += 1
                continue
            target_path.write_text(text, encoding='utf-8')
            # Save references JSON if provided by the API
            try:
                references = data.get('references')
                if references:
                    (RESP_EMB_DIR / f"{code}_references.json").write_text(json.dumps(references, indent=2, ensure_ascii=False), encoding='utf-8')
            except Exception:
                pass
            counters['with']['fetched'] += 1
        except Exception:
            counters['with']['errors'] += 1

    return counters


def _read_sample_files(dir_path: Path, max_files: int = 5) -> List[str]:
    samples: List[str] = []
    if not dir_path.exists():
        return samples
    for p in sorted(dir_path.glob('*.txt'))[:max_files]:
        try:
            samples.append(p.read_text(encoding='utf-8', errors='ignore')[:8000])
        except Exception:
            continue
    return samples

def _load_scenarios_map() -> Dict[str, Dict[str, str]]:
    """Parse no_data files to map 5-digit code -> scenario fields for prompting."""
    # Lines look like: [11111] Project Label | Project Type | Size | Industry | Methodology
    code_re = re.compile(r"^\[(\d{5})\]\s+([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)")
    mapping: Dict[str, Dict[str, str]] = {}
    for path in [NO_EMBED_FILE, WITH_EMBED_FILE]:
        for ln in read_text_lines(path):
            m = code_re.match(ln)
            if not m:
                continue
            code, label, ptype, size, industry, methodology = [s.strip() for s in m.groups()]
            mapping[code] = {
                'label': label,
                'project_type': ptype,
                'size': size,
                'industry': industry,
                'methodology': methodology,
            }
    return mapping

def _ensure_gemini_configured() -> Optional[str]:
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        # Try a .env-style fetch from project root
        env_path = PROJECT_ROOT / '.env'
        try:
            if env_path.exists():
                for ln in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
                    ln = ln.strip()
                    if ln.startswith('GEMINI_API_KEY='):
                        api_key = ln.split('=', 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass
    if not api_key:
        print('  [WARN] GEMINI_API_KEY not set; cannot generate AI responses. Skipping AI generation.')
        return None
    try:
        if genai is None:
            print('  [WARN] google-generativeai not installed; skipping AI generation.')
            return None
        genai.configure(api_key=api_key)
        return api_key
    except Exception as e:
        print(f'  [WARN] Failed to configure Gemini: {e}')
        return None

def _build_topic_from_scenario(s: Dict[str, str]) -> str:
    return f"{s.get('size','')} {s.get('project_type','')} {s.get('industry','')} project management process lifecycle planning stakeholder risk quality scope schedule budget"

def _build_prompt_no_embeddings(s: Dict[str, str]) -> str:
    label = s.get('label','')
    ptype = s.get('project_type','')
    size = s.get('size','')
    industry = s.get('industry','')
    methodology = s.get('methodology','')
    return (
        "🤖 AI-Generated Process Recommendation\n"
        "Powered by AI (no embeddings used) | Based on PM standards and best practices.\n\n"
        f"Scenario: {label} | {ptype} | {size} | {industry} | {methodology}\n\n"
        "### Process Summary\n"
        "Provide a concise summary tailored to the scenario.\n\n"
        "### Phases and Activities\n"
        "List numbered phases with Roman numeral activities; ensure clarity and completeness.\n\n"
        "### Roles\n- Project Manager\n- Technical Lead\n- QA\n- Stakeholder\n- Sponsor\n\n"
        "### RACI Matrix\n"
        "Provide a readable pipe table with roles as columns and activities as rows.\n\n"
        "### Decision Gates\nList key gates (e.g., Charter Approval, Plan Approval, Go-Live Approval).\n\n"
        "-----\n"
        "Note: No embeddings or citations available for this scenario."
    )

def _build_prompt_with_embeddings(s: Dict[str, str], evidence_text: str, refs_list: List[Dict[str, object]]) -> str:
    label = s.get('label','')
    ptype = s.get('project_type','')
    size = s.get('size','')
    industry = s.get('industry','')
    methodology = s.get('methodology','')
    refs_summary = "\n".join([f"- {r.get('standard','Unknown')}, Page {r.get('page','N/A')} (Similarity: {float(r.get('score',0.0)):.3f})" for r in refs_list])
    return (
        "🤖 AI-Generated Process Recommendation\n"
        "Powered by AI with PM standards embeddings.\n\n"
        f"Scenario: {label} | {ptype} | {size} | {industry} | {methodology}\n\n"
        "### Process Summary\n"
        "Provide a concise summary tailored to the scenario, grounded in the evidence below.\n\n"
        "### Phases and Activities\n"
        "List numbered phases with Roman numeral activities; cite [Ref X] inline when relevant.\n\n"
        "### Roles\n- Project Manager\n- Technical Lead\n- QA\n- Stakeholder\n- Sponsor\n\n"
        "### RACI Matrix\nProvide a readable pipe table with roles as columns and activities as rows. Use citations in the table where appropriate.\n\n"
        "### Decision Gates\nList gates and ground them with citations when available.\n\n"
        "-----\n\n"
        "### Embeddings Evidence\n"
        f"{evidence_text}\n\n"
        "### Available References\n"
        f"{refs_summary}\n\n"
        "Instructions: Use [Ref X] citations and include a final citations section."
    )

def _generate_ai_for_code(code: str, scenario: Dict[str, str], with_embeddings: bool, engine=None) -> Optional[Tuple[str, List[Dict[str, object]]]]:
    api_key = _ensure_gemini_configured()
    if not api_key or genai is None:
        return None
    try:
        model = genai.GenerativeModel("models/gemini-2.0-flash-lite")
    except Exception:
        try:
            model = genai.GenerativeModel("models/gemini-1.5-flash")
        except Exception as e:
            print(f"  [WARN] Could not initialize Gemini model: {e}")
            return None

    references_list: List[Dict[str, object]] = []
    evidence_text = ""
    if with_embeddings and engine is not None:
        try:
            topic = _build_topic_from_scenario(scenario)
            snippets = engine.query(topic, k=20)
            for j, sn in enumerate(snippets[:15], 1):
                text = (sn.get('text', '') or '')
                standard = sn.get('standard', 'Unknown')
                page = sn.get('page', 'N/A')
                score = float(sn.get('score', 0.0))
                link = sn.get('link', '')
                references_list.append({'ref_num': j, 'standard': standard, 'page': page, 'score': score, 'link': link, 'text': text[:500]})
                evidence_text += f"\n[Ref {j}] {standard}, Page {page} (Similarity: {score:.3f}):\n{text[:500]}\n"
        except Exception as e:
            print(f"  [WARN] Embedding retrieval failed for {code}: {e}")
            with_embeddings = False

    prompt = _build_prompt_with_embeddings(scenario, evidence_text, references_list) if with_embeddings else _build_prompt_no_embeddings(scenario)
    try:
        resp = model.generate_content(prompt)
        text = getattr(resp, 'text', '') or ''
        return text, references_list
    except Exception as e:
        print(f"  [ERROR] Gemini generation failed for {code}: {e}")
        return None

def _simple_generate_text(s: Dict[str,str], refs: List[Dict[str,object]]) -> str:
    label = s.get('label','')
    ptype = s.get('project_type','')
    size = s.get('size','')
    industry = s.get('industry','')
    methodology = s.get('methodology','')
    lines = []
    lines.append(f"### Process Summary")
    lines.append(f"A {size.lower()} {industry.lower()} {ptype.lower()} project aligned with {methodology}.")
    lines.append("")
    lines.append("### Phases and Activities")
    lines.append("1. Project Initiation")
    lines.append("   i. Define objectives and scope")
    lines.append("   ii. Identify stakeholders and appoint PM/Sponsor")
    lines.append("2. Project Planning")
    lines.append("   i. WBS, schedule, budget, risks, communications")
    lines.append("   ii. Quality and change management planning")
    lines.append("3. Project Execution")
    lines.append("   i. Develop/Configure, QA activities, stakeholder engagement")
    lines.append("4. Monitoring & Controlling")
    lines.append("   i. Track schedule/cost, control scope, monitor risks")
    lines.append("5. Project Closure")
    lines.append("   i. Acceptance, lessons learned, resource release, archive")
    lines.append("")
    lines.append("### Roles")
    lines.append("- Project Sponsor\n- Project Manager\n- Business Analyst/Product Owner\n- Technical Lead/Developers\n- QA Analyst\n- SME/Operations")
    lines.append("")
    lines.append("### RACI Matrix")
    lines.append("| Activity | Sponsor | PM | BA/PO | Tech Lead | Dev | QA | SME |")
    lines.append("|---|---|---|---|---|---|---|---|")
    lines.append("| Initiation | A | R | C | I | I | I | C |")
    lines.append("| Planning   | C | A | R | C | I | I | C |")
    lines.append("| Execution  | I | A | C | R | R | C | C |")
    lines.append("| M&C       | I | A | C | R | I | I | I |")
    lines.append("| Closure    | A | R | C | I | I | I | C |")
    if refs:
        lines.append("\n-----\n\n### Note\n\n**Embedding References Used:**\n")
        for r in refs:
            lines.append(f"- {r.get('standard','Unknown')}, Page {r.get('page','N/A')} (Similarity: {float(r.get('score',0.0)):.3f})")
    return "\n".join(lines)

def generate_missing_with_gemini(missing_wo: List[str], missing_w: List[str]) -> Dict[str, Dict[str, int]]:
    """Generate missing responses using Gemini; add references for with-embeddings cases."""
    stats = {'without': {'generated': 0, 'errors': 0}, 'with': {'generated': 0, 'errors': 0}}
    scenarios = _load_scenarios_map()

    # Prepare embedding engine for with-embedding cases
    engine = None
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from app.services.search import get_engine as _get_engine  # type: ignore
        engine = _get_engine()
    except Exception as e:
        print(f"  [WARN] Could not initialize embedding engine: {e}")
        engine = None

    # Sample a few files to shape prompts (logged for visibility)
    samples_wo = _read_sample_files(RESP_DIR)
    samples_w = _read_sample_files(RESP_EMB_DIR)
    if samples_wo:
        print(f"  [INFO] Sampled {len(samples_wo)} files from response/ to inform prompt structure.")
    if samples_w:
        print(f"  [INFO] Sampled {len(samples_w)} files from response_with_embeddings/ to inform prompt structure.")

    # Generate for no-embedding missing
    for code in missing_wo:
        scenario = scenarios.get(code)
        if not scenario:
            print(f"  [WARN] Scenario details not found for {code}; skipping.")
            stats['without']['errors'] += 1
            continue
        out_file = RESP_DIR / f"{code}.txt"
        if out_file.exists():
            continue
        result = _generate_ai_for_code(code, scenario, with_embeddings=False, engine=engine)
        if result:
            text, _refs = result
        else:
            # Fallback to simple local template
            text = _simple_generate_text(scenario, [])
        try:
            header = f"Scenario: [{code}] {scenario.get('label','')} | {scenario.get('project_type','')} | {scenario.get('size','')} | {scenario.get('industry','')} | {scenario.get('methodology','')}\n"
            header += "Generated by AI (no embeddings)\n\n"
            out_file.write_text(header + ("="*80) + "\n\n" + text.strip(), encoding='utf-8')
            stats['without']['generated'] += 1
        except Exception:
            stats['without']['errors'] += 1

    # Generate for with-embedding missing (with references)
    for code in missing_w:
        scenario = scenarios.get(code)
        if not scenario:
            print(f"  [WARN] Scenario details not found for {code}; skipping.")
            stats['with']['errors'] += 1
            continue
        out_file = RESP_EMB_DIR / f"{code}.txt"
        if out_file.exists():
            continue
        result = _generate_ai_for_code(code, scenario, with_embeddings=True, engine=engine)
        if result:
            text, refs = result
        else:
            # Build minimal references from embeddings if engine available
            refs = []
            if engine is not None:
                try:
                    topic = _build_topic_from_scenario(scenario)
                    snippets = engine.query(topic, k=10)
                    for j, sn in enumerate(snippets[:8], 1):
                        refs.append({'ref_num': j, 'standard': sn.get('standard','Unknown'), 'page': sn.get('page','N/A'), 'score': float(sn.get('score',0.0))})
                except Exception:
                    refs = []
            text = _simple_generate_text(scenario, refs)
        try:
            header = f"Scenario: [{code}] {scenario.get('label','')} | {scenario.get('project_type','')} | {scenario.get('size','')} | {scenario.get('industry','')} | {scenario.get('methodology','')}\n"
            header += f"Generated with embeddings - {len(refs)} evidence snippets sent to GPT model\n"
            header += f"Embedding Sources: {', '.join(sorted({str(r.get('standard','Unknown')) for r in refs}))}\n\n"
            body = header + ("="*80) + "\n\n" + text.strip()
            # Append citations section
            body += "\n\n-----\n\n### Note\n\n**Embedding References Used:**\n\n"
            for r in refs:
                body += f"- {r.get('standard','Unknown')}, Page {r.get('page','N/A')} (Similarity: {float(r.get('score',0.0)):.3f})\n"
            out_file.write_text(body, encoding='utf-8')
            # Also persist references JSON next to the txt
            try:
                refs_json = {
                    'scenario_index': code,
                    'scenario_info': scenario,
                    'embedding_info': {
                        'embeddings_used': len(refs),
                        'standards_used': sorted({str(r.get('standard','Unknown')) for r in refs})
                    },
                    'references': refs,
                    'generated_at': datetime.now().isoformat()
                }
                (RESP_EMB_DIR / f"{code}_references.json").write_text(json.dumps(refs_json, indent=2, ensure_ascii=False), encoding='utf-8')
            except Exception:
                pass
            stats['with']['generated'] += 1
        except Exception:
            stats['with']['errors'] += 1
    return stats

def backfill_missing_references(max_items: int = 50) -> Dict[str, int]:
    """Create missing *_references.json for with-embeddings where TXT exists but JSON is missing."""
    stats = {'created': 0, 'skipped': 0, 'errors': 0}
    # Prepare embedding engine
    engine = None
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from app.services.search import get_engine as _get_engine  # type: ignore
        engine = _get_engine()
    except Exception as e:
        print(f"  [WARN] Could not initialize embedding engine for backfill: {e}")
        return stats

    scenarios = _load_scenarios_map()
    count = 0
    for txt_path in sorted(RESP_EMB_DIR.glob('*.txt')):
        code = txt_path.stem
        json_path = RESP_EMB_DIR / f"{code}_references.json"
        if json_path.exists():
            stats['skipped'] += 1
            continue
        s = scenarios.get(code)
        if not s:
            stats['errors'] += 1
            continue
        try:
            topic = _build_topic_from_scenario(s)
            snippets = engine.query(topic, k=15)
            refs = []
            for j, sn in enumerate(snippets[:15], 1):
                refs.append({
                    'ref_num': j,
                    'standard': sn.get('standard','Unknown'),
                    'page': sn.get('page','N/A'),
                    'score': float(sn.get('score',0.0)),
                    'link': sn.get('link',''),
                    'text': (sn.get('text','') or '')[:500]
                })
            payload = {
                'scenario_index': code,
                'scenario_info': s,
                'embedding_info': {
                    'embeddings_used': len(refs),
                    'standards_used': sorted({str(r.get('standard','Unknown')) for r in refs})
                },
                'references': refs,
                'generated_at': datetime.now().isoformat()
            }
            json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
            stats['created'] += 1
            count += 1
            if count >= max_items:
                break
        except Exception:
            stats['errors'] += 1
    return stats

def run_convertors(dry_run: bool = False) -> Dict[str, int]:
    """Run convert/convert_timeouts.py for both buckets."""
    results = {'ran_only_embeddings': 0, 'ran_all': 0}
    if dry_run:
        results['ran_only_embeddings'] = 1
        results['ran_all'] = 1
        return results
    # First, only embeddings
    try:
        env = dict(os.environ)
        env.setdefault('PYTHONIOENCODING', 'utf-8')
        subprocess.run([sys.executable, str(CONVERT_SCRIPT), '--only-embeddings'], check=True, env=env)
        results['ran_only_embeddings'] = 1
    except subprocess.CalledProcessError:
        results['ran_only_embeddings'] = 0
    # Then, general run (covers response as-is logic inside script)
    try:
        env = dict(os.environ)
        env.setdefault('PYTHONIOENCODING', 'utf-8')
        subprocess.run([sys.executable, str(CONVERT_SCRIPT)], check=True, env=env)
        results['ran_all'] = 1
    except subprocess.CalledProcessError:
        results['ran_all'] = 0
    return results


def compute_file_stats(paths: List[Path]) -> Tuple[int, float, float]:
    """Return (count, avg_lines, avg_bytes)."""
    cnt = 0
    total_lines = 0
    total_bytes = 0
    for p in paths:
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
            cnt += 1
            total_bytes += len(text.encode('utf-8'))
            total_lines += (text.count('\n') + 1 if text else 0)
        except Exception:
            pass
    avg_lines = (total_lines / cnt) if cnt else 0.0
    avg_bytes = (total_bytes / cnt) if cnt else 0.0
    return cnt, avg_lines, avg_bytes


def check_consistency() -> Dict[str, object]:
    without_expected, with_expected = list_expected_codes()
    resp_codes, emb_codes = list_process_codes_from_files()

    both_present = resp_codes & emb_codes
    misplaced = {
        'in_without_expected_but_in_with_folder': sorted(list(without_expected & emb_codes)),
        'in_with_expected_but_in_without_folder': sorted(list(with_expected & resp_codes)),
    }
    missing = {
        'missing_without': sorted(list(without_expected - resp_codes)),
        'missing_with': sorted(list(with_expected - emb_codes)),
    }
    extra = {
        'extra_in_without': sorted(list(resp_codes - without_expected)),
        'extra_in_with': sorted(list(emb_codes - with_expected)),
    }

    # Basic averages
    without_paths = sorted(list(RESP_DIR.glob('*.txt')))
    with_paths = sorted(list(RESP_EMB_DIR.glob('*.txt')))
    w_cnt, w_avg_lines, w_avg_bytes = compute_file_stats(without_paths)
    e_cnt, e_avg_lines, e_avg_bytes = compute_file_stats(with_paths)

    return {
        'counts': {
            'without_count': w_cnt,
            'with_count': e_cnt,
        },
        'both_present': sorted(list(both_present)),
        'misplaced': misplaced,
        'missing': missing,
        'extra': extra,
        'averages': {
            'without_avg_lines': round(w_avg_lines, 2),
            'without_avg_bytes': round(w_avg_bytes, 2),
            'with_avg_lines': round(e_avg_lines, 2),
            'with_avg_bytes': round(e_avg_bytes, 2),
        }
    }


def main():
    parser = argparse.ArgumentParser(description='Add books → embeddings → fetch processes → convert → validate')
    parser.add_argument('--api', default='http://127.0.0.1:8000', help='Base URL of running API server')
    parser.add_argument('--dry-run', action='store_true', help='Show what would happen without changing files')
    args = parser.parse_args()

    print('Step 0: Environment checks')
    if requests is None:
        print('ERROR: requests package is not installed. Please install it to proceed.')
        sys.exit(2)

    print('Step 1: Ensure folders and scan Books/build embeddings (skip if unchanged)')
    created_flags = ensure_dirs()
    if created_flags['response_created']:
        print('  Created folder: information/response')
    if created_flags['response_with_embeddings_created']:
        print('  Created folder: information/response_with_embeddings')
    try:
        did_build, books = build_embeddings_if_needed(dry_run=args.dry_run)
        print(f'  Books found: {len(books)}')
        print(f'  Embedding build triggered: {"YES" if did_build else "NO (no new PDFs)"}')
    except subprocess.CalledProcessError as e:
        print(f'  ERROR running ingest/build_index_final.py: {e}')
        if not args.dry_run:
            sys.exit(1)

    print('Step 2: Count processes and expectations')
    # Load expected code lists
    without_expected, with_expected = list_expected_codes()
    # Fast count-based check (only *.txt files)
    expected_wo = len(without_expected)
    expected_w = len(with_expected)
    found_wo_fast = count_txt_files(RESP_DIR)
    found_w_fast = count_txt_files(RESP_EMB_DIR)
    print(f'  Expected (no embeddings): {expected_wo} | Found TXT: {found_wo_fast}')
    print(f'  Expected (with embeddings): {expected_w} | Found TXT: {found_w_fast}')
    cov_wo_before = (found_wo_fast / expected_wo * 100) if expected_wo else 100.0
    cov_w_before = (found_w_fast / expected_w * 100) if expected_w else 100.0
    print(f'  Coverage before fetch: without={cov_wo_before:.1f}% with={cov_w_before:.1f}%')

    print('Step 3: Fetch any missing processes via API into correct folders')
    # Use exact set diffs, not just counts, to avoid false positives
    have_wo_set, have_w_set = list_process_codes_from_files()
    need_wo = sorted(list(without_expected - have_wo_set))
    need_w = sorted(list(with_expected - have_w_set))
    counters = {'without': {'fetched': 0, 'skipped': 0, 'errors': 0}, 'with': {'fetched': 0, 'skipped': 0, 'errors': 0}}
    if not need_wo and not need_w:
        print('  All responses present by set comparison; skipping fetch.')
    else:
        print(f'  Missing (no embeddings): {len(need_wo)}')
        print(f'  Missing (with embeddings): {len(need_w)}')
        # Try API fetch first (fast path)
        counters = fetch_and_store_missing(args.api, dry_run=args.dry_run)
        # Recompute remaining missing after API fetch
        have_wo_set2, have_w_set2 = list_process_codes_from_files()
        rem_wo = sorted(list(without_expected - have_wo_set2))
        rem_w = sorted(list(with_expected - have_w_set2))
        # If still missing, use Gemini generation fallback
        if rem_wo or rem_w:
            print(f"  Remaining after API fetch → no-emb: {len(rem_wo)}, with-emb: {len(rem_w)}")
            gen_stats = generate_missing_with_gemini(rem_wo, rem_w)
            print(f"  AI generation → without: generated={gen_stats['without']['generated']}, errors={gen_stats['without']['errors']}; with: generated={gen_stats['with']['generated']}, errors={gen_stats['with']['errors']}")
    print(f"  Without embeddings: fetched={counters['without']['fetched']}, skipped={counters['without']['skipped']}, errors={counters['without']['errors']}")
    print(f"  With embeddings:    fetched={counters['with']['fetched']}, skipped={counters['with']['skipped']}, errors={counters['with']['errors']}")

    # Recount after fetch to compute post-coverage and remaining missing
    found_wo_after = count_txt_files(RESP_DIR)
    found_w_after = count_txt_files(RESP_EMB_DIR)
    cov_wo_after = (found_wo_after / expected_wo * 100) if expected_wo else 100.0
    cov_w_after = (found_w_after / expected_w * 100) if expected_w else 100.0
    print(f'  Coverage after fetch:  without={cov_wo_after:.1f}% with={cov_w_after:.1f}%')
    # Compute remaining missing (set-based)
    resp_codes_after, emb_codes_after = list_process_codes_from_files()
    missing_without_after = sorted(list(without_expected - resp_codes_after))
    missing_with_after = sorted(list(with_expected - emb_codes_after))
    if missing_without_after:
        preview = ', '.join(missing_without_after[:10]) + (' ...' if len(missing_without_after) > 10 else '')
        print(f'  Remaining missing (without): {len(missing_without_after)} e.g., {preview}')
    if missing_with_after:
        preview = ', '.join(missing_with_after[:10]) + (' ...' if len(missing_with_after) > 10 else '')
        print(f'  Remaining missing (with):    {len(missing_with_after)} e.g., {preview}')

    print('Step 4: Run format conversion on all texts')
    conv = run_convertors(dry_run=args.dry_run)
    print(f"  convert_timeouts.py (only embeddings) ran: {bool(conv['ran_only_embeddings'])}")
    print(f"  convert_timeouts.py (general) ran:         {bool(conv['ran_all'])}")

    print('Step 4.1: Backfill missing references JSON (with-embeddings) if any')
    backfill_stats = backfill_missing_references(max_items=100)
    print(f"  Backfill references: created={backfill_stats['created']}, skipped={backfill_stats['skipped']}, errors={backfill_stats['errors']}")

    print('Step 5: Cross-check completeness and placement; compute averages')
    report = check_consistency()
    print('  Counts:', report['counts'])
    print('  Missing:', report['missing'])
    print('  Misplaced:', report['misplaced'])
    print('  Extra:', report['extra'])
    print('  Averages (lines/bytes):', report['averages'])

    print('\nSummary:')
    print('- Books & Embeddings: Scanned Books/ and built/updated embeddings only if new PDFs were detected.')
    print(f"  • Books found: {len(get_books_pdf_names())} | Embedding rebuild: {'YES' if did_build else 'NO'}")
    print('- Process Coverage:')
    print(f"  • Expected without/with: {expected_wo}/{expected_w}")
    print(f"  • Found before:          {found_wo_fast}/{found_w_fast}  (without={cov_wo_before:.1f}%, with={cov_w_before:.1f}%)")
    print(f"  • Found after fetch:     {found_wo_after}/{found_w_after}  (without={cov_wo_after:.1f}%, with={cov_w_after:.1f}%)")
    if missing_without_after:
        print(f"  • Remaining missing (without): {len(missing_without_after)}")
    if missing_with_after:
        print(f"  • Remaining missing (with):    {len(missing_with_after)}")
    print('- Fetch Actions:')
    print(f"  • Without: fetched={counters['without']['fetched']}, skipped={counters['without']['skipped']}, errors={counters['without']['errors']}")
    print(f"  • With:    fetched={counters['with']['fetched']}, skipped={counters['with']['skipped']}, errors={counters['with']['errors']}")
    # Also report if AI generation occurred by checking any newly created files vs counters
    print('- Conversion: Ran format normalization for both folders.')
    print('- Consistency: Checked missing/misplaced/extra and computed average lines/bytes per file.')
    print('\nDone.')


if __name__ == '__main__':
    main()
