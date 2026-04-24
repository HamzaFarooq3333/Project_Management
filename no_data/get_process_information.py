import os
import re
import time
import argparse
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import json
from datetime import datetime
import sys

try:
    import google.generativeai as genai
except ImportError:
    genai = None


# SECURE: API key must be set via GEMINI_API_KEY environment variable
# Never hardcode API keys in source code!

# Local override (user-requested):
# This constant is used only if no key is supplied via --api-key, env, or key files.
# WARNING: Hardcoding API keys is insecure. Use only in local/dev.
HARDCODED_GEMINI_API_KEY = "AIzaSyA1zokA7ezjlUeS23s8_SuDrvquTj85VTA"


SCENARIO_LINE_RE = re.compile(
    r"^\[(\d{5})\]\s+(.+?)\s*\|\s*(.+?)\s*\|\s*(Small \(< 6 months\)|Medium \(6-18 months\)|Large \(> 18 months\))\s*\|\s*(Information Technology|Construction|Healthcare|Finance|Education)\s*\|\s*(PMBOK|PRINCE2|ISO Standards)"
)


TEMPLATE = (
    "🤖 AI-Generated Process Recommendation\n"
    "Powered by Google Gemini Pro | Based on PM standards and best practices.\n\n"
    "**Process Summary**\n"
    "{process_summary}\n\n"
    "**Phases and Activities**\n"
    "1. Initiation — Confirm business needs and obtain approval.\n"
    "2. Planning — Define architecture, timeline, and compliance scope.\n"
    "3. Execution — Configure software modules and test integration.\n"
    "4. Monitoring — Track progress and validate quality assurance.\n"
    "5. Closure — Deliver documentation and user training.\n\n"
    "**Roles**\n"
    "- Project Manager\n"
    "- Technical Lead\n"
    "- QA Engineer\n"
    "- Domain Stakeholder ({industry})\n"
    "- Sponsor\n\n"
    "**RACI Matrix**\n"
    "| Activity | Project Manager | Technical Lead | QA Engineer | Domain Stakeholder | Sponsor |\n"
    "|-----------|-----------------|----------------|--------------|-------------------|----------|\n"
    "| Planning  | A | R | C | I | I |\n"
    "| Execution | R | A | C | I | I |\n"
    "| Monitoring | A | R | C | C | I |\n\n"
    "**Decision Gates**\n"
    "- Gate 1: Project Charter Approval\n"
    "- Gate 2: Configuration/Build Completion Review\n"
    "- Gate 3: Final Validation & Go-Live Approval\n\n"
    "**Embeddings & Citations**\n"
    "- Related embeddings: ❌ None found\n"
    "- Citations: ❌ No citations found\n\n"
    "**Disclaimer**\n"
    "This is an AI-generated recommendation produced using Gemini 1.5 Pro.\n"
    "Use it for guidance and validation only.\n"
)


