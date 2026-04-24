import io
from fastapi import APIRouter, Query, Response
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Dict, Optional, Any, List
from pathlib import Path
import subprocess, sys
import shlex
from ..services.search import get_engine
from ..services.summary import summarize_book_from_snippets
from ..services.local_ai import generate_process_recommendation, generate_summary, generate_answer_from_context
from ..services.retrieval import retrieve_external_context
from ..services.pdf_generator import generate_process_pdf
import os

router = APIRouter(prefix="/api")
@router.post('/answer-from-citations')
def answer_from_citations(payload: Dict[str, Any]):
    """Generate an answer strictly from provided citations.
    Expected payload: { question: str, citations: [{standard,page,excerpt}] }
    """
    question = str(payload.get('question') or '').strip()
    citations = payload.get('citations') or []
    if not question:
        return { 'answer': '', 'error': 'question is required' }
    if not isinstance(citations, list) or not citations:
        return { 'answer': '', 'error': 'citations array is required' }
    try:
        answer = generate_answer_from_context(question, citations)
        return { 'answer': answer }
    except Exception as e:
        return { 'answer': '', 'error': str(e) }


@router.post('/upload-pdfs')
async def upload_pdfs(files: List[UploadFile] = File(...)):
    """Upload multiple PDF files and save them into the Books folder."""
    saved = []
    skipped = []
    try:
        # Resolve Books directory at project root
        books_dir = Path(__file__).resolve().parents[2] / 'Books'
        books_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            try:
                # Basic validation
                filename = (f.filename or '').strip()
                if not filename:
                    skipped.append({'file': filename or '(unnamed)', 'reason': 'empty filename'})
                    continue
                # Enforce .pdf extension
                if not filename.lower().endswith('.pdf'):
                    skipped.append({'file': filename, 'reason': 'not a PDF'})
                    continue
                # Sanitize filename and ensure uniqueness
                safe_name = filename.replace('..', '').replace('/', '_').replace('\\', '_')
                target = books_dir / safe_name
                if target.exists():
                    base = target.stem
                    ext = target.suffix
                    counter = 1
                    while True:
                        candidate = books_dir / f"{base}_{counter}{ext}"
                        if not candidate.exists():
                            target = candidate
                            break
                        counter += 1

                # Write file
                content = await f.read()
                with open(target, 'wb') as out:
                    out.write(content)
                saved.append({'file': filename, 'saved_as': target.name, 'size': len(content)})
            except Exception as fe:
                skipped.append({'file': getattr(f, 'filename', '(unknown)'), 'reason': str(fe)})

        return {
            'saved_count': len(saved),
            'skipped_count': len(skipped),
            'saved': saved,
            'skipped': skipped
        }
    except Exception as e:
        return Response(content=f"Upload failed: {e}", media_type="text/plain", status_code=500)

@router.post('/run-add-book')
def run_add_book(
    dry_run: bool = Query(False, description="If true, executes add_book.py with --dry-run"),
    api_base: str = Query('', description="API base to pass to add_book.py; defaults to current host if empty")
):
    """Run the add_book.py orchestrator script on the server."""
    try:
        project_root = Path(__file__).resolve().parents[2]
        script = project_root / 'add_book.py'
        if not script.exists():
            return Response(content=f"add_book.py not found at {script}", media_type="text/plain", status_code=404)

        cmd = [sys.executable, str(script)]
        if api_base:
            cmd += ['--api', api_base]
        if dry_run:
            cmd += ['--dry-run']

        # Force UTF-8 for child process to avoid Windows console encoding issues
        env = dict(os.environ)
        env.setdefault('PYTHONIOENCODING', 'utf-8')

        # Run synchronously and capture output
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(project_root),
            env=env,
        )
        out = proc.stdout if proc.stdout is not None else ''
        err = proc.stderr if proc.stderr is not None else ''
        return {
            'returncode': proc.returncode,
            'stdout': out[-20000:],  # cap output size
            'stderr': err[-20000:],
            'command': cmd,
        }
    except Exception as e:
        return Response(content=f"Failed to run add_book.py: {e}", media_type="text/plain", status_code=500)


