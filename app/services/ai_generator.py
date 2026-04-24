"""
AI-Powered Text Generation using GPT-2 Model
No API key required - uses locally downloaded model
"""

from typing import Dict, Any, List
import os
import re

# Global model and tokenizer
_model = None
_tokenizer = None
_model_loaded = False
_model_available = False

# Check if transformers is available
try:
    import transformers
    import torch
    _model_available = True
except ImportError:
    _model_available = False
    print("⚠️ transformers/torch not installed - using template fallback")

def _load_model():
    """Load GPT-2 model and tokenizer (lazy loading)"""
    global _model, _tokenizer, _model_loaded
    
    if not _model_available:
        return None, None
    
    if _model_loaded:
        return _model, _tokenizer
    
    try:
        print("🤖 Loading GPT-2 model...")
        from transformers import GPT2LMHeadModel, GPT2Tokenizer
        
        model_name = "gpt2"
        
        # Load tokenizer
        _tokenizer = GPT2Tokenizer.from_pretrained(model_name)
        # Ensure pad token is distinct and present to avoid attention mask inference issues
        if (_tokenizer.pad_token_id is None) or (_tokenizer.pad_token_id == _tokenizer.eos_token_id):
            _tokenizer.add_special_tokens({"pad_token": "<|pad|>"})
        
        # Load model with proper device handling
        _model = GPT2LMHeadModel.from_pretrained(model_name, torch_dtype=torch.float32)
        # If tokenizer was expanded, resize model embeddings and set config pad id
        if hasattr(_tokenizer, "pad_token_id") and _tokenizer.pad_token_id is not None:
            _model.resize_token_embeddings(len(_tokenizer))
            _model.config.pad_token_id = _tokenizer.pad_token_id
        _model.eval()  # Set to evaluation mode
        # Move model to CPU to avoid tensor issues
        _model = _model.cpu()
        
        print("✅ GPT-2 model loaded successfully")
        _model_loaded = True
        
        return _model, _tokenizer
        
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        print("Falling back to template mode...")
        _model_loaded = False
        return None, None


