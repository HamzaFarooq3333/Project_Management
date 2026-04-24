# PM Standards Comparator

A comprehensive web application for comparing and analyzing Project Management standards including PMBOK 7th Edition, PRINCE2, and ISO 21500/21502.

## 🎯 Features

### Standards Repository & Search
- **Semantic Search**: AI-powered search across all PM standards
- **Multi-Standard Navigation**: Browse PMBOK, PRINCE2, ISO 21500, and ISO 21502
- **Deep Linking**: Direct links to specific sections in PDF documents
- **Bookmarking**: 📚 Save and organize important sections with full bookmark management
  - One-click bookmarking from search results
  - Persistent storage using localStorage
  - Filter bookmarks by standard
  - Export bookmarks to JSON
  - Visual indicators and notifications

### Comparison Engine
- **Topic-Based Comparison**: Compare how different standards handle the same topics
- **Side-by-Side Analysis**: View similarities, differences, and unique elements
- **Visual Analytics**: Interactive scatter plots and relationship maps
- **Evidence-Based Insights**: Detailed analysis with source references

### Process Generator (🤖 AI-Powered)
- **🤖 AI-Generated Recommendations**: Google Gemini AI creates detailed, tailored processes
- **Comprehensive Output**: 800-1200 word professional process guides with:
  - Executive Summary & Methodology Recommendations
  - Detailed Process Phases with timelines
  - Key Activities & Critical Deliverables
  - Roles & Responsibilities
  - Tailoring Guidance & Risk Considerations
  - Success Metrics & Standards Alignment
- **Evidence-Based**: References actual PM standards content
- **Customizable**: Tailored to project type, size, industry, and methodology preference

### Advanced Analytics
- **Similarity Analysis**: Identify common practices across standards
- **Difference Detection**: Highlight unique terminologies and methodologies
- **Coverage Analysis**: Understand what each standard covers uniquely
- **Process Mapping**: Visual representation of standard relationships

## 🧠 Deep Technical Overview (Architecture & Flow)

### Backend Architecture (FastAPI)
- **Entrypoints**
  - `run.py`: Uvicorn launcher that serves the FastAPI app from `app.main:app` (with reload in dev).
  - `start_app.py` / `start_with_check.py`: Convenience scripts that (optionally) check AI model availability and then start the server.
- **App setup (`app/main.py`)**
  - Creates the FastAPI app, mounts `/static`, and configures Jinja2 templates for `index.html`, `graphs.html`, and `view.html`.
  - Adds permissive CORS so the frontend JS can call the API without issues.
  - Ensures the `information/response` and `information/response_with_embeddings` folders exist at startup.
  - Serves PDFs from the `Books/` folder via `GET /pdf/{standard}` with smart filename heuristics, and exposes a full-screen viewer via `GET /view`.