@router.get('/search')
def search(q: str = Query(..., description="Search query"), k: int = 10, standard: Optional[str] = Query(None, description="Filter by standard: PMBOK|PRINCE2|ISO21500|ISO21502")):
    """Enhanced search with better navigation and metadata."""
    engine = get_engine()
    results = engine.query(q, k=k, standard_filter=standard)
    
    # Add enhanced metadata for better navigation
    enhanced_results = []
    for result in results:
        enhanced_result = {
            **result,
            'bookmark_id': f"{result['standard']}_{result['page']}_{hash(result['text'][:50])}",
            'navigation_hint': f"Found in {result['standard']} page {result['page']}",
            'relevance_score': result.get('score', 0.0),
            'text_preview': result['text'][:200] + "..." if len(result['text']) > 200 else result['text']
        }
        enhanced_results.append(enhanced_result)
    
    return {
        'results': enhanced_results,
        'query': q,
        'total_results': len(enhanced_results),
        'search_metadata': {
            'standards_searched': list(set(r['standard'] for r in enhanced_results)),
            'page_range': {
                'min': min(r['page'] for r in enhanced_results) if enhanced_results else 0,
                'max': max(r['page'] for r in enhanced_results) if enhanced_results else 0
            }
        }
    }


@router.get('/compare')
def compare(topic: str = Query(...)):
    """Enhanced comparison with detailed analysis."""
    engine = get_engine()
    results = engine.query(topic, k=20)
    
    # Organize results by standard
    buckets: Dict[str, Dict[str, Any]] = {
        'PMBOK': {'results': [], 'summary': None, 'link': None},
        'PRINCE2': {'results': [], 'summary': None, 'link': None},
        'ISO21500': {'results': [], 'summary': None, 'link': None},
        'ISO21502': {'results': [], 'summary': None, 'link': None}
    }
    
    for r in results:
        std = r['standard'].upper()
        if 'PMBOK' in std:
            buckets['PMBOK']['results'].append(r)
            if buckets['PMBOK']['summary'] is None:
                buckets['PMBOK']['summary'] = r['text']
                buckets['PMBOK']['link'] = r.get('link')
        elif 'PRINCE' in std:
            buckets['PRINCE2']['results'].append(r)
            if buckets['PRINCE2']['summary'] is None:
                buckets['PRINCE2']['summary'] = r['text']
                buckets['PRINCE2']['link'] = r.get('link')
        elif 'ISO21500' in std:
            buckets['ISO21500']['results'].append(r)
            if buckets['ISO21500']['summary'] is None:
                buckets['ISO21500']['summary'] = r['text']
                buckets['ISO21500']['link'] = r.get('link')
        elif 'ISO21502' in std:
            buckets['ISO21502']['results'].append(r)
            if buckets['ISO21502']['summary'] is None:
                buckets['ISO21502']['summary'] = r['text']
                buckets['ISO21502']['link'] = r.get('link')
    
    # Generate topic-adaptive insights based on available results
    # Heuristic: use top text per standard to craft bullets and attach links
    def _first_text(std_key: str):
        lst = buckets.get(std_key, {}).get('results', [])
        return lst[0] if lst else None

    sim = []
    dif = []
    uniq = []
    # Similarities: if all standards have some result, frame shared concepts
    if all(buckets[s]['results'] for s in buckets):
        sim.append(f"All standards cover {topic} with emphasis on governance and stakeholders")
    # Differences by standard focus
    if buckets['PMBOK']['results']:
        r = _first_text('PMBOK')
        dif.append(f"PMBOK highlights knowledge areas/process groups — p.{r['page']}" if r else "PMBOK highlights knowledge areas/process groups")
    if buckets['PRINCE2']['results']:
        r = _first_text('PRINCE2')
        dif.append(f"PRINCE2 stresses product-based planning and roles — p.{r['page']}" if r else "PRINCE2 stresses product-based planning and roles")
    if buckets['ISO21502']['results'] or buckets['ISO21500']['results']:
        r = _first_text('ISO21502') or _first_text('ISO21500')
        dif.append(f"ISO provides terminology and guidance applicable across contexts — p.{r['page']}" if r else "ISO provides terminology and guidance applicable across contexts")
    # Uniques: pick one highlight per standard
    for key, label in [('PMBOK','PMBOK'), ('PRINCE2','PRINCE2'), ('ISO21502','ISO'), ('ISO21500','ISO')]:
        r = _first_text(key)
        if r:
            uniq.append(f"{label}: {r['text'][:80]}… (p.{r['page']})")

    insights = {'similarities': sim, 'differences': dif, 'uniques': uniq}
    
    return {
        'topic': topic,
        'standards': buckets,
        'insights': insights,
        'comparison_metadata': {
            'total_results': len(results),
            'standards_covered': [k for k, v in buckets.items() if v['results']],
            'coverage_score': len([k for k, v in buckets.items() if v['results']]) / len(buckets)
        }
    }