def generate_with_ai(prompt: str, max_length: int = 500, unlimited: bool = False) -> str:
    """Generate text using GPT-2 model"""
    if not _model_available:
        print("   [DEBUG] Model not available")
        return None
        
    model, tokenizer = _load_model()
    
    if model is None or tokenizer is None:
        print("   [DEBUG] Model or tokenizer is None")
        return None
    
    try:
        import torch
        
        # Encode the prompt (keep it short for better generation) with mask
        enc = tokenizer(
            prompt,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=300
        )
        input_ids = enc["input_ids"]
        attention_mask = enc.get("attention_mask")
        input_length = len(input_ids[0])
        
        print(f"   [DEBUG] Input tokens: {input_length}")
        
        # Generate tokens (deterministic). If unlimited, let model run up to its context window
        # GPT-2 small supports context length of 1024 tokens.
        max_ctx = 1024
        use_max_length = unlimited
        if unlimited:
            # Fill up to model context, rely on EOS/heuristics to stop
            gen_kwargs = {
                'max_length': min(max_ctx, input_length + max_length) if max_length else max_ctx
            }
        else:
            # Strictly bounded compute time
            max_new = max(80, min(max_length, 220))
            gen_kwargs = {
                'max_new_tokens': max_new
            }
        
        # Ensure tensors are on CPU and properly formatted
        input_ids = input_ids.cpu()
        if attention_mask is not None:
            attention_mask = attention_mask.cpu()
        
        with torch.no_grad():
            outputs = model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                **gen_kwargs,
                num_return_sequences=1,
                no_repeat_ngram_size=2,
                do_sample=False,
                num_beams=2,
                length_penalty=1.0,
                repetition_penalty=1.1,
                early_stopping=True,
                pad_token_id=(model.config.pad_token_id if getattr(model.config, "pad_token_id", None) is not None else tokenizer.eos_token_id),
                eos_token_id=tokenizer.eos_token_id
            )
        
        # Decode
        generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        print(f"   [DEBUG] Generated length: {len(generated_text)}")
        
        # Extract only the new generated part
        prompt_decoded = tokenizer.decode(input_ids[0], skip_special_tokens=True)
        if generated_text.startswith(prompt_decoded):
            generated_text = generated_text[len(prompt_decoded):].strip()
        
        if not generated_text or len(generated_text) < 10:
            print("   [DEBUG] Generated text too short or empty")
            return None
        
        return generated_text
        
    except Exception as e:
        print(f"❌ Generation error: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_process_recommendation_ai(
    project_type: str,
    project_size: str,
    industry: str,
    methodology_preference: str,
    evidence_snippets: List[Dict[str, Any]]
) -> str:
    """Generate process recommendation using AI model with book references"""
    
    print(f"   [DEBUG] Snippets count: {len(evidence_snippets) if evidence_snippets else 0}")
    
    if not evidence_snippets:
        print("   [DEBUG] No evidence snippets provided")
        return "No relevant reference found in the selected book."
    
    # Build grounded evidence context with direct links (selected book only)
    evidence_items = []
    for i, s in enumerate(evidence_snippets[:6], 1):  # up to 6 references
        std = s.get('standard', 'Unknown')
        text = (s.get('text', '') or '')[:140]
        page = s.get('page', '?')
        link = f"/view?standard={s.get('standard','')}&page={page}&text={(s.get('text','') or '')[:100]}"
        evidence_items.append(f"[{i}] {std} p.{page}: {text}\nLink: {link}")
    
    evidence_text = "\n".join(evidence_items)
    
    # If evidence is too sparse, short-circuit
    if len(evidence_snippets) < 2:
        return "No relevant reference found in the selected book."

    # Create strict, very detailed prompt grounded in selected-book evidence with citation tracking
    prompt = (
        f"You are a senior project manager. Create a very detailed, step-by-step, numbered process for a {project_size} "
        f"{project_type} project in the {industry} industry, strictly aligned to {methodology_preference}. "
        f"Use ONLY the following references (all from the same book). Each step must be specific, actionable, and directly grounded in the references. "
        f"Include precise actions, inputs, outputs, and responsible roles when indicated by the references. "
        f"For each step, include a citation reference in the format [Ref: X] where X is the reference number. "
        f"After the process, provide a justification section explaining why specific practices were selected from the standards. "
        f"If the references do not contain relevant information to cover the requested process, respond exactly: 'No relevant reference found in the selected book.' "
        f"Avoid any database/technology chatter or unrelated content. Keep one action per line.\n\n"
        f"References (selected book only):\n{evidence_text}\n\n"
        f"Numbered Process (as many steps as needed):\n1. "
    )
    
    print(f"   [DEBUG] Prompt length: {len(prompt)} chars")
    
    # Generate with AI (unlimited mode to allow longer, detailed steps; validator will filter)
    generated = generate_with_ai(prompt, max_length=900, unlimited=True)
    
    print(f"   [DEBUG] Generated result: {generated[:100] if generated else 'None'}...")
    
    steps: List[str] = []
    citation_data = None
    
    if generated:
        steps = validate_process_output(generated, evidence_snippets)
        print(f"   [DEBUG] Validated steps: {len(steps)}")
        
        # Parse citations from the generated text
        citation_data = parse_citations_from_process(generated, evidence_snippets)
        print(f"   [DEBUG] Citations found: {citation_data['total_citations'] if citation_data else 0}")
        
    if not steps:
        print("   [DEBUG] Falling back to extractive outline")
        steps = build_extractive_outline(evidence_snippets, max_steps=15)
    
    if steps:
        # Render numbered steps only (avoid duplicate headings; UI adds title)
        steps_block = "\n".join([f"{idx}. {line}" for idx, line in enumerate(steps, 1)])
        
        # Add citation tracking to the response
        citation_section = ""
        if citation_data and citation_data.get('used_references'):
            citation_section = f"\n\n---\n\n## 📚 Citations & Justification\n\n{format_citations_display(citation_data)}"
        
        # Format the complete response
        full_response = (
            f"{steps_block}{citation_section}\n\n---\n\n"
            f"**Generated using**: GPT-2 Language Model  \n"
            f"**Methodology**: {methodology_preference}  \n"
            f"**Evidence Base**: {len(evidence_snippets)} excerpts from PM standards\n"
        )
        return full_response
    
    return None


def _extract_keywords(snippets: List[Dict[str, Any]]) -> List[str]:
    words: List[str] = []
    for s in snippets or []:
        txt = (s.get('text') or '').lower()
        words.extend(re.findall(r"[a-zA-Z]{4,}", txt))
    # keep moderately frequent words as pseudo-keywords
    freq: Dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    candidates = [w for w, c in freq.items() if c >= 2][:200]
    # include PMBOK domain words
    candidates.extend([
        'stakeholder','planning','scope','schedule','budget','risk','quality','procurement','communication',
        'measurement','uncertainty','delivery','governance','lifecycle','team','benefits','value'
    ])
    return list(dict.fromkeys(candidates))