- **API router (`app/routers/api.py`)**
  - `POST /api/answer-from-citations`: Given a question and citation snippets, calls `generate_answer_from_context` to answer strictly from those excerpts.
  - `POST /api/upload-pdfs`: Accepts one or more PDF files and saves them into `Books/`, enforcing `.pdf` extension and safe filenames.
  - `POST /api/run-add-book`: Orchestrator hook that runs `add_book.py` on the server and streams its stdout/stderr back as JSON.
  - `GET /api/search`: Semantic search across all standards using `SemanticSearch.get_engine()`, returning enriched results (bookmark IDs, navigation hints, relevance scores, page ranges).
  - `GET /api/compare`: High-level comparison that buckets search hits by standard (PMBOK, PRINCE2, ISO21500, ISO21502) and synthesizes similarities, differences, and unique points.
  - `GET /api/compare/detailed`: Calls `engine.compare_detailed` to return per-standard summaries plus similarity/difference pairs between standards.
  - `GET /api/analysis`: Runs the cross-book similarity algorithm (`analyze_all_books_auto`) to classify each chunk as **similar**, **dissimilar**, or **unique**, returning debug stats and per-book uniqueness metrics.
  - `GET /api/graphs`: Builds a 2D PCA projection of topic-relevant chunks from all books, annotated with similarity labels and links, for use in the dedicated graphs page.
  - `GET /api/process-recommendation`: Core **process generator** endpoint:
    - Queries the embedding index for project-specific evidence.
    - When `use_ai=true`, it calls the AI pipeline (`local_ai` + `ai_generator`) to generate a long-form, evidence-backed process (phases, activities, roles, RACI, decision gates, citations).
    - When `use_ai=false`, it falls back to a rich, template-based engine that still uses search results to ground recommendations.
  - `GET /api/summary`: Builds a comprehensive book summary for a selected standard:
    - With AI: uses `generate_summary` (AI-backed) on all snippets for that standard.
    - Fallback: uses `summarize_book_from_snippets` (local summarization templates/transformers).
  - `GET /api/export-pdf` & `POST /api/export-pdf`: Accept structured process data (including AI answer, roles, RACI, decision gates, and citations) and use `pdf_generator.generate_process_pdf` to return a professionally formatted PDF.
  - `GET /api/process-by-id`: Pure filesystem endpoint that, given a 5‑digit code:
    - Reads routing metadata from `no_data/no_embedding.txt` and `information/response[_with_embeddings]`.
    - Returns the saved process text, the physical path, and (if present) a parsed `{code}_references.json` structure.

### Core Services & Data Layer (`app/services`)
- **Semantic Search (`search.py`)**
  - Lazily loads `SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')` and a FAISS index from `data/faiss.index`.
  - Encodes queries, performs vector search, and reconstructs rich metadata (`standard`, `text`, `page`, `score`, PDF deep-link).
  - Implements:
    - `query(q, k, standard_filter)` for high-level search.
    - `compare_detailed(topic, k)` for cross-standard pairwise similarity/difference/unique snippets.
    - `analyze_two_books(...)` and `analyze_all_books_auto(...)` for 2D visualization and **unique points detection** (backed by the enhanced cross-book algorithm in `docs/UNIQUE_POINTS_ALGORITHM.md`).
    - `get_all_snippets_for_standard(standard)` to stream all chunks of a given book in page order for summarization.
- **External retrieval (`retrieval.py`)**
  - Adds web context by calling Wikipedia, OpenAlex, and arXiv (with caching) via `retrieve_external_context(topic)`, which the AI generator can enrich with external citations.
- **Summarization & local transformers (`summary.py`)**
  - Uses Hugging Face summarization pipelines (BART/distilBART) as a local CPU-based summarizer when AI is not available.
  - Builds book-level context from snippets and returns concise, multi-chunk summaries, splitting text as needed to respect model limits.
- **AI generation pipeline (`ai_generator.py` + `local_ai.py`)**
  - `ai_generator.py`:
    - Lazily loads a local GPT‑2 model (no external API key required) and handles safe tokenization, padding, CPU-only inference, and output post-processing.
    - `generate_process_recommendation_ai(...)`:
      - Builds a strict, citation-focused prompt grounded in selected-book evidence snippets.
      - Generates detailed, step-by-step processes (with `[Ref X]` markers).
      - Validates and normalizes steps, constructs extractive outlines when generation is weak, and extracts/structures citations with rich metadata and HTML snippets for the UI.
    - `generate_summary_ai(...)`: AI-based book summaries constrained to a small number of lines.
  - `local_ai.py`:
    - High-level façade used by the router:
      - Attempts to call GPT‑2 via `ai_generator` first.
      - If loading or generation fails, falls back to a sophisticated template engine that still uses evidence to build an executive summary, phases, activities, deliverables, tailoring guidance, roles, decision gates, KPIs, and methodology alignment.
    - Also exposes `generate_summary(...)` which can use Hugging Face Inference API or local transformers to create book summaries.