@router.get('/compare/detailed')
def compare_detailed(topic: str = Query(..., description='Topic to compare in detail'), k: int = 30):
    engine = get_engine()
    data = engine.compare_detailed(topic, k=k)
    return data


@router.get('/analysis')
def analysis(k: int = 100, threshold: float = 0.6, unique_threshold: float = 0.35):
    """Automatically analyze all books using cross-book similarity for unique detection.
    
    Args:
        k: Number of chunks per book (default 100)
        threshold: Similarity threshold for similar/dissimilar classification (default 0.6)
        unique_threshold: Cross-book similarity threshold for uniqueness detection (default 0.35)
    
    Returns unique points per book based on cross-book similarity.
    """
    engine = get_engine()
    result = engine.analyze_all_books_auto(k=k, threshold=threshold, unique_threshold=unique_threshold)
    
    # Add enhanced debugging information
    similar_count = len([p for p in result['points'] if p['label'] == 'similar'])
    dissimilar_count = len([p for p in result['points'] if p['label'] == 'dissimilar'])
    unique_count = len([p for p in result['points'] if p['label'] == 'unique'])
    
    result['debug_info'] = {
        'total_points': len(result['points']),
        'similar_count': similar_count,
        'dissimilar_count': dissimilar_count,
        'unique_count': unique_count,
        'threshold_used': threshold,
        'unique_threshold_used': unique_threshold,
        'algorithm': result.get('algorithm', 'cross_book_similarity')
    }
    
    return result



@router.get('/graphs')
def graphs(topic: str = Query(..., description='Topic to plot across all books'), k: int = 60, threshold: float = 0.6, unique_threshold: float = 0.3) -> Dict[str, Any]:
    """Return points for all books projected to 2D with labels.

    Reuses the two-book analysis by pairing each book against the union to compute similarity flags,
    then projects combined vectors via PCA.
    """
    engine = get_engine()

    books = ['PMBOK', 'PRINCE2', 'ISO21500', 'ISO21502']
    all_hits: List[Dict[str, Any]] = []
    book_to_hits: Dict[str, List[Dict[str, Any]]] = {}
    for b in books:
        hits = engine.query(topic, k=k, standard_filter=b)
        book_to_hits[b] = hits
        all_hits.extend(hits)

    # If no data, return empty
    if not all_hits:
        return {'points': [], 'threshold': threshold}

    # Encode all and do PCA to 2D
    texts = [h['text'] for h in all_hits]
    vecs = engine._encode_texts(texts)
    import numpy as np  # type: ignore
    mean = vecs.mean(axis=0, keepdims=True)
    X = vecs - mean
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    components = Vt[:2].T
    proj = X @ components

    # For similarity label, compute within-book best against all other books
    # Also compute uniqueness score against other books to flag unique content
    # Pre-split projections back to hits
    points: List[Dict[str, Any]] = []
    offset = 0
    for b in books:
        hits = book_to_hits.get(b, [])
        n = len(hits)
        if n == 0:
            continue
        this_vecs = vecs[offset:offset+n]
        other_vecs = np.vstack([vecs[:offset], vecs[offset+n:]]) if len(vecs) > n else vecs[offset:offset+n]
        sim = this_vecs @ other_vecs.T
        max_sim = sim.max(axis=1) if other_vecs.shape[0] > 0 else np.zeros(n)
        for i, h in enumerate(hits):
            x, y = float(proj[offset + i, 0]), float(proj[offset + i, 1])
            # Determine labels:
            # - 'unique' if maximum similarity to any point in other books is below unique_threshold
            # - else 'similar' if max similarity >= threshold
            # - else 'dissimilar'
            max_s = float(max_sim[i])
            if max_s < unique_threshold:
                label = 'unique'
            elif max_s >= threshold:
                label = 'similar'
            else:
                label = 'dissimilar'
            points.append({
                'x': x,
                'y': y,
                'label': label,
                'standard': b,
                'text': h['text'],
                'link': h['link'],
                'page': h['page']
            })
        offset += n

    return {'points': points, 'threshold': threshold, 'unique_threshold': unique_threshold}


