Backend: API + App Setup

Endpoints
1) GET /api/process-by-id
   - Purpose: Return saved process by 5‑digit code from filesystem, with optional references for embedding scenarios.
   - Source: app/routers/api.py

Code (minimal extract)
```python
@router.get('/process-by-id')
def process_by_id(code: str = Query(..., description='5-digit process code, e.g., 11111')) -> Dict[str, Any]:
    code_str = str(code).strip()
    if not (len(code_str) == 5 and code_str.isdigit()):
        return { 'error': 'Invalid code format. Expected 5 digits like 11111.' }

    base = Path(__file__).resolve().parents[2]  # project root
    no_data_file = base / 'no_data' / 'no_embedding.txt'
    resp_dir = base / 'information' / 'response'
    resp_emb_dir = base / 'information' / 'response_with_embeddings'

    try:
        in_no_embedding = False
        if no_data_file.exists():
            txt = no_data_file.read_text(encoding='utf-8', errors='ignore')
            in_no_embedding = f"[{code_str}]" in txt

        if in_no_embedding:
            target = resp_dir / f"{code_str}.txt"
            if not target.exists():
                return { 'error': f'Listed in no_embedding but missing file: {target.name}' }
            content = target.read_text(encoding='utf-8', errors='ignore')
            return { 'code': code_str, 'source': 'response', 'path': str(target), 'text': content }

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
        return { 'code': code_str, 'source': 'response_with_embeddings', 'path': str(target_txt), 'text': content, 'references': references }
    except Exception as e:
        return { 'error': str(e) }
```

App Setup
- Purpose: Ensure static/templates mount, CORS, and auto-create information folders.
- Source: app/main.py

Code (relevant extract)
```python
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure information subfolders exist for file-based process fetching
INFO_DIR = Path(__file__).resolve().parents[1] / 'information'
try:
    (INFO_DIR / 'response').mkdir(parents=True, exist_ok=True)
    (INFO_DIR / 'response_with_embeddings').mkdir(parents=True, exist_ok=True)
except Exception:
    pass
```

Filesystem Layout
```text
information/
  response/
    24141.txt
    ...
  response_with_embeddings/
    11111.txt
    11111_references.json
    11112.txt
    11112_references.json
```

Returned JSON shape
```json
{
  "code": "11111",
  "source": "response_with_embeddings",
  "path": "E:/.../information/response_with_embeddings/11111.txt",
  "text": "... file content ...",
  "references": { "scenario_index": "11111", "scenario_info": { ... }, "references": [ { "standard": "PMBOK", "page": 24, "score": 0.61, "link": "/pdf/PMBOK#page=24", "text": "..." } ] }
}
```


