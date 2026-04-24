Frontend: UI + Fetch + Rendering

UI (index.html)
- Add a numeric code input, button, status line, and containers (already in app/templates/index.html):
```html
<div class="row">
  <button id="generateProcessBtn">Generate Process</button>
  <input id="processCode" type="text" inputmode="numeric" pattern="\d{5}" maxlength="5" placeholder="Enter 5-digit code (e.g., 11111)" style="margin-left:10px; width:180px;" />
  <button id="fetchProcessByCodeBtn" class="btn-secondary" aria-busy="false" style="margin-left:10px;">Fetch by Code</button>
</div>
<div id="fetchStatus" class="muted" style="margin-top: 8px; min-height: 18px;"></div>

<div id="processResults" style="display: none;">
  <div class="row" style="margin-bottom: 20px;">
    <button id="viewDiagramBtn" class="btn-secondary" style="display: none;">📊 View Process Diagram</button>
    <button id="exportPdfBtn" class="btn-primary" style="display: none;">📄 Export Process Document</button>
  </div>
  <div id="processRecommendations"></div>
  <div id="processDetails"></div>
</div>
```

Fetch + Rendering (app.js)
Key functions involved in the flow:
1) deriveCodeFromForm() → returns manual 5-digit code or derives from form selections
2) attachFetchByCodeHandler() → binds click & Enter; shows status & disables button; calls fetchAndDisplayByCode
3) fetchAndDisplayByCode(code) → calls /api/process-by-id?code=XXXXX with timeout; renders text + clickable references
4) buildReferencesHtml(refs) → turns JSON references into links to /pdf/<STANDARD>#page=<n> and /view?standard=...&page=...

Code (extract)
```javascript
async function fetchJSONWithTimeout(url, opts, timeoutMs = 15000){
  let timer;
  try{
    const p = Promise.race([
      fetchJSON(url, opts),
      new Promise((_, reject)=>{ timer = setTimeout(()=>reject(new Error('Request timeout')), timeoutMs); })
    ]);
    return await p;
  } finally { if (timer) clearTimeout(timer); }
}

function deriveCodeFromForm(){
  const manualEl = document.getElementById('processCode');
  const manual = (manualEl && manualEl.value) ? manualEl.value.trim() : '';
  if (/^\d{5}$/.test(manual)) return manual;
  // map form selections to digits (scenario/type/size/industry/methodology)
  // returns e.g., "11111"; see app.js for full mapping
}

async function fetchAndDisplayByCode(code){
  const resultsDiv = document.getElementById('processResults');
  const recommendationsDiv = document.getElementById('processRecommendations');
  const detailsDiv = document.getElementById('processDetails');
  resultsDiv.style.display = 'block';
  showProcessStatus('📄 Fetching process from files…');
  detailsDiv.innerHTML = '';

  try{
    const url = window.location.origin + `/api/process-by-id?code=${encodeURIComponent(code)}`;
    const data = await fetchJSONWithTimeout(url, undefined, 15000);
    if(data.error){ showProcessError(`Error: ${data.error}`); return; }
    const src = data.source === 'response' ? 'Without Embeddings' : 'With Embeddings';
    const refs = (data.references && data.references.references) ? data.references.references : (data.references || []);
    const refsHtml = buildReferencesHtml(refs);
    recommendationsDiv.innerHTML = `
      <div class="card">
        <h3>Process ${code} <span class="muted" style="font-size:12px;">(${src})</span></h3>
        <div style="white-space: pre-wrap;">${data.text}</div>
      </div>`;
    detailsDiv.innerHTML = refsHtml;
    appendProcessFooter(recommendationsDiv, code, src);
  }catch(e){ showProcessError(`Error: ${e.message}`); }
}

function buildReferencesHtml(refs){
  if (!Array.isArray(refs) || refs.length === 0) return '<div class="muted">No references available.</div>';
  const items = refs.map(r=>{
    const std = r.standard || 'Unknown';
    const page = r.page || '?';
    const score = (typeof r.score === 'number') ? r.score.toFixed(3) : (r.score||'');
    const mapped = mapStandardToKey(std); // PMBOK|PRINCE2|ISO21500|ISO21502
    const viewHref = mapped ? `/view?standard=${encodeURIComponent(mapped)}&page=${encodeURIComponent(page)}&text=${encodeURIComponent((r.text||'').slice(0,160))}` : '';
    const pdfHref = r.link ? r.link : (mapped ? `/pdf/${mapped}#page=${page}` : '');
    const linkParts = [];
    if (pdfHref) linkParts.push(`<a href="${pdfHref}" target="_blank">Open PDF</a>`);
    if (viewHref) linkParts.push(`<a href="${viewHref}" target="_blank">Open View</a>`);
    return `<li><strong>${std}</strong> · p.${page} ${score?`· sim=${score}`:''}<br>${linkParts.join(' · ')}</li>`;
  }).join('');
  return `<div class="card"><h3>📑 Clickable References</h3><ul style="padding-left:18px;">${items}</ul></div>`;
}
```

UX behaviors
- Status line under controls shows: "Validating code…" → "Code: XXXXX — Getting info…" → "Loaded." on success.
- Errors render inside the Process section with a red-accent card.
- Enter key inside the code input triggers the same fetch as the button.