@router.get('/process-recommendation')
def process_recommendation(
    project_type: str = Query(..., description="Type of project: software, construction, research, etc."),
    project_size: str = Query(..., description="Project size: small, medium, large"),
    industry: str = Query(..., description="Industry: IT, construction, healthcare, etc."),
    methodology_preference: str = Query("PMBOK", description="Preferred methodology: PMBOK, PRINCE2, ISO"),
    use_ai: bool = Query(False, description="Use AI-powered generation (Gemini)")
):
    """Generate tailored project process recommendations using AI and PM standards."""
    try:
        engine = get_engine()
        
        # Broad results for non-AI sections (kept for UI recommendations list)
        search_queries = [
            f"{project_type} {project_size} {industry} project process",
            "project lifecycle planning stakeholder risk quality scope schedule budget"
        ]
        all_results = []
        for query in search_queries:
            all_results.extend(engine.query(query, k=10))
    
        # Organize recommendations by standard (for evidence display)
        recommendations = {
            'PMBOK': {'processes': []},
            'PRINCE2': {'processes': []},
            'ISO': {'processes': []}
        }
        
        for result in all_results:
            standard = result['standard'].upper()
            # Generate proper view link
            view_link = f"/view?standard={result['standard']}&page={result['page']}&text={result['text'][:100]}"
            
            if 'PMBOK' in standard:
                recommendations['PMBOK']['processes'].append({
                    'name': f"Process from {result['standard']}",
                    'description': result['text'][:200],
                    'page': result['page'],
                    'link': view_link
                })
            elif 'PRINCE' in standard:
                recommendations['PRINCE2']['processes'].append({
                    'name': f"Process from {result['standard']}",
                    'description': result['text'][:200],
                    'page': result['page'],
                    'link': view_link
                })
            elif 'ISO' in standard:
                recommendations['ISO']['processes'].append({
                    'name': f"Process from {result['standard']}",
                    'description': result['text'][:200],
                    'page': result['page'],
                    'link': view_link
                })
    
        # Generate AI-powered process recommendation
        if use_ai:
            try:
                print(f"🤖 Attempting AI generation for {project_type} project in {industry}...")
                # Build a focused topic for evidence retrieval from selected book(s)
                topic = (
                    f"{project_size} {project_type} {industry} project management process lifecycle planning stakeholder risk quality scope schedule budget"
                )

                # Helper: strict book filtering to selected methodology
                def _matches_preference(std: str, pref: str) -> bool:
                    s = (std or '').upper()
                    p = (pref or '').upper()
                    if p == 'PMBOK':
                        return 'PMBOK' in s
                    if p == 'PRINCE2':
                        return 'PRINCE' in s
                    if p == 'ISO':
                        return 'ISO21500' in s or 'ISO21502' in s or s.startswith('ISO')
                    return False

                # Retrieve top similar chunks to the composed topic from ALL books first
                evidence_candidates = engine.query(topic, k=80)
                
                # Filter to ONLY the selected methodology's book(s)
                filtered_evidence = [r for r in evidence_candidates if _matches_preference(r.get('standard', ''), methodology_preference)]
                
                print(f"   [DEBUG] Retrieved {len(evidence_candidates)} total candidates, filtered to {len(filtered_evidence)} from selected book(s)")
                print(f"   [DEBUG] Selected books: {list(set(r['standard'] for r in filtered_evidence))}")

                if not filtered_evidence:
                    print("⚠️ No evidence matched selected methodology; falling back...")
                    raise RuntimeError('no-evidence-for-methodology')

                ai_generated_process = generate_process_recommendation(
                    project_type=project_type,
                    project_size=project_size,
                    industry=industry,
                    methodology_preference=methodology_preference,
                    evidence_snippets=filtered_evidence
                )
                
                print(f"✅ AI generation successful!")
                
                # Structure the AI response properly
                # External retrieval for additional context (non-book citations)
                external = retrieve_external_context(topic, limit_total=4)

                # Build structured citations from filtered evidence
                citations = []
                for r in filtered_evidence[:25]:
                    citations.append({
                        'standard': r.get('standard'),
                        'page': r.get('page'),
                        'link': r.get('link'),
                        'excerpt': (r.get('text') or '')[:240]
                    })
                # Add external references as citations with source tag
                for ex in external:
                    citations.append({
                        'standard': ex.get('source'),
                        'page': '-',
                        'link': ex.get('url'),
                        'excerpt': f"{ex.get('title','')} — {ex.get('snippet','')[:180]}",
                        'external': True
                    })

                # Parse structured phases/activities from the generated text
                def _parse_structured_process(text: str) -> dict:
                    lines = [ln.strip() for ln in (text or '').split('\n') if ln.strip()]
                    phases: list[dict] = []
                    current_phase: dict | None = None
                    act_counter = 0
                    for ln in lines:
                        if ln[:2].isdigit() or ln.lower().startswith(('phase', 'stage', 'step')) or ln[:2].strip('.').isdigit():
                            # new phase
                            current_phase = {'title': ln.split(':')[0][:120], 'activities': []}
                            phases.append(current_phase)
                        elif ln.startswith(('-', '•', '*')):
                            act_counter += 1
                            if current_phase is None:
                                current_phase = {'title': 'Process', 'activities': []}
                                phases.append(current_phase)
                            current_phase['activities'].append({'id': f'a{act_counter}', 'title': ln.lstrip('-•* ').strip()[:160]})
                    if not phases:
                        phases = [{'title': 'Process', 'activities': []}]
                    return {'phases': phases}

                structured = _parse_structured_process(ai_generated_process)

                # Map each activity to nearest evidence snippet using embeddings
                engine_local = get_engine()
                ev_texts = [(r.get('text') or '') for r in filtered_evidence]
                ev_vecs = engine_local._encode_texts(ev_texts) if ev_texts else None
                step_citations: dict[str, list] = {}
                if ev_vecs is not None and len(ev_texts) > 0:
                    # flatten activities
                    activities: list[dict] = []
                    for ph in structured['phases']:
                        for act in ph.get('activities', []):
                            activities.append(act)
                    if activities:
                        act_vecs = engine_local._encode_texts([a['title'] for a in activities])
                        import numpy as np  # type: ignore
                        sims = act_vecs @ ev_vecs.T
                        for i, act in enumerate(activities):
                            j = int(np.argmax(sims[i]))
                            r = filtered_evidence[j]
                            step_citations[act['id']] = [{
                                'standard': r.get('standard'),
                                'page': r.get('page'),
                                'link': r.get('link'),
                                'excerpt': (r.get('text') or '')[:200]
                            }]

                # Heuristic roles extraction and default RACI
                def _extract_roles(text: str) -> list[str]:
                    default = ['Project Manager', 'Sponsor', 'Team Lead', 'Stakeholder']
                    extra = []
                    low = (text or '').lower()
                    if 'product owner' in low: extra.append('Product Owner')
                    if 'scrum master' in low: extra.append('Scrum Master')
                    if 'qa' in low or 'quality' in low: extra.append('QA Lead')
                    roles = default + [r for r in extra if r not in default]
                    # de-duplicate
                    seen = set(); uniq = []
                    for r in roles:
                        if r not in seen:
                            uniq.append(r); seen.add(r)
                    return uniq

                roles = _extract_roles(ai_generated_process)

                # Build simple RACI: PM=Accountable, Team Lead=Responsible, Sponsor=Informed, Stakeholder=Consulted
                raci = {}
                for ph in structured['phases']:
                    for act in ph.get('activities', []):
                        entries = []
                        if 'Team Lead' in roles: entries.append({'role': 'Team Lead', 'assignment': 'R'})
                        if 'Project Manager' in roles: entries.append({'role': 'Project Manager', 'assignment': 'A'})
                        if 'Stakeholder' in roles: entries.append({'role': 'Stakeholder', 'assignment': 'C'})
                        if 'Sponsor' in roles: entries.append({'role': 'Sponsor', 'assignment': 'I'})
                        raci[act['id']] = entries

                # Derive decision gates from text or provide defaults
                def _extract_gates(text: str) -> list[dict]:
                    gates: list[dict] = []
                    lines = [ln.strip() for ln in (text or '').split('\n') if ln.strip()]
                    for ln in lines:
                        if any(k in ln.lower() for k in ['gate', 'approval', 'go/no-go']):
                            gates.append({
                                'name': ln[:120],
                                'entry': ['Inputs prepared'],
                                'exit': ['Approved / Not approved']
                            })
                    if not gates:
                        gates = [
                            {'name': 'Gate 1: Initiation Approval', 'entry': ['Business Case'], 'exit': ['Charter Approved']},
                            {'name': 'Gate 2: Plan Approval', 'entry': ['Baseline Plans'], 'exit': ['Execution Go-Ahead']}
                        ]
                    return gates

                decision_gates = _extract_gates(ai_generated_process)

                ai_recommendation = {
                    'process': ai_generated_process,
                    'citations': citations,
                    'structured': structured,
                    'step_citations': step_citations,
                    'roles': roles,
                    'raci': raci,
                    'decision_gates': decision_gates,
                    'justification': 'Process generated using AI with PM standards evidence'
                }
                
                return {
                    'mode': 'ai_generated',
                    'ai_recommendation': ai_recommendation,
                    'recommendations': recommendations,
                    'evidence_base': {
                        'total_sources': len(filtered_evidence),
                        'standards_consulted': list(set(r['standard'] for r in filtered_evidence)),
                        'ai_powered': True
                    }
                }
            except Exception as e:
                print(f"❌ AI generation failed: {e}")
                import traceback
                traceback.print_exc()
                # Fall through to fallback with error message
                print("⚠️ Falling back to template-based generation...")
        
        # Fallback: Basic template-based recommendations
        # Add roles and decision gates to template-based recommendations
        def _generate_roles(project_type: str, project_size: str) -> list:
            roles = [
                'Project Manager', 'Sponsor', 'Team Lead', 'Stakeholder'
            ]
            if project_type == 'software':
                roles.extend(['Product Owner', 'Scrum Master', 'QA Lead'])
            if project_size == 'large':
                roles.extend(['Program Manager', 'PMO'])
            return roles

        def _generate_decision_gates(project_type: str, project_size: str) -> list:
            gates = [
                {'name': 'Gate 1: Initiation Approval', 'entry': ['Business case'], 'exit': ['Charter approved']},
                {'name': 'Gate 2: Plan Approval', 'entry': ['Baseline plans'], 'exit': ['Execution go-ahead']},
                {'name': 'Gate 3: Closure Acceptance', 'entry': ['Deliverables complete'], 'exit': ['Lessons learned captured']}
            ]
            if project_type == 'software':
                gates.insert(2, {'name': 'Gate 2b: Release Readiness', 'entry': ['Test reports'], 'exit': ['Deployment approval']})
            if project_size == 'large':
                gates.insert(1, {'name': 'Gate 1b: Procurement Strategy', 'entry': ['Procurement plan'], 'exit': ['Contracts approved']})
            return gates

        tailored_recommendations = {
            'project_characteristics': {
                'type': project_type,
                'size': project_size,
                'industry': industry,
                'methodology_preference': methodology_preference
            },
            'recommended_approach': _generate_approach_recommendation(project_type, project_size, methodology_preference),
            'process_phases': _generate_process_phases(project_type, project_size),
            'key_activities': _generate_key_activities(project_type, industry),
            'critical_deliverables': _generate_deliverables(project_type, project_size),
            'tailoring_guidance': _generate_tailoring_guidance(project_type, project_size, industry),
            'roles': _generate_roles(project_type, project_size),
            'decision_gates': _generate_decision_gates(project_type, project_size)
        }
        
        return {
            'mode': 'template_based',
            'recommendations': recommendations,
            'tailored_approach': tailored_recommendations,
            'evidence_base': {
                'total_sources': len(all_results),
                'standards_consulted': list(set(r['standard'] for r in all_results)),
                'confidence_level': 'High' if len(all_results) > 10 else 'Medium',
                'ai_powered': False
            }
        }
    except Exception as e:
        print(f"[ERROR] process_recommendation failed: {e}")
        try:
            import traceback; traceback.print_exc()
        except Exception:
            pass
        return {
            'mode': 'template_based',
            'recommendations': {'PMBOK': {'processes': []}, 'PRINCE2': {'processes': []}, 'ISO': {'processes': []}},
            'tailored_approach': {
                'project_characteristics': {
                    'type': project_type,
                    'size': project_size,
                    'industry': industry,
                    'methodology_preference': methodology_preference
                },
                'recommended_approach': _generate_approach_recommendation(project_type, project_size, methodology_preference),
                'process_phases': _generate_process_phases(project_type, project_size),
                'key_activities': _generate_key_activities(project_type, industry),
                'critical_deliverables': _generate_deliverables(project_type, project_size),
                'tailoring_guidance': _generate_tailoring_guidance(project_type, project_size, industry),
                'roles': ['Project Manager','Sponsor','Team Lead','Stakeholder'],
                'decision_gates': [
                    {'name': 'Gate 1: Initiation Approval', 'entry': ['Business case'], 'exit': ['Charter approved']}
                ]
            },
            'evidence_base': {
                'total_sources': 0,
                'standards_consulted': [],
                'confidence_level': 'Low',
                'ai_powered': False
            }
        }