- **PDF export (`pdf_generator.py`)**
  - First part: a minimal helper that can assemble a basic process PDF with roles, RACI, decision gates, and citations.
  - Second part: a full `PDFGenerator` class that builds a multi-page, styled document with:
    - Title page (project metadata).
    - Process overview and AI answer sections.
    - Detailed process steps, citations, and justification pages.
  - Top-level `generate_process_pdf(process_data)` is what the API calls; it accepts rich structures (including `step_citations`, `roles`, `raci`, `decision_gates`) and returns raw PDF bytes.

### Ingestion & Indexing Pipeline (`ingest/` + `add_book.py` + `information/`)
- **Text extraction & indexing (`ingest/build_index_final.py`)**
  - Reads PM standard PDFs from `Books/` (or HTML/EPUB fallbacks) and:
    - Cleans text, removes boilerplate, and splits into overlapping, sentence-aware chunks.
    - Extracts rich per-chunk metadata (standard, viewer page, pdf page index, potential titles, word/sentence counts).
    - Uses **1‑based page numbers** that exactly match PDF viewers (validated by analysis scripts).
  - Encodes all chunks with SentenceTransformers, builds a FAISS inner-product index, and persists:
    - `data/faiss.index`: vector index.
    - `data/meta.pkl`: rich metadata per chunk.
    - `data/stats.pkl`: global and per-standard stats.
- **Page-number validation (`ingest/analyze_page_numbers.py`, `ingest/verify_page_numbers.py`)**
  - `analyze_page_numbers.py`: inspects PDFs for page-number patterns and emits `page_analysis_results.json` with recommendations for page mapping.
  - `verify_page_numbers.py`: uses the live search engine to verify that stored page numbers and generated `/pdf/...#page=N` links align with the viewer, failing fast if not.
- **End-to-end orchestrator (`add_book.py`)**
  - High-level script used both from CLI and via `POST /api/run-add-book`:
    1. Detects whether new PDFs have been added to `Books/` and (re)builds the index only when necessary (`ingest/build_index_final.py`).
    2. Reads expected 5‑digit process codes from `no_data/no_embedding.txt` and `no_data/with_embeddings.txt`.
    3. Ensures a corresponding `.txt` (and optional `*_references.json`) exists under:
       - `information/response/` (no embeddings).
       - `information/response_with_embeddings/` (with embeddings + references).
    4. For missing processes:
       - Tries to fetch them via `GET /api/process-by-id?code=XXXXX`.
       - If still missing, optionally uses **Gemini AI** to generate processes (with or without embeddings) and backfills both `.txt` and `_references.json`.
    5. Runs `convert/convert_timeouts.py` to normalize output formats.
    6. Computes consistency and coverage stats (missing/misplaced/extra codes, average lengths, etc.) and prints a human-readable summary.
- **Offline AI generation helpers**
  - `no_data/get_process_information.py`: batch-offline generator that reads scenario definitions, calls Gemini to generate rich Markdown processes, and writes them into `information/response[_with_embeddings]` with full embedding reference JSON.
  - `download_gen_model.py` and `check_model.py`: utilities to download the GPT‑2 model and validate its availability before running the app.

