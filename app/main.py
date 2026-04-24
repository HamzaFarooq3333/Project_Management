from fastapi import FastAPI, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path
from .routers import api

app = FastAPI(title="PM Standards Comparator")

# Include API router
app.include_router(api.router)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Allow same-origin/local development fetches without CORS issues
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
    # Non-fatal: the read endpoints will still work if folders are missing
    pass


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/graphs", response_class=HTMLResponse)
def graphs_page(request: Request):
    return templates.TemplateResponse("graphs.html", {"request": request})


@app.get("/health")
def health():
    return {"status": "ok"}


# Resolve project root and Books directory for serving PDFs
ROOT_DIR = Path(__file__).resolve().parents[1]
BOOKS_DIR = ROOT_DIR / 'Books'

STANDARD_TO_FILE = {
    'PMBOK': '02 Project Management - PMBOK.pptx.pdf',
    'PRINCE2': '03 Project Management - Prince2.pptx.pdf',
    'ISO21500': 'ISO-21500-2021.pdf',
    'ISO21502': 'ISO-21502-2020.pdf',
}


@app.get('/pdf/{standard}')
def serve_pdf(standard: str):
    key = standard.upper()
    if key not in STANDARD_TO_FILE:
        raise HTTPException(status_code=404, detail="Unknown standard")
    filename = STANDARD_TO_FILE[key]
    pdf_path = BOOKS_DIR / filename

    # Vercel-friendly option: host PDFs elsewhere (S3/GDrive/etc.) and redirect.
    # This avoids Vercel deployment size limits for large PDFs.
    pdf_base_url = (os.getenv("PDF_BASE_URL") or "").strip().rstrip("/")
    if pdf_base_url:
        return RedirectResponse(url=f"{pdf_base_url}/{filename}")
    if not pdf_path.exists():
        # Try to find a matching file by heuristic to handle naming differences
        candidates = list(BOOKS_DIR.glob('*.pdf'))
        def matches(name: str, key: str) -> bool:
            n = name.lower()
            k = key.lower()
            if k == 'pmbok':
                return 'pmbok' in n
            if k == 'prince2':
                return 'prince' in n
            if k == 'iso21500':
                return '21500' in n
            if k == 'iso21502':
                return '21502' in n
            return k in n
        for f in candidates:
            if matches(f.name, key):
                pdf_path = f
                break
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(str(pdf_path), media_type='application/pdf')


@app.get('/favicon.ico')
def favicon():
    # Avoid noisy 404 in dev; return empty response
    return HTMLResponse(status_code=204)


@app.get("/view", response_class=HTMLResponse)
def view_chunk(request: Request, standard: str, page: int, text: str = "", from_dot: str = ""):
    key = standard.upper()
    if key not in STANDARD_TO_FILE:
        raise HTTPException(status_code=404, detail="Unknown standard")
    
    # Prefer HTML if available for inline anchors; else PDF page-level
    html_path = BOOKS_DIR / f"{key}.html"
    if html_path.exists():
        # If a search text is provided, use a simple hash anchor with the first words
        anchor = ''
        if text:
            from urllib.parse import quote
            terms = "-".join(text.split()[:6])
            anchor = f"#{quote(terms)}"
        pdf_url = f"/static/{html_path.name}{anchor}"
    else:
        # Build PDF URL with enhanced highlighting for dot clicks
        pdf_url = f"/pdf/{key}#page={page}"
    
    if text and from_dot == "true":
        # Enhanced highlighting for dot clicks
        from urllib.parse import quote
        # Use a shorter, more focused search term for better highlighting
        search_terms = text.split()[:5]  # Take first 5 words for better matching
        search_query = " ".join(search_terms)
        q = quote(search_query)
        pdf_url = f"/pdf/{key}#page={page}&search={q}&highlight=true"
    elif text and not html_path.exists():
        # Regular search without special highlighting
        from urllib.parse import quote
        q = quote(text[:200])
        pdf_url = f"/pdf/{key}#page={page}&search={q}"
    
    return templates.TemplateResponse("view.html", {
        "request": request, 
        "pdf_url": pdf_url, 
        "standard": key, 
        "page": page, 
        "text": text,
        "from_dot": from_dot == "true"
    })


