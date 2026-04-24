import os
from typing import List, Dict, Any

from fastapi import HTTPException

try:
    from transformers import pipeline
except Exception:
    pipeline = None


def _get_summarization_model():
    """Get a local summarization model using transformers."""
    if pipeline is None:
        raise HTTPException(status_code=500, detail="transformers library is not installed")
    
    # Use a lightweight summarization model
    try:
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn", device=-1)  # CPU
        return summarizer
    except Exception as e:
        # Fallback to a smaller model if the large one fails
        try:
            summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", device=-1)
            return summarizer
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"Failed to load summarization model: {e2}")


def build_book_context(snippets: List[Dict[str, Any]], max_chars: int = 24000) -> str:
    parts: List[str] = []
    total = 0
    for s in snippets:
        prefix = f"[{s.get('standard','?')} p.{s.get('page','?')}] "
        text = (s.get("text") or "").strip()
        if not text:
            continue
        chunk = prefix + text
        if total + len(chunk) > max_chars:
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n\n".join(parts)


def summarize_book_from_snippets(standard: str, snippets: List[Dict[str, Any]], api_key: str | None = None) -> Dict[str, Any]:
    context = build_book_context(snippets)
    if not context:
        raise HTTPException(status_code=404, detail="No content available to summarize for the selected standard")

    model = _get_summarization_model()
    
    # Split context into chunks if too long (transformers models have token limits)
    max_length = 1024  # Conservative limit for most models
    if len(context) > max_length:
        # Split into chunks and summarize each, then combine
        chunks = [context[i:i+max_length] for i in range(0, len(context), max_length)]
        summaries = []
        
        for chunk in chunks[:3]:  # Limit to first 3 chunks to avoid too much processing
            try:
                result = model(chunk, max_length=150, min_length=50, do_sample=False)
                summaries.append(result[0]['summary_text'])
            except Exception as e:
                # If summarization fails, use first part of chunk
                summaries.append(chunk[:200] + "...")
        
        summary_text = " ".join(summaries)
    else:
        try:
            result = model(context, max_length=200, min_length=100, do_sample=False)
            summary_text = result[0]['summary_text']
        except Exception as e:
            # Fallback to simple text truncation
            summary_text = context[:500] + "..."

    return {
        "standard": standard,
        "summary": summary_text.strip(),
        "sources_count": len(snippets),
    }


# --- Process generation leveraging selected-book context ---
def generate_process_from_snippets(standard: str, snippets: List[Dict[str, Any]], project_type: str, project_size: str, industry: str) -> Dict[str, Any]:
    """Generate a tailored process using the selected book as contextual reference.

    Uses the same local transformers pipeline as summarization to draft a structured process outline.
    """
    context = build_book_context(snippets, max_chars=20000)
    if not context:
        raise HTTPException(status_code=404, detail="No content available to generate process for the selected standard")

    gen = _get_summarization_model()
    # Construct a prompt-like instruction by prepending guidance to the context
    instruction = (
        f"You are generating a process tailored for a {project_size} {project_type} project in the {industry} industry, "
        f"strictly referencing {standard}. Provide a concise, numbered outline with phases, key activities, and deliverables.\n\n"
    )
    prompt = instruction + context

    try:
        # Reuse summarization model to condense into an outline
        result = gen(prompt[:3000], max_length=220, min_length=120, do_sample=False)
        text = result[0]['summary_text']
    except Exception:
        text = (instruction + context[:700])[:1000]

    return {
        "standard": standard,
        "project_type": project_type,
        "project_size": project_size,
        "industry": industry,
        "generated_process": text.strip(),
        "sources_count": len(snippets),
    }