### Frontend Architecture (Templates + JS)
- **Main UI (`app/templates/index.html` + `app/static/styles.css` + `app/static/app.js`)**
  - Tabbed layout with:
    - **All Search**: Global semantic search over all standards, with result cards and inline bookmark buttons.
    - **Book Search**: Search restricted to a specific standard.
    - **Compare**: Topic-based comparisons plus detailed similarities/differences/unique view.
    - **Process Generator**: Scenario selector, project metadata form, AI-generated process, Fetch‑by‑Code integration, diagram viewer, and PDF export.
    - **Book Analysis**: Auto-run cross-book analysis with three interactive scatter plots (similar, dissimilar, unique) plus a dot preview panel.
    - **Summary**: One-click AI summary generator per standard with progress UI.
    - **Bookmarks**: Full bookmark management UI (stats, filtering, export, clear all).
  - Core JS building blocks (`app.js`):
    - `fetchJSON` / `fetchJSONWithTimeout`: unified HTTP helpers with origin-prefixing and hard timeouts.
    - **Search UIs**: wire buttons and inputs to `/api/search`, create cards with deep links and bookmark controls, and show errors inline.
    - **Comparison UIs**:
      - Quick compare: renders per-standard cards plus similarity/difference/unique insight lists from `/api/compare`.
      - Detailed compare: renders side-by-side excerpts and links from `/api/compare/detailed`.
    - **Book Analysis & Graphs**:
      - Progress bar + status messaging while `/api/analysis` runs.
      - Pure Canvas-based scatter plots with **click-to-open** and **hover** UX.
      - Enhanced scatter plot engine (`drawEnhancedScatter`) plus dot preview panel showing book, page, label, and snippet, with a "View in Book" button wired to `/view`.
    - **Process Generator workflow**:
      - Collects scenario/form inputs and calls `/api/process-recommendation`.
      - Renders either AI-generated content (formatted Markdown + evidence cards, structured traceability table, roles, RACI, decision gates, citations) or template-based content when AI is unavailable.
      - Maintains `currentProcessData`, which contains normalized process text, citations, evidence base, and raw AI response for downstream PDF export and diagram generation.
      - `deriveCodeFromForm()` builds a deterministic 5‑digit code from scenario, type, size, industry, and methodology; `fetchAndDisplayByCode()` then calls `/api/process-by-id` and displays the saved process plus clickable references.
      - Export to PDF: `exportPdfBtn` builds a robust payload (or GET fallback) to `/api/export-pdf`, downloads the generated PDF, and handles large content by trimming and fallbacks when needed.
      - Flowchart: `generateProcessDiagram()` uses a simplified, reference-stripped text to infer canonical phases, builds a Mermaid flowchart, and renders it inside a modal with SVG/PNG download options.
    - **Bookmarks system**:
      - `BookmarkManager` class (localStorage-backed) with methods to add/remove/inspect bookmarks, clear all, export to JSON, and render a responsive bookmarks list with actions.
      - Bookmarks are tightly integrated into search results via `bookmark_id` and include standard, page, snippet, query, and timestamp for later filtering and context.
    - **Multiple PDF Upload & Add-Book Orchestration**:
      - `/api/upload-pdfs`: UI for multi-PDF upload into `Books/`.
      - `/api/run-add-book`: Button to trigger the full backend `add_book.py` pipeline, with stdout/stderr captured for debugging directly in the UI.
- **Graphs-only UI (`app/templates/graphs.html` + `app/static/graphs.js`)**
  - A lighter page focused purely on similarity/difference/unique graphs for a given topic using `/api/graphs`.
  - Uses its own `drawScatterInteractive` implementation to project points and allow click-through to `/view` for the underlying chunks.
- **PDF Viewer UI (`app/templates/view.html`)**
  - Full-screen `<iframe>` that loads either the HTML-rendered book or the PDF with `#page=N&search=...` parameters.
  - Special styling and behavior when coming from dot-clicks (`from_dot=true`) to highlight the relevant snippet.
  - Minimal header with page navigation (jump to page, custom page input) toggled via a button or `H` keyboard shortcut.

### Testing & Quality Assurance
- **Python tests (`tests/`)**
  - `test_search_functionality.py`: Validates search engine import, initialization, query behavior, filtering, detailed comparison, analysis, page-number correctness, link generation, and metadata consistency.
  - `test_api_endpoints.py`: Black-box tests for all key endpoints (`/health`, `/api/search`, `/api/compare`, `/api/compare/detailed`, `/api/analysis`, `/api/graphs`, `/api/process-recommendation`, `/pdf/{standard}`, `/view`).
  - `test_process_recommendations.py`: Focuses on process recommendation behavior across project types/sizes/industries, ensuring structures are complete and content is meaningful and free of blacklisted tech chatter.
  - `test_ai_process_structuring.py` & `test_everything.py`: Deeper integration tests that validate AI pipeline wiring, GPT‑2 model behavior, and the end-to-end recommendation stack (including fallback paths).