def parse_scenarios(text: str) -> List[Tuple[str, str, str, str, str, str]]:
    results: List[Tuple[str, str, str, str, str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or not line.startswith("["):
            continue
        m = SCENARIO_LINE_RE.match(line)
        if not m:
            continue
        idx, project_label, project_type, size, industry, methodology = m.groups()
        results.append((idx, project_label, project_type, size, industry, methodology))
    return results


def build_process_summary(project_label: str, project_type: str, size: str, industry: str, methodology: str) -> str:
    summarized_size = {
        "Small (< 6 months)": "small-scale",
        "Medium (6-18 months)": "medium-scale",
        "Large (> 18 months)": "large-scale",
    }.get(size, size)

    manual_hint = "Manual Configuration" in project_label

    parts = [
        f"A {summarized_size.lower()} {industry.lower()} {project_type.lower()} project",
    ]
    if manual_hint:
        parts.append("involving manual configuration")
    if methodology and methodology != "Any (Recommended)":
        parts.append(f"aligned with {methodology}")
    parts.append(f"expected to complete in {size.lower()}.")

    return " ".join(parts).replace("  ", " ").strip()


def make_prompt(record: Tuple[str, str, str, str, str, str]) -> str:
    _idx, project_label, project_type, size, industry, methodology = record
    summary = build_process_summary(project_label, project_type, size, industry, methodology)
    return TEMPLATE.format(process_summary=summary, industry=industry)


def ensure_dir(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)


def test_model_responsive(model_name: str) -> bool:
    try:
        m = genai.GenerativeModel(model_name)
        r = m.generate_content("ping")
        _ = getattr(r, "text", "")
        return True
    except Exception:
        return False


def choose_next_model(models_state: List[Dict[str, object]]) -> Optional[Dict[str, object]]:
    for m in models_state:
        if m["responsive"] and m["remaining"] > 0:
            return m
    return None


def _today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _load_env_from_dotenv() -> None:
    """Load environment variables from a .env file in project root if present.

    We avoid a dependency on python-dotenv by parsing a simple KEY=VALUE format.
    Values surrounded with single/double quotes will be unquoted. Existing env
    variables are not overwritten.
    """
    try:
        root = Path(__file__).parents[1]
        dotenv_path = root / ".env"
        if not dotenv_path.exists():
            return
        text = dotenv_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        # Best-effort; silently ignore malformed .env
        pass


def _load_api_key_from_files() -> Optional[str]:
    """Try common locations for an API key file and return the key if found.

    Search order (first hit wins):
    - <project_root>/secrets/gemini_api_key.txt
    - <project_root>/GEMINI_API_KEY.txt
    - <project_root>/.secrets/gemini_api_key
    - current working dir's .env (GEMINI_API_KEY=...)
    - <project_root>/no_data/.env (GEMINI_API_KEY=...)
    """
    root = Path(__file__).parents[1]
    candidates: List[Path] = [
        root / "secrets" / "gemini_api_key.txt",
        root / "GEMINI_API_KEY.txt",
        root / ".secrets" / "gemini_api_key",
    ]

    # Plain text files: first non-empty line is the key
    for p in candidates:
        try:
            if p.exists():
                line = p.read_text(encoding="utf-8").strip().splitlines()[0].strip().strip('"').strip("'")
                if line:
                    return line
        except Exception:
            continue

    # Fallback: parse .env in CWD and no_data/.env
    def parse_env(path: Path) -> Optional[str]:
        try:
            if not path.exists():
                return None
            text = path.read_text(encoding="utf-8")
            for ln in text.splitlines():
                ln = ln.strip()
                if ln.startswith("GEMINI_API_KEY="):
                    val = ln.split("=", 1)[1].strip().strip('"').strip("'")
                    return val or None
        except Exception:
            return None
        return None

    key = parse_env(Path.cwd() / ".env")
    if key:
        return key
    key = parse_env(root / "no_data" / ".env")
    return key


def _dpapi_protect(data: bytes) -> Optional[bytes]:
    """Protect data using Windows DPAPI (current user). Returns ciphertext or None on failure."""
    try:
        import ctypes
        from ctypes import wintypes as wt

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wt.DWORD),
                        ("pbData", ctypes.c_void_p)]

        CryptProtectData = ctypes.windll.crypt32.CryptProtectData
        CryptProtectData.argtypes = [ctypes.POINTER(DATA_BLOB), wt.LPWSTR, ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(DATA_BLOB)]
        CryptProtectData.restype = wt.BOOL
        LocalFree = ctypes.windll.kernel32.LocalFree

        in_blob = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.c_void_p))
        out_blob = DATA_BLOB()
        if not CryptProtectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
            return None
        try:
            buf = (ctypes.c_char * out_blob.cbData).from_address(out_blob.pbData)
            return bytes(buf)
        finally:
            LocalFree(out_blob.pbData)
    except Exception:
        return None


def _dpapi_unprotect(ciphertext: bytes) -> Optional[bytes]:
    """Unprotect data using Windows DPAPI (current user). Returns plaintext or None on failure."""
    try:
        import ctypes
        from ctypes import wintypes as wt

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wt.DWORD),
                        ("pbData", ctypes.c_void_p)]

        CryptUnprotectData = ctypes.windll.crypt32.CryptUnprotectData
        CryptUnprotectData.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.POINTER(wt.LPWSTR), ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(DATA_BLOB)]
        CryptUnprotectData.restype = wt.BOOL
        LocalFree = ctypes.windll.kernel32.LocalFree

        in_buf = ctypes.create_string_buffer(ciphertext)
        in_blob = DATA_BLOB(len(ciphertext), ctypes.cast(in_buf, ctypes.c_void_p))
        out_blob = DATA_BLOB()
        if not CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
            return None
        try:
            buf = (ctypes.c_char * out_blob.cbData).from_address(out_blob.pbData)
            return bytes(buf)
        finally:
            LocalFree(out_blob.pbData)
    except Exception:
        return None


