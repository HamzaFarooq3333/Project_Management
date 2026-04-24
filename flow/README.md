Flow: Fetch-and-Display Process Content by Code

Purpose
This folder documents the complete flow (backend + frontend) that fetches a saved process by its 5‑digit code from the filesystem and renders it in the UI when the "Fetch by Code" button is clicked.

High-level Flow
1) User enters a 5‑digit code (or leaves blank to derive from form selections) and clicks "Fetch by Code".
2) Frontend derives the code, shows inline status ("Getting info…"), and calls GET /api/process-by-id?code=XXXXX.
3) Backend resolves the code to the proper file location:
   - If code is listed in no_data/no_embedding.txt → information/response/<code>.txt
   - Else → information/response_with_embeddings/<code>.txt (+ *_references.json if present)
4) Backend returns { code, source, text, references }. Frontend renders text and a clickable references list.

Key Files
- Backend
  - app/routers/api.py → /api/process-by-id endpoint
  - app/main.py → FastAPI app, static/templates mount, CORS, folder creation for information/response and information/response_with_embeddings
- Frontend
  - app/templates/index.html → Process Generator UI (inputs, "Fetch by Code" button, containers)
  - app/static/app.js → Event binding, code derivation, fetch with timeout, status/error helpers, rendering + clickable references

Migration Guide (to a new project)
1) Copy these files (or port the logic):
   - Backend: app/main.py (or at minimum the INFO_DIR folder creation block), app/routers/api.py (/api/process-by-id) and your existing app structure
   - Frontend: app/templates/index.html (Process tab portion), app/static/app.js (Fetch-by-Code helpers and bindings)
2) Ensure the information folder exists or is created on startup with two subfolders:
   - information/response
   - information/response_with_embeddings
3) Place your pre-generated files (<code>.txt and <code>_references.json) into those subfolders accordingly.
4) Start the app and verify:
   - Navigating to the Process tab
   - Entering a code (e.g., 11111)
   - Clicking Fetch by Code → should display status, content, and references.

See backend.md and frontend.md in this folder for exact code and details.