- **Scripted checks (`scripts/`)**
  - `test_frontend_presence.py`: Uses FastAPI’s `TestClient` to confirm that the root HTML includes the Fetch-by-Code controls and that `/api/process-by-id` responds.
  - `test_process_by_id.py` and `test_fetch_15.py`: Exercise the filesystem-based process retrieval layer across a variety of codes and ensure the correct source buckets (`response` vs `response_with_embeddings`) and reference availability.
- **Meta test runner (`run_tests.py`)**
  - Boots the API server if needed, runs all major test suites plus page-number verification and a live data-integrity smoke test against the FAISS index, then stops the server and prints a summarized pass/fail table and success rate.

### End-to-End User Flows (for LinkedIn Storytelling)
- **1. “Research a topic across standards”**
  - User opens the app → types a topic in **All Search** → `/api/search` hits the FAISS index → results show enriched snippets with page numbers, deep links, and bookmark stars → user bookmarks key findings → bookmarks appear in the dedicated **Bookmarks** tab with filters and export.
- **2. “Compare how PMBOK vs PRINCE2 vs ISO treat a concept”**
  - User goes to **Compare** tab → enters a topic → `/api/compare` returns per-book buckets and synthesized insights → `/api/compare/detailed` powers a more granular view of similarities/differences at the excerpt level → user can click deep links to open source PDFs or the focused viewer.
- **3. “Generate a tailored project process with evidence”**
  - In the **Process Generator** tab, user picks scenario, type, size, industry, and methodology → frontend calls `/api/process-recommendation` with `use_ai=true`:
    - Backend pulls book embeddings via `SemanticSearch`, retrieves external context via `retrieve_external_context`, and passes everything into the AI pipeline.
    - GPT‑2/AI produces a structured, evidence-backed process; the app augments it with structured phases, per-step citations, roles, RACI, and decision gates, and caches it in `currentProcessData`.
  - User can:
    - Open a generated **flowchart** (Mermaid diagram) for a high-level visual.
    - Export a **PDF** process document with all metadata included.
- **4. “Load a pre-generated scenario by code”**
  - User enters/derives a 5‑digit code and clicks **Fetch by Code** → frontend calls `/api/process-by-id` → backend reads from `information/response[_with_embeddings]` and returns text + references → UI shows the canonical, (often Gemini-generated) scenario process and a clickable, book-level citations card, with fast navigation via `/view` and `/pdf` links.

This end-to-end pipeline—PDF ingestion → semantic embeddings → AI-enhanced reasoning → interactive visualizations & exports—is what powers the PM Standards Comparator and makes it a strong, portfolio-ready project for showcasing full-stack, ML, and AI integration skills.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip package manager

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd pm-standards-comparator
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up the data**
   ```bash
   # Place your PDF files in the Books/ directory:
   # - PMBOK 7th Edition PDF
   # - PRINCE2 PDF
   # - ISO 21500-2021 PDF
   # - ISO 21502-2020 PDF
   ```

4. **Build the search index**
   ```bash
   python ingest/build_index_final.py
   ```

5. **Run the application**
   ```bash
   python run.py
   ```

6. **Access the application**
   Open your browser and go to `http://localhost:8000`

## ▲ Deploy on Vercel

This repo includes a Vercel serverless entrypoint (`api/index.py`) and config (`vercel.json`).

### 1) Prepare (important limits)

- **PDF size limit**: Vercel deployments often fail if you include large PDFs in `Books/`.  
  Recommended: host PDFs elsewhere and set `PDF_BASE_URL` (see below).
- **Cold starts**: Loading ML models/indexes can be slow on first request.

### 2) Push to GitHub

Vercel deploys from a Git repo. Push this folder to GitHub (or any git provider Vercel supports).

### 3) Create the Vercel project

- In Vercel dashboard: **New Project** → import your repo
- **Framework preset**: “Other”
- **Root Directory**: repository root (the folder containing `vercel.json`)

### 4) Set environment variables (recommended)

In Vercel → Project → Settings → Environment Variables:

- **`PDF_BASE_URL`**: Base URL where your PDFs are hosted, e.g.  
  `https://your-bucket-or-host/Books`  
  When set, `GET /pdf/{standard}` will **redirect** to `PDF_BASE_URL/<filename>`.

### 5) Deploy

Click **Deploy**. After deployment:
- `/<root>` serves the UI
- `/health` should return `{"status":"ok"}`
- `/api/search?q=risk%20management` should return search results

## 📚 Usage

### Search Functionality
- **All Search**: Search across all standards simultaneously
- **Book Search**: Search within specific standards
- **Advanced Filters**: Filter by standard, page range, or content type

### Comparison Features
- **Quick Compare**: Get instant comparisons for any topic
- **Detailed Analysis**: Deep dive into similarities and differences
- **Visual Analytics**: Interactive charts and relationship maps

### Process Generation
- **Project Setup**: Define project characteristics
- **Recommendation Engine**: Get tailored process recommendations
- **Evidence Base**: See which standards support each recommendation

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all tests
python run_tests.py

# Run specific test suites
python tests/test_search_functionality.py
python tests/test_api_endpoints.py
python tests/test_process_recommendations.py
```

## 📁 Project Structure

```
pm-standards-comparator/
├── app/                    # Main application
│   ├── main.py            # FastAPI application
│   ├── routers/           # API routes
│   ├── services/          # Core services
│   ├── static/            # Frontend assets
│   └── templates/         # HTML templates
├── ingest/                # Data processing
│   ├── build_index_final.py
│   ├── analyze_page_numbers.py
│   └── verify_page_numbers.py
├── tests/                 # Test suite
│   ├── test_api_endpoints.py
│   ├── test_search_functionality.py
│   └── test_process_recommendations.py
├── data/                  # Search index and metadata
├── Books/                 # PDF documents
├── docs/                  # Documentation
└── requirements.txt       # Dependencies
```

## 🔧 API Endpoints

### Search
- `GET /api/search` - Semantic search across standards
- `GET /api/compare` - Topic comparison
- `GET /api/compare/detailed` - Detailed analysis

### Process Generation
- `GET /api/process-recommendation` - Generate tailored processes

### Analytics
- `GET /api/analysis` - Full analysis of all standards
- `GET /api/graphs` - Visual analytics

### PDF Access
- `GET /pdf/{standard}` - Access PDF documents
- `GET /view` - PDF viewer with navigation

## 🎓 Educational Use

This application is designed for:
- **Project Managers**: Compare methodologies and choose appropriate approaches
- **Students**: Learn about different PM standards and their applications
- **Researchers**: Analyze relationships between PM frameworks
- **Organizations**: Standardize project management practices

## 📖 Standards Covered

- **PMBOK 7th Edition**: Process-based approach with knowledge areas
- **PRINCE2**: Product-based planning with clear roles
- **ISO 21500**: International project management guidance
- **ISO 21502**: Project management best practices

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is for educational purposes. Please ensure you have proper licenses for the PM standards documents.

## 🤖 AI Features

### Google Gemini Integration
- **AI-Powered Process Generation**: Detailed, context-aware project processes
- **AI-Powered Summaries**: Comprehensive standard summaries
- **Secure API Key**: Encrypted, backend-only storage
- **Graceful Fallback**: Template-based generation if AI unavailable

**Documentation**: See `docs/AI_INTEGRATION_GUIDE.md` for details

## 🆘 Support

For issues and questions:
1. Check the documentation in `/docs`
2. Run the test suite to verify functionality
3. Create an issue in the repository

## 🔄 Updates

- **v1.0**: Initial release with basic search and comparison
- **v1.1**: Added process recommendation engine
- **v1.2**: Enhanced analytics and visualization
- **v1.3**: Improved page numbering and deep linking
- **v1.4**: 🤖 **AI Integration** - Google Gemini for process generation and summaries
- **v1.5**: 📚 **Bookmarking System** - Full bookmark management with localStorage
- **v1.6**: 🟣 **Enhanced Unique Detection** - Cross-book similarity algorithm

---

**Built with ❤️ for the Project Management community**