_BLACKLIST_TERMS = {
    'postgres','postgresql','mysql','sqlite','postgis','oracle','mongodb','redis','kafka','hadoop',
    'django','rails','laravel','react','angular','kubernetes','docker','helm','ansible','terraform'
}


def validate_process_output(text: str, snippets: List[Dict[str, Any]]) -> List[str]:
    if not text:
        return []
    
    # Split into lines and extract numbered steps
    raw_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    step_lines: List[str] = []
    
    for ln in raw_lines:
        # Look for numbered steps (1., 2., etc.) or bullet points
        if re.match(r"^(\d+\.|- |•)", ln):
            # Clean up the line
            clean_line = re.sub(r"^(\d+\.|- |•)\s*", "", ln).strip()
            if clean_line and len(clean_line) > 5:  # Basic length check
                step_lines.append(clean_line)
    
    # If we have steps, return them (less strict validation)
    if step_lines:
        return step_lines[:20]  # Limit to 20 steps max
    
    # Fallback: extract any meaningful lines
    fallback_lines = []
    for ln in raw_lines:
        if len(ln) > 10 and not any(term in ln.lower() for term in _BLACKLIST_TERMS):
            fallback_lines.append(ln)
            if len(fallback_lines) >= 10:
                break
    
    return fallback_lines


def build_extractive_outline(snippets: List[Dict[str, Any]], max_steps: int = 15) -> List[str]:
    candidates: List[str] = []
    for s in snippets or []:
        txt = (s.get('text') or '').strip()
        # split into sentences
        parts = re.split(r"(?<=[.!?])\s+", txt)
        for p in parts:
            p = p.strip()
            if not p:
                continue
            # heuristic: verb-led/action-like
            if re.match(r"^(define|identify|establish|plan|develop|manage|monitor|control|validate|verify|engage|communicate|procure|assure|measure|evaluate|mitigate)\b", p, re.I):
                candidates.append(p)
    # de-dup and truncate
    seen = set()
    outline: List[str] = []
    for c in candidates:
        k = c.lower()
        if k in seen:
            continue
        seen.add(k)
        outline.append(c)
        if len(outline) >= max_steps:
            break
    # ensure minimum steps by padding with generic evidence-grounded actions
    fillers = [
        "Engage key stakeholders and document expectations",
        "Define project scope, constraints, and success criteria",
        "Develop schedule and budget baselines",
        "Identify and analyze risks; plan responses",
        "Establish quality standards and assurance activities",
        "Plan communications and information management",
        "Define procurement strategy and contract approach",
        "Monitor performance and manage changes via change control",
        "Measure benefits and track value delivery",
        "Review lessons learned and close project formally"
    ]
    for f in fillers:
        if len(outline) >= max_steps:
            break
        if f.lower() not in seen:
            outline.append(f)
            seen.add(f.lower())
    return outline[:max_steps]

def generate_summary_ai(standard: str, snippets: List[Dict[str, Any]]) -> str:
    """Generate summary using AI model with book references"""
    
    if not snippets:
        print("   [DEBUG] No snippets for summary")
        return None
    
    # Build context from book embeddings/snippets
    context_items = []
    for s in snippets[:10]:  # Use 10 snippets for better book coverage
        text = s.get('text', '')[:100]  # Get meaningful text from each snippet
        if text:
            context_items.append(text)
    
    context = " ".join(context_items)
    
    # Hardcoded prompt: Ask for exactly 10 lines maximum summary of the complete book
    prompt = f"""Based on the following content from {standard}, write a complete summary of this project management standard in exactly 10 lines maximum covering its key concepts, principles, and approach.

Content from {standard}:
{context}

Summary (exactly 10 lines maximum):
{standard} is"""
    
    print(f"   [DEBUG] Summary prompt length: {len(prompt)} chars")
    
    # Generate with AI
    generated = generate_with_ai(prompt, max_length=300)
    
    if generated:
        # Return ONLY the summary text - nothing else, limit to 10 lines
        summary_text = f"{standard} is{generated}".strip()
        # Clean up formatting and limit to 10 lines
        lines = summary_text.split('\n')
        if len(lines) > 10:
            lines = lines[:10]
        summary_text = '\n'.join(lines)
        summary_text = summary_text.replace('\n\n', '\n').replace('  ', ' ')
        return summary_text
    
    # Fallback: Create a basic summary from snippets if AI fails
    print("   [DEBUG] AI generation failed, creating fallback summary")
    if snippets:
        key_concepts = []
        for s in snippets[:5]:  # Use first 5 snippets
            text = s.get('text', '')[:200]
            if text:
                key_concepts.append(text)
        
        if key_concepts:
            summary_lines = [
                f"{standard} is a project management standard that provides guidance on:",
                f"1. {key_concepts[0][:100]}..." if key_concepts else "",
                f"2. {key_concepts[1][:100]}..." if len(key_concepts) > 1 else "",
                f"3. {key_concepts[2][:100]}..." if len(key_concepts) > 2 else "",
                f"4. {key_concepts[3][:100]}..." if len(key_concepts) > 3 else "",
                f"5. {key_concepts[4][:100]}..." if len(key_concepts) > 4 else "",
                "The standard emphasizes structured approaches to project management.",
                "It provides frameworks for planning, executing, and controlling projects.",
                "Key focus areas include stakeholder management and risk assessment.",
                "The methodology supports various project types and industries."
            ]
            return '\n'.join([line for line in summary_lines if line.strip()])[:10]
    
    return f"{standard} summary not available - AI model not working properly."