@router.get('/summary')
def summary(
    standard: str = Query(..., description="Book to summarize: PMBOK|PRINCE2|ISO21500|ISO21502"),
    use_ai: bool = Query(True, description="Use AI-powered summarization (Gemini)"),
    k: int | None = None
):
    """Generate a comprehensive summary for a selected standard using AI.

    Uses Gemini AI to create detailed, well-structured summaries based on content from the standard.
    """
    engine = get_engine()
    # Get snippets from the selected standard
    snippets = engine.get_all_snippets_for_standard(standard)
    
    if use_ai and snippets:
        try:
            # Use Gemini AI for comprehensive summary
            ai_summary = generate_summary(standard, snippets)
            return {
                'standard': standard,
                'summary': ai_summary,
                'sources_count': len(snippets),
                'ai_powered': True,
                'mode': 'ai_generated'
            }
        except Exception as e:
            print(f"AI summary generation failed: {e}")
            # Fall through to fallback
    
    # Fallback: Use basic summarization
    result = summarize_book_from_snippets(standard, snippets)
    result['ai_powered'] = False
    result['mode'] = 'template_based'
    return result


def _generate_approach_recommendation(project_type: str, project_size: str, methodology_preference: str) -> str:
    """Generate approach recommendation based on project characteristics."""
    return f"Use {methodology_preference} methodology tailored for {project_size} {project_type} projects"