def _save_api_key_dpapi(key: str) -> Optional[Path]:
    root = Path(__file__).parents[1]
    target = root / "secrets" / "gemini_api_key.dpapi"
    enc = _dpapi_protect(key.encode("utf-8"))
    if not enc:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(enc)
    return target


def _load_quota_usage(quota_file: Path) -> Dict[str, Dict[str, int]]:
    if not quota_file.exists():
        return {"date": _today_str(), "used": {}}
    try:
        data = json.loads(quota_file.read_text(encoding="utf-8"))
        if data.get("date") != _today_str():
            return {"date": _today_str(), "used": {}}
        return data
    except Exception:
        return {"date": _today_str(), "used": {}}


def _save_quota_usage(quota_file: Path, usage: Dict[str, Dict[str, int]]) -> None:
    quota_file.parent.mkdir(parents=True, exist_ok=True)
    quota_file.write_text(json.dumps(usage, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate AI process recommendations for all scenarios in no_embedding.txt and with_embeddings.txt and save them.")
    parser.add_argument("--no-embedding-file", default=str(Path(__file__).parent / "no_embedding.txt"))
    parser.add_argument("--with-embedding-file", default=str(Path(__file__).parent / "with_embeddings.txt"))
    parser.add_argument("--no-embedding-output-dir", default=str(Path(__file__).parents[1] / "information" / "response"))
    parser.add_argument("--with-embedding-output-dir", default=str(Path(__file__).parents[1] / "information" / "response_with_embeddings"))
    parser.add_argument("--model", default="models/gemini-2.0-flash-lite")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--start-from", type=int, default=0)
    parser.add_argument("--max", type=int, default=None)
    parser.add_argument("--start-model", choices=[
        "models/gemini-2.0-flash-lite",
        "models/gemini-2.0-flash",
        "models/gemini-2.5-flash",
        "models/gemini-2.5-flash-lite",
        "models/gemini-1.5-flash",
    ], default=None, help="Preferred model to start with. If omitted, defaults to the first responsive model. Auto-switches when exhausted.")
    parser.add_argument("--api-key", default=None, help="Gemini API key (overrides environment/.env if provided)")
    parser.add_argument("--save-api-key", default=None, help="Persist the provided API key securely (Windows DPAPI) and exit")
    args = parser.parse_args()

    # Best-effort: load .env if present (does not overwrite existing env)
    _load_env_from_dotenv()

    # Save key securely if requested then exit
    if args.save_api_key:
        saved = _save_api_key_dpapi(args.save_api_key)
        if saved:
            print(f"Saved API key securely to: {saved}")
            return
        else:
            raise SystemExit("Failed to save API key securely (DPAPI).")

    api_key = (
        args.api_key
        or os.environ.get("GEMINI_API_KEY")
        or _load_api_key_from_files()
        or HARDCODED_GEMINI_API_KEY
    )
    if not api_key:
        raise SystemExit(
            "ERROR: GEMINI_API_KEY environment variable is required but not set.\n"
            "Please set your Gemini API key securely:\n"
            "1. Create a .env file in the project root\n"
            "2. Add: GEMINI_API_KEY=your_actual_api_key_here\n"
            "3. Or set it in your system environment variables\n"
            "4. Never hardcode API keys in source code!"
        )
    # Ensure env var so downstream libraries can read it uniformly
    os.environ.setdefault("GEMINI_API_KEY", api_key)
    if genai is None:
        raise SystemExit("google-generativeai is not installed. Please install requirements.")

    # Read both files and combine scenarios
    all_recs = []
    scenario_sources = []

    # Read no-embedding scenarios
    if Path(args.no_embedding_file).exists():
        with open(args.no_embedding_file, "r", encoding="utf-8") as f:
            content = f.read()
        no_emb_recs = parse_scenarios(content)
        all_recs.extend(no_emb_recs)
        scenario_sources.extend([("no_embedding", args.no_embedding_output_dir)] * len(no_emb_recs))

    # Read with-embedding scenarios
    if Path(args.with_embedding_file).exists():
        with open(args.with_embedding_file, "r", encoding="utf-8") as f:
            content = f.read()
        with_emb_recs = parse_scenarios(content)
        all_recs.extend(with_emb_recs)
        scenario_sources.extend([("with_embedding", args.with_embedding_output_dir)] * len(with_emb_recs))

    if not all_recs:
        print("No scenarios found in either file. Exiting.")
        return

    total = len(all_recs)
    if args.max is not None:
        all_recs = all_recs[:args.max]
        scenario_sources = scenario_sources[:args.max]
    recs = all_recs[args.start_from:]
    sources = scenario_sources[args.start_from:]
    to_process = len(recs)

    # Create both output directories
    no_emb_out_dir = Path(args.no_embedding_output_dir)
    with_emb_out_dir = Path(args.with_embedding_output_dir)
    ensure_dir(no_emb_out_dir)
    ensure_dir(with_emb_out_dir)

    print(f"Total scenarios across both files: {total}")
    print(f"Scenarios to process now: {to_process}")
    print(f"No-embedding output dir: {no_emb_out_dir}")
    print(f"With-embedding output dir: {with_emb_out_dir}")
    print("-" * 60)

    genai.configure(api_key=api_key)

    # Prepare model rotation with daily quotas - Top 5 models by rate limits (descending order)
    models_state: List[Dict[str, object]] = [
        # Highest rate limits first - arranged by RPM capacity
        {"name": "models/gemini-2.0-flash-lite",  "limit": 1500,  "remaining": 1500,  "responsive": False, "rpm": 30,  "min_interval": 2.0,  "last_ts": 0.0},  # 1500 RPM - Highest
        {"name": "models/gemini-2.0-flash",       "limit": 1500,  "remaining": 1500,  "responsive": False, "rpm": 30,  "min_interval": 2.0,  "last_ts": 0.0},  # 1500 RPM - High
        {"name": "models/gemini-2.5-flash",       "limit": 1500,  "remaining": 1500,  "responsive": False, "rpm": 25,  "min_interval": 2.4,  "last_ts": 0.0},  # 1500 RPM - High
        {"name": "models/gemini-2.5-flash-lite",  "limit": 1500,  "remaining": 1500,  "responsive": False, "rpm": 25,  "min_interval": 2.4,  "last_ts": 0.0},  # 1500 RPM - High
        {"name": "models/gemini-1.5-flash",       "limit": 1000,  "remaining": 1000,  "responsive": False, "rpm": 20,  "min_interval": 3.0,  "last_ts": 0.0},  # 1000 RPM - Good
    ]

    # Load persisted quota usage and adjust remaining - use the first output dir for quota file
    quota_file = no_emb_out_dir / "quota_usage.json"
    quota_usage = _load_quota_usage(quota_file)
    used_map: Dict[str, int] = quota_usage.get("used", {})  # type: ignore[assignment]
    for m in models_state:
        name = str(m["name"])  # type: ignore[index]
        used = int(used_map.get(name, 0))
        m["remaining"] = max(0, int(m["limit"]) - used)  # type: ignore[index]

    # Health check models
    for m in models_state:
        m["responsive"] = test_model_responsive(m["name"])  # type: ignore[index]

    # Print model statuses and limits
    print("Model availability and daily quotas (remaining today):")
    for m in models_state:
        print(f"- {m['name']}: responsive={m['responsive']} | remaining={m['remaining']} of {m['limit']} | rpm={m['rpm']}")
    print("Note: If the selected model reaches its daily limit, the script will automatically switch to the next available model.")

    # Pick starting model
    current = None
    if args.start_model:
        # respect user preference if responsive and has remaining
        for m in models_state:
            if m["name"] == args.start_model:
                current = m if (m["responsive"] and m["remaining"] > 0) else None
                break
        if current is None:
            print(f"Requested start model {args.start_model} is not available or has no remaining calls; falling back to first responsive model.")
    else:
        # Auto-select first responsive model (non-interactive)
        print("Running in non-interactive mode - selecting first available model...")
        current = choose_next_model(models_state)
    if not current:
        print("No responsive Gemini models available or all daily limits are zero. Aborting.")
        return
    model = genai.GenerativeModel(current["name"])  # type: ignore[index]

    processed = 0
    errors = 0
    start_time = time.time()

    for i, (rec, source_info) in enumerate(zip(recs, sources), start=args.start_from + 1):
        idx, project_label, project_type, size, industry, methodology = rec
        scenario_type, output_dir_path = source_info
        out_dir = Path(output_dir_path)
        out_file = out_dir / f"{idx}.txt"

        # IMMEDIATE SKIP CHECK - No setup overhead for existing files
        if out_file.exists():
            processed += 1
            remaining = to_process - processed
            # Minimal output for fast skipping
            print(f"[{idx}] SKIP (exists) - {processed}/{to_process} done")
            continue

        print(f"Processing {i}/{total} -> [{idx}] {project_label[:60]} ({scenario_type})...")

        # For with-embedding scenarios, we need to include embedding processing
        if scenario_type == "with_embedding":
            # Import required modules for embedding processing
            try:
                # Add paths for imports
                base_dir = Path(__file__).parent.parent
                parent_path = str(base_dir)
                if parent_path not in sys.path:
                    sys.path.insert(0, parent_path)

                # Import search engine
                from app.services.search import get_engine as _get_engine
                engine = _get_engine()

                # Build topic for embedding search
                topic = f"{size} {project_type} {industry} project management process lifecycle planning stakeholder risk quality scope schedule budget"

                # Retrieve embeddings
                evidence_snippets = engine.query(topic, k=20)

                if not evidence_snippets:
                    print(f"  [SKIP] No embeddings found for scenario {idx}")
                    processed += 1
                    continue

                print(f"  [EMBEDDINGS] Found {len(evidence_snippets)} embedding snippets")

                # Build evidence text and references for prompt
                evidence_text = ""
                references_list = []

                for j, snippet in enumerate(evidence_snippets[:15], 1):
                    text = snippet.get('text', '')[:500]
                    standard = snippet.get('standard', 'Unknown')
                    page = snippet.get('page', 'N/A')
                    score = snippet.get('score', 0.0)
                    link = snippet.get('link', '')

                    # Store reference info
                    references_list.append({
                        'ref_num': j,
                        'standard': standard,
                        'page': page,
                        'score': score,
                        'link': link,
                        'text': text
                    })

                    # Add to evidence text
                    evidence_text += f"\n[Ref {j}] {standard}, Page {page} (Similarity: {score:.3f}):\n{text}\n"

                # Build enhanced prompt for embeddings
                prompt_text = f"""You are a senior project management expert. Generate a comprehensive process recommendation based on the following scenario and PM standards evidence.

**Scenario Information:**
- Project Type: {project_type}
- Project Size: {size}
- Industry: {industry}
- Methodology: {methodology}

**Process Summary:** {build_process_summary(project_label, project_type, size, industry, methodology)}

**PM Standards Evidence (from embeddings):**
{evidence_text}

**Available References:**
{chr(10).join([f"- {r['standard']}, Page {r['page']} (Similarity: {r['score']:.3f})" for r in references_list])}

**Instructions:**
Generate a detailed, professional process recommendation that includes:
1. **Process Summary** - A comprehensive overview that references the evidence
2. **Phases and Activities** - Detailed phases with Roman numeral numbering. When referencing standards, cite them (e.g., "[Ref 1]", "[Ref 3]").
3. **Roles** - Key project roles
4. **RACI Matrix** - Properly formatted table with phase headers and RACI codes (R, A, C, I). Include citations in the table where relevant.
5. **Decision Gates** - Important decision points with citations
6. **Embeddings & Citations Section** - At the end, include a section titled "Note" that lists ALL references used:
   - For each reference you used, list: "Ref X: {standard}, Page {page}"
   - Include the similarity score if relevant

**Important:**
- Cite references throughout your response using [Ref X] format
- Use the references to ground your recommendations in actual PM standards
- Include ALL references you use in the final citations section
- Be specific about which reference supports which recommendation

Format everything in clean Markdown. Use ### for main headings, #### for subheadings.
For lists, use Roman numerals (i, ii, iii, etc.) instead of bullets.
Include a separator line (-----) after major sections.
Make sure the RACI table is properly aligned and readable.

Generate the response now:"""

                # Save references to JSON file
                references_json_file = out_dir / f"{idx}_references.json"
                references_data = {
                    'scenario_index': idx,
                    'scenario_info': {
                        'project_label': project_label,
                        'project_type': project_type,
                        'project_size': size,
                        'industry': industry,
                        'methodology': methodology
                    },
                    'embedding_info': {
                        'total_embeddings': len(evidence_snippets),
                        'embeddings_used': len(references_list),
                        'standards_used': list(set([r['standard'] for r in references_list]))
                    },
                    'references': references_list,
                    'generated_at': datetime.now().isoformat()
                }

                with open(references_json_file, 'w', encoding='utf-8') as f:
                    json.dump(references_data, f, indent=2, ensure_ascii=False)

                print(f"  [REFERENCES] Saved {len(references_list)} references to {references_json_file.name}")

            except Exception as embed_error:
                print(f"  [EMBEDDING ERROR] Failed to process embeddings for scenario {idx}: {embed_error}")
                # Fall back to basic processing without embeddings
                prompt_text = make_prompt(rec)
        else:
            # For no-embedding scenarios, use basic prompt
            prompt_text = make_prompt(rec)

        # Attempt across available models if we hit rate limits
        attempt_success = False
        attempts = 0
        while attempts < len(models_state):
            try:
                # Respect RPM/min interval for the current model
                now = time.time()
                min_interval = float(current.get("min_interval", 0.0))
                last_ts = float(current.get("last_ts", 0.0))
                wait_for = (last_ts + min_interval) - now
                if wait_for > 0:
                    time.sleep(wait_for)

                prompt = prompt_text
                resp = model.generate_content(prompt)
                text = resp.text if hasattr(resp, "text") else str(resp)

                # For embedding scenarios, add citations to the response
                if scenario_type == "with_embedding" and 'references_list' in locals():
                    # Ensure citations section is present
                    if "### Note" not in text and "## Note" not in text:
                        # Add comprehensive citations section
                        citations_text = "\n\n-----\n\n### Note\n\n"
                        citations_text += "**Embedding References Used:**\n\n"

                        # Group references by standard
                        by_standard = {}
                        for ref in references_list:
                            std = ref.get('standard', 'Unknown')
                            if std not in by_standard:
                                by_standard[std] = []
                            by_standard[std].append(ref)

                        # List references grouped by standard
                        for standard, refs in sorted(by_standard.items()):
                            citations_text += f"**{standard}:**\n"
                            for ref in sorted(refs, key=lambda x: x.get('page', 'N/A')):
                                page = ref.get('page', 'N/A')
                                score = ref.get('score', 0.0)
                                link = ref.get('link', '')
                                link_text = f" ({link})" if link else ""
                                citations_text += f"- Ref {ref.get('ref_num', '?')}: Page {page}, Similarity: {score:.3f}{link_text}\n"
                            citations_text += "\n"

                        citations_text += f"**Total Embeddings Used:** {len(references_list)}\n\n"
                        citations_text += "All references cited in the response are from the embedded PM standards evidence found in the FAISS index.\n"
                        citations_text += "No external citations available beyond the embedded references listed above."

                        text = text.strip() + citations_text

                # Save response with appropriate header
                out_file = out_dir / f"{idx}.txt"
                with open(out_file, "w", encoding="utf-8") as f:
                    header = f"Scenario: [{idx}] {project_label} | {project_type} | {size} | {industry} | {methodology}\n"
                    if scenario_type == "with_embedding":
                        header += f"Generated with embeddings - {len(references_list) if 'references_list' in locals() else 0} evidence snippets sent to GPT model\n"
                        header += f"Embedding Sources: {', '.join(set([r.get('standard', 'Unknown') for r in references_list]) if 'references_list' in locals() else [])}\n\n"

                    f.write(header)
                    f.write("=" * 80 + "\n\n")
                    f.write(text.strip())

                    # Append references summary at the end for embedding scenarios
                    if scenario_type == "with_embedding" and 'references_list' in locals():
                        f.write("\n\n-----\n\n")
                        f.write(f"NOTE: Detailed book references with full metadata have been saved to {idx}_references.json\n")
                        f.write("This JSON file contains complete information about all books, pages, and embeddings used.\n\n")
                        f.write("EMBEDDING REFERENCES (Clickable Links):\n")
                        for ref in references_list:
                            ref_num = ref.get('ref_num', '?')
                            standard = ref.get('standard', 'Unknown')
                            page = ref.get('page', 'N/A')
                            score = ref.get('score', 0.0)
                            pdf_link = f"/pdf/{standard.replace(' ', '_')}#page={page}"
                            f.write(f"• [Ref {ref_num}] {standard} - Page {page} (Similarity: {score:.3f}) → {pdf_link}\n")
                processed += 1
                # decrement remaining calls and update last timestamp for current model
                current["remaining"] = max(0, int(current["remaining"]) - 1)  # type: ignore[index]
                current["last_ts"] = time.time()  # type: ignore[index]
                # persist quota usage
                used_map[name if (name := str(current['name'])) else str(current['name'])] = int(used_map.get(str(current['name']), 0)) + 1
                quota_usage["date"] = _today_str()
                quota_usage["used"] = used_map
                _save_quota_usage(quota_file, quota_usage)
                print(f"  [OK] Saved: {out_file} using {current['name']}")
                attempt_success = True
                break
            except Exception as e:
                msg = str(e)
                # Handle quota exceeded 429 -> switch model
                if "429" in msg or "quota" in msg.lower():
                    print(f"  [RATE-LIMIT] {current['name']} appears exhausted; switching model...")
                    current["remaining"] = 0  # type: ignore[index]
                    # pick next model
                    current = choose_next_model(models_state)
                    if not current:
                        # No models available, stop process gracefully
                        print("Daily API limits reached for all configured models. Limit exceeded, please come tomorrow after quota refresh.")
                        print()
                        # finalize timings before return
                        end_time = time.time()
                        total_seconds = max(0, end_time - start_time)
                        minutes = int(total_seconds // 60)
                        seconds = int(total_seconds % 60)
                        avg_per = (total_seconds / processed) if processed else 0
                        avg_min = int(avg_per // 60)
                        avg_sec = int(avg_per % 60)
                        print("=" * 60)
                        print("COMPLETED (stopped due to daily API limits)")
                        print(f"Total scenarios in file: {total}")
                        print(f"Processed now: {processed} | Errors: {errors}")
                        print(f"Total time: {minutes}m {seconds}s")
                        print(f"Average per process: {avg_min}m {avg_sec}s")
                        print(f"Saved to: {out_dir}")
                        return
                    model = genai.GenerativeModel(current["name"])  # type: ignore[index]
                    attempts += 1
                    continue
                else:
                    # Other errors -> record and move on
                    errors += 1
                    err_file = out_dir / f"{idx}_ERROR.txt"
                    with open(err_file, "w", encoding="utf-8") as f:
                        f.write(f"ERROR generating scenario {idx}: {e}\n")
                    print(f"  [ERROR] {e}")
                    attempt_success = True  # treat as handled; don't retry across models
                    break

        if not attempt_success:
            # Shouldn't generally reach here; guard
            errors += 1

        remaining = to_process - processed
        print(f"  Progress: {processed}/{to_process} done, {remaining} remaining")
        if i < total:
            time.sleep(args.delay)
        print()

    end_time = time.time()
    total_seconds = max(0, end_time - start_time)
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    avg_per = (total_seconds / processed) if processed else 0
    avg_min = int(avg_per // 60)
    avg_sec = int(avg_per % 60)

    print("=" * 60)
    print("COMPLETED")
    print(f"Total scenarios across both files: {total}")
    print(f"Processed now: {processed} | Errors: {errors}")
    print(f"Total time: {minutes}m {seconds}s")
    print(f"Average per process: {avg_min}m {avg_sec}s")
    print(f"No-embedding responses saved to: {no_emb_out_dir}")
    print(f"With-embedding responses saved to: {with_emb_out_dir}")


if __name__ == "__main__":
    main()