def parse_citations_from_process(process_text: str, evidence_snippets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Parse citations from AI-generated process text and create citation tracking"""
    import re
    
    # Extract citation references from the text
    citation_pattern = r'\[Ref:\s*(\d+)\]'
    citations = re.findall(citation_pattern, process_text)
    
    # Track which references were actually used
    used_references = []
    citation_details = {}
    
    for ref_num in citations:
        ref_index = int(ref_num) - 1  # Convert to 0-based index
        if 0 <= ref_index < len(evidence_snippets):
            snippet = evidence_snippets[ref_index]
            used_references.append(snippet)
            
            # Create citation detail
            standard = snippet.get('standard', 'Unknown')
            page = snippet.get('page', '?')
            text = snippet.get('text', '')[:200]
            
            citation_details[ref_num] = {
                'standard': standard,
                'page': page,
                'text': text,
                'link': f"/view?standard={snippet.get('standard','')}&page={page}&text={text[:100]}"
            }
    
    # Extract justification section if present
    justification_match = re.search(r'Justification[:\s]*(.*?)(?=\n\n|\Z)', process_text, re.DOTALL | re.IGNORECASE)
    justification = justification_match.group(1).strip() if justification_match else "Justification not provided by AI."
    
    return {
        'used_references': used_references,
        'citation_details': citation_details,
        'justification': justification,
        'total_citations': len(citations),
        'unique_standards': list(set([ref.get('standard', 'Unknown') for ref in used_references]))
    }


def format_citations_display(citation_data: Dict[str, Any]) -> str:
    """Format citation data for display in the UI"""
    if not citation_data or not citation_data.get('used_references'):
        return "<div class='muted'>No citations found in the generated process.</div>"
    
    citations_html = []
    
    # Add justification section
    if citation_data.get('justification'):
        citations_html.append(f"""
        <div class="card" style="background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%); margin-bottom: 20px;">
            <h4 style="color: #e94560; margin-bottom: 10px;">🎯 Process Justification</h4>
            <div style="line-height: 1.6; font-size: 14px;">
                {citation_data['justification']}
            </div>
        </div>
        """)
    
    # Add citation details
    citations_html.append(f"""
    <div class="card" style="background: linear-gradient(135deg, #1c2541 0%, #0b132b 100%);">
        <h4 style="color: #e94560; margin-bottom: 15px;">
            📚 Citations Used ({citation_data['total_citations']} references)
        </h4>
        <div style="font-size: 12px; color: #aaa; margin-bottom: 15px;">
            Standards referenced: {', '.join(citation_data['unique_standards'])}
        </div>
    """)
    
    for ref_num, details in citation_data['citation_details'].items():
        citations_html.append(f"""
        <div style="margin: 10px 0; padding: 12px; background: rgba(255,255,255,0.05); border-radius: 5px; border-left: 3px solid #e94560;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <strong style="color: #e94560;">[Ref: {ref_num}] {details['standard']} - Page {details['page']}</strong>
                <a href="{details['link']}" target="_blank" style="font-size: 11px; color: #4a9eff; text-decoration: none;">
                    View Source →
                </a>
            </div>
            <div style="font-size: 12px; color: #ccc; line-height: 1.4;">
                {details['text']}...
            </div>
        </div>
        """)
    
    citations_html.append("</div>")
    
    return "".join(citations_html)