def _generate_process_phases(project_type: str, project_size: str) -> list:
    """Generate process phases based on project characteristics."""
    base_phases = ["Initiation", "Planning", "Execution", "Monitoring & Control", "Closure"]
    
    if project_type == "software":
        return ["Requirements", "Design", "Development", "Testing", "Deployment", "Maintenance"]
    elif project_type == "construction":
        return ["Pre-construction", "Construction", "Commissioning", "Handover"]
    else:
        return base_phases


def _generate_key_activities(project_type: str, industry: str) -> list:
    """Generate key activities based on project type and industry."""
    activities = [
        "Stakeholder identification and engagement",
        "Risk assessment and mitigation planning",
        "Resource planning and allocation",
        "Quality assurance and control",
        "Communication management"
    ]
    
    if project_type == "software":
        activities.extend(["Code review", "Testing strategy", "Version control"])
    elif project_type == "construction":
        activities.extend(["Safety planning", "Permit acquisition", "Site preparation"])
    
    return activities


def _generate_deliverables(project_type: str, project_size: str) -> list:
    """Generate critical deliverables based on project characteristics."""
    deliverables = [
        "Project charter",
        "Project management plan",
        "Risk register",
        "Stakeholder register",
        "Lessons learned document"
    ]
    
    if project_size == "large":
        deliverables.extend(["Program management plan", "Portfolio dashboard"])
    
    return deliverables


def _generate_tailoring_guidance(project_type: str, project_size: str, industry: str) -> list:
    """Generate tailoring guidance based on project characteristics."""
    guidance = [
        f"Tailor processes for {project_size} {project_type} projects in {industry}",
        "Adjust communication frequency based on project complexity",
        "Customize risk management approach for industry-specific risks",
        "Modify quality standards based on regulatory requirements"
    ]
    
    return guidance


@router.get('/export-pdf')
def export_process_pdf(
    project_type: str = Query(..., description="Type of project: software, construction, research, etc."),
    project_size: str = Query(..., description="Project size: small, medium, large"),
    industry: str = Query(..., description="Industry: IT, construction, healthcare, etc."),
    methodology_preference: str = Query("PMBOK", description="Preferred methodology: PMBOK, PRINCE2, ISO"),
    scenario_description: str = Query("", description="Optional scenario description"),
    process_text: str = Query("", description="Process text to include in PDF"),
    citations_json: str = Query("", description="Citations as JSON string"),
    ai_model_answer: str = Query("", description="Complete AI model answer"),
    evidence_base: str = Query("", description="Evidence base information")
):
    """Export process recommendation as a professional PDF document."""
    try:
        import json
        
        # Prepare data for PDF generation
        process_data = {
            'project_type': project_type,
            'project_size': project_size,
            'industry': industry,
            'methodology_preference': methodology_preference,
            'scenario_description': scenario_description,
            'process_text': process_text or f"Generated process for {project_size} {project_type} project in {industry} industry using {methodology_preference} methodology.",
            'ai_model_answer': ai_model_answer,
            'citations': None
        }
        
        # Parse citations if provided
        if citations_json:
            try:
                process_data['citations'] = json.loads(citations_json)
            except json.JSONDecodeError:
                print("Warning: Could not parse citations JSON")
        
        # Generate PDF
        pdf_bytes = generate_process_pdf(process_data)
        
        # Return PDF as streaming response
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=process_recommendation_{project_type}_{project_size}.pdf"
            }
        )
        
    except Exception as e:
        print(f"PDF generation failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Return error response
        return Response(
            content=f"PDF generation failed: {str(e)}",
            status_code=500,
            media_type="text/plain"
        )


@router.post('/export-pdf')
def export_process_pdf_post(payload: Dict[str, Any]):
    """POST variant: accepts JSON payload to handle large process_text safely."""
    try:
        import json
        
        # Extract and normalize fields from JSON
        project_type = str(payload.get('project_type', '') or '')
        project_size = str(payload.get('project_size', '') or '')
        industry = str(payload.get('industry', '') or '')
        methodology_preference = str(payload.get('methodology_preference', 'PMBOK') or 'PMBOK')
        scenario_description = str(payload.get('scenario_description', '') or '')
        process_text = str(payload.get('process_text', '') or '')
        ai_model_answer = str(payload.get('ai_model_answer', '') or '')
        citations = payload.get('citations')
        evidence_base = payload.get('evidence_base')

        # Build process data
        process_data = {
            'project_type': project_type,
            'project_size': project_size,
            'industry': industry,
            'methodology_preference': methodology_preference,
            'scenario_description': scenario_description,
            'process_text': process_text or f"Generated process for {project_size} {project_type} project in {industry} industry using {methodology_preference} methodology.",
            'ai_model_answer': ai_model_answer,
            'citations': None,
            'evidence_base': evidence_base
        }

        # Normalize citations
        if citations:
            if isinstance(citations, str):
                try:
                    process_data['citations'] = json.loads(citations)
                except Exception:
                    process_data['citations'] = None
            elif isinstance(citations, dict):
                process_data['citations'] = citations
            else:
                try:
                    process_data['citations'] = dict(citations)
                except Exception:
                    process_data['citations'] = None

        # Generate PDF
        pdf_bytes = generate_process_pdf(process_data)

        # Return PDF as streaming response
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=process_recommendation_{project_type or 'project'}_{project_size or 'size'}.pdf"
            }
        )
    except Exception as e:
        print(f"PDF generation failed (POST): {e}")
        import traceback
        traceback.print_exc()
        return Response(
            content=f"PDF generation failed: {str(e)}",
            media_type="text/plain",
            status_code=500
        )


@router.get('/process-by-id')
def process_by_id(code: str = Query(..., description='5-digit process code, e.g., 11111')) -> Dict[str, Any]:
    """Fetch a process by its 5-digit code using filesystem only.

    Logic:
    1) If code is listed in no_data/no_embedding.txt -> read information/response/{code}.txt
    2) Else -> read information/response_with_embeddings/{code}.txt and {code}_references.json (if exists)
    Returns the discovered content; does not call any AI models.
    """
    code_str = str(code).strip()
    if not (len(code_str) == 5 and code_str.isdigit()):
        return { 'error': 'Invalid code format. Expected 5 digits like 11111.' }

    base = Path(__file__).resolve().parents[2]  # project root
    no_data_file = base / 'no_data' / 'no_embedding.txt'
    resp_dir = base / 'information' / 'response'
    resp_emb_dir = base / 'information' / 'response_with_embeddings'

    try:
        # Check if code is in no_embedding index
        in_no_embedding = False
        if no_data_file.exists():
            txt = no_data_file.read_text(encoding='utf-8', errors='ignore')
            in_no_embedding = f"[{code_str}]" in txt

        if in_no_embedding:
            # Return plain response file
            target = resp_dir / f"{code_str}.txt"
            if not target.exists():
                return { 'error': f'Listed in no_embedding but missing file: {target.name}' }
            content = target.read_text(encoding='utf-8', errors='ignore')
            return {
                'code': code_str,
                'source': 'response',
                'path': str(target),
                'text': content
            }

        # Otherwise, try with-embeddings files
        target_txt = resp_emb_dir / f"{code_str}.txt"
        target_json = resp_emb_dir / f"{code_str}_references.json"
        if not target_txt.exists():
            return { 'error': f'Process not found for code {code_str} in either area.' }

        content = target_txt.read_text(encoding='utf-8', errors='ignore')
        references = None
        if target_json.exists():
            try:
                import json
                references = json.loads(target_json.read_text(encoding='utf-8', errors='ignore'))
            except Exception:
                references = None

        return {
            'code': code_str,
            'source': 'response_with_embeddings',
            'path': str(target_txt),
            'text': content,
            'references': references
        }
    except Exception as e:
        return { 'error': str(e) }

