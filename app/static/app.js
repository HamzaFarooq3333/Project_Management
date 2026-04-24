async function fetchJSON(url, opts){
  const fullUrl = url && url.startsWith('/') ? (window.location.origin + url) : url;
  const res = await fetch(fullUrl, opts);
  if(!res.ok) throw new Error(await res.text());
  return res.json();
}

// Fetch wrapper with timeout (default 15s)
async function fetchJSONWithTimeout(url, opts, timeoutMs = 15000){
  let timer;
  try{
    const p = Promise.race([
      fetchJSON(url, opts),
      new Promise((_, reject)=>{ timer = setTimeout(()=>reject(new Error('Request timeout')), timeoutMs); })
    ]);
    return await p;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

// Simple markdown-to-HTML converter for AI-generated content
function formatMarkdown(text) {
  // Coerce input to a safe string
  const src = typeof text === 'string'
    ? text
    : (text && typeof text.process === 'string'
        ? text.process
        : (text?.toString?.() || ''));
  if (!src) return '';
  
  // Convert markdown to HTML
  let html = src
    // Headers
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    // Bold
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    // Lists (unordered)
    .replace(/^\- (.*$)/gim, '<li>$1</li>')
    // Lists (numbered)
    .replace(/^\d+\. (.*$)/gim, '<li>$1</li>')
    // Line breaks
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
  
  // Wrap lists in ul tags
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
  
  // Wrap content in paragraphs if not already wrapped
  if (!html.startsWith('<')) {
    html = '<p>' + html + '</p>';
  }
  
  return html;
}

// Sanitize AI text: remove URLs and generator footers
function sanitizeAIText(text){
  if(!text || typeof text !== 'string') return '';
  let t = text
    // remove explicit link: ... lines
    .replace(/^\s*link:\s*\S+.*/gim, '')
    // remove raw URLs
    .replace(/https?:\/\/\S+/g, '')
    // remove common generator footer lines
    .replace(/^\s*Generated using:.*$/gim, '')
    .replace(/^\s*Note:\s*.*$/gim, (m)=> m.includes('project management guide') ? '' : m)
    // collapse multiple blank lines
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  return t;
}

// ==================== BOOKMARK MANAGEMENT ====================
class BookmarkManager {
  constructor() {
    this.STORAGE_KEY = 'pm_standards_bookmarks';
    this.bookmarks = this.loadBookmarks();
  }
  
  loadBookmarks() {
    try {
      const stored = localStorage.getItem(this.STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch (e) {
      console.error('Failed to load bookmarks:', e);
      return [];
    }
  }
  
  saveBookmarks() {
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.bookmarks));
      this.updateBookmarksDisplay();
    } catch (e) {
      console.error('Failed to save bookmarks:', e);
    }
  }
  
  addBookmark(result) {
    const bookmark = {
      id: result.bookmark_id || `${result.standard}_${result.page}_${Date.now()}`,
      standard: result.standard,
      text: result.text,
      page: result.page,
      link: result.link,
      timestamp: Date.now(),
      query: result.query || ''
    };
    
    // Check if already bookmarked
    const exists = this.bookmarks.find(b => b.id === bookmark.id);
    if (!exists) {
      this.bookmarks.unshift(bookmark); // Add to beginning
      this.saveBookmarks();
      this.showNotification('✅ Bookmark added!');
      return true;
    }
    return false;
  }
  
  removeBookmark(id) {
    this.bookmarks = this.bookmarks.filter(b => b.id !== id);
    this.saveBookmarks();
    this.showNotification('🗑️ Bookmark removed');
  }
  
  isBookmarked(result) {
    const id = result.bookmark_id || `${result.standard}_${result.page}_${Date.now()}`;
    return this.bookmarks.some(b => b.id === id);
  }
  
  clearAll() {
    if (confirm('Are you sure you want to delete all bookmarks?')) {
      this.bookmarks = [];
      this.saveBookmarks();
      this.showNotification('🗑️ All bookmarks cleared');
    }
  }
  
  exportBookmarks() {
    const data = JSON.stringify(this.bookmarks, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pm-bookmarks-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    this.showNotification('📥 Bookmarks exported!');
  }
  
  updateBookmarksDisplay(filter = '') {
    const listContainer = document.getElementById('bookmarksList');
    const noBookmarks = document.getElementById('noBookmarks');
    const stats = document.getElementById('bookmarksStats');
    const filters = document.getElementById('bookmarkFilters');
    
    let displayBookmarks = this.bookmarks;
    
    // Apply filter
    if (filter) {
      displayBookmarks = this.bookmarks.filter(b => 
        b.standard.toUpperCase().includes(filter.toUpperCase())
      );
    }
    
    if (this.bookmarks.length === 0) {
      noBookmarks.style.display = 'block';
      listContainer.innerHTML = '';
      stats.style.display = 'none';
      filters.style.display = 'none';
      return;
    }
    
    noBookmarks.style.display = 'none';
    stats.style.display = 'block';
    filters.style.display = 'flex';
    
    // Update stats
    const standards = [...new Set(this.bookmarks.map(b => b.standard))];
    document.getElementById('totalBookmarks').textContent = this.bookmarks.length;
    document.getElementById('bookmarkStandards').textContent = standards.join(', ');
    
    // Render bookmarks
    listContainer.innerHTML = displayBookmarks.map(b => `
      <div class="bookmark-item">
        <div class="bookmark-header">
          <span class="bookmark-standard">${b.standard}</span>
          <div class="bookmark-actions">
            <button class="bookmark-open" onclick="window.open('${b.link}', '_blank')">
              📖 Open
            </button>
            <button class="bookmark-delete" onclick="bookmarkManager.removeBookmark('${b.id}')">
              🗑️ Delete
            </button>
          </div>
        </div>
        <div class="bookmark-text">${b.text.substring(0, 300)}${b.text.length > 300 ? '...' : ''}</div>
        <div class="bookmark-meta">
          <span>📄 Page ${b.page}</span>
          <span>🕐 ${new Date(b.timestamp).toLocaleDateString()}</span>
          ${b.query ? `<span>🔍 Query: "${b.query}"</span>` : ''}
        </div>
      </div>
    `).join('');
  }
  
  showNotification(message) {
    // Simple notification - could be enhanced with a toast library
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: var(--accent);
      color: #04151f;
      padding: 12px 20px;
      border-radius: 8px;
      font-weight: 600;
      z-index: 10000;
      animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
      notification.style.animation = 'slideOut 0.3s ease';
      setTimeout(() => notification.remove(), 300);
    }, 2000);
  }
}

// Initialize bookmark manager
const bookmarkManager = new BookmarkManager();

// Add CSS animations for notifications
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }
  @keyframes slideOut {
    from { transform: translateX(0); opacity: 1; }
    to { transform: translateX(100%); opacity: 0; }
  }
`;
document.head.appendChild(style);

// Tabs
document.querySelectorAll('.tab').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p=>p.classList.remove('active'));
    btn.classList.add('active');
    const tab = btn.getAttribute('data-tab');
    document.getElementById(`tab-${tab}`).classList.add('active');
    // Re-attach fetch handler when switching to Process tab
    if (tab === 'process') {
      try { attachFetchByCodeHandler(); } catch(_) {}
    }
  });
});

document.getElementById('searchBtn').addEventListener('click', async ()=>{
  const q = document.getElementById('searchInput').value;
  const out = document.getElementById('searchResults');
  out.innerHTML = '<div class="muted">Searching…</div>';
  try{
    const data = await fetchJSON(`/api/search?q=${encodeURIComponent(q)}`);
    out.innerHTML = data.results.map(r=>{
      const link = r.link ? `<a href="${r.link}" target="_blank">Open</a>` : '';
      const isBookmarked = bookmarkManager.isBookmarked(r);
      const bookmarkBtnClass = isBookmarked ? 'bookmark-btn bookmarked' : 'bookmark-btn';
      r.query = q; // Store query for bookmark
      return `
        <div class="card">
          <div style="display: flex; justify-content: space-between; align-items: start;">
            <div style="flex: 1;">${r.text}</div>
            <button class="${bookmarkBtnClass}" onclick='bookmarkManager.addBookmark(${JSON.stringify(r).replace(/'/g, "&#39;")})' title="Bookmark this result">
              ${isBookmarked ? '⭐' : '☆'}
            </button>
          </div>
          <div class="muted">${r.standard} · p.${r.page} ${link}</div>
        </div>
      `;
    }).join('');
  }catch(e){ out.innerHTML = `<div class="muted">${e.message}</div>`; }
});

// Book search with standard filter
document.getElementById('bookSearchBtn').addEventListener('click', async ()=>{
  const q = document.getElementById('bookSearchInput').value;
  const std = document.getElementById('standardSelect').value;
  const out = document.getElementById('bookSearchResults');
  out.innerHTML = '<div class="muted">Searching…</div>';
  try{
    const data = await fetchJSON(`/api/search?q=${encodeURIComponent(q)}&standard=${encodeURIComponent(std)}`);
    out.innerHTML = data.results.map(r=>{
      const link = r.link ? `<a href="${r.link}" target="_blank">Open</a>` : '';
      const isBookmarked = bookmarkManager.isBookmarked(r);
      const bookmarkBtnClass = isBookmarked ? 'bookmark-btn bookmarked' : 'bookmark-btn';
      r.query = q; // Store query for bookmark
      return `
        <div class="card">
          <div style="display: flex; justify-content: space-between; align-items: start;">
            <div style="flex: 1;">${r.text}</div>
            <button class="${bookmarkBtnClass}" onclick='bookmarkManager.addBookmark(${JSON.stringify(r).replace(/'/g, "&#39;")})' title="Bookmark this result">
              ${isBookmarked ? '⭐' : '☆'}
            </button>
          </div>
          <div class="muted">${r.standard} · p.${r.page} ${link}</div>
        </div>
      `;
    }).join('');
  }catch(e){ out.innerHTML = `<div class="muted">${e.message}</div>`; }
});

document.getElementById('compareBtn').addEventListener('click', async ()=>{
  const topic = document.getElementById('compareTopic').value;
  const out = document.getElementById('compareResults');
  out.innerHTML = '<div class="muted">Comparing…</div>';
  try{
    const data = await fetchJSON(`/api/compare?topic=${encodeURIComponent(topic)}`);
    const cols = ['PMBOK','PRINCE2','ISO'];
    out.innerHTML = cols.map(k=>{
      const item = data[k.toLowerCase()] || {summary:'No match', link:null};
      const linkHtml = item.link ? `<a href="${item.link}" target="_blank">Open</a>` : '';
      return `<div class="card"><h3>${k}</h3><div>${item.summary}</div><div class="muted">${linkHtml}</div></div>`;
    }).join('');
    const insights = document.getElementById('insights');
    insights.innerHTML = `
      <div class="card"><strong>Similarities</strong><div>${(data.insights?.similarities||[]).join('<br>')}</div></div>
      <div class="card"><strong>Differences</strong><div>${(data.insights?.differences||[]).join('<br>')}</div></div>
      <div class="card"><strong>Unique Points</strong><div>${(data.insights?.uniques||[]).join('<br>')}</div></div>
    `;
  }catch(e){ out.innerHTML = `<div class="muted">${e.message}</div>`; }
});

// Detailed similarities/differences
document.getElementById('compareDetailedBtn').addEventListener('click', async ()=>{
  const topic = document.getElementById('compareTopic').value;
  const out = document.getElementById('compareDetailed');
  out.innerHTML = '<div class="muted">Analyzing…</div>';
  try{
    const data = await fetchJSON(`/api/compare/detailed?topic=${encodeURIComponent(topic)}`);
    const simHtml = (data.similarities||[]).map(p=>{
      const a = p.a, b = p.b;
      return `<div class="card"><div><strong>${a.standard}</strong> ↔ <strong>${b.standard}</strong> <span class="muted">(sim=${p.similarity.toFixed(2)})</span></div><div>${a.text}</div><div>${b.text}</div><div class="muted">${a.link?`<a href="${a.link}" target="_blank">Open A</a>`:''} ${b.link?`<a href="${b.link}" target="_blank">Open B</a>`:''}</div></div>`;
    }).join('');
    const diffHtml = (data.differences||[]).map(p=>{
      const a = p.a, b = p.b;
      return `<div class="card"><div><strong>${a.standard}</strong> ↔ <strong>${b.standard}</strong> <span class="muted">(sim=${p.similarity.toFixed(2)})</span></div><div>${a.text}</div><div>${b.text}</div><div class="muted">${a.link?`<a href="${a.link}" target="_blank">Open A</a>`:''} ${b.link?`<a href="${b.link}" target="_blank">Open B</a>`:''}</div></div>`;
    }).join('');
    const uniqHtml = (data.uniques||[]).map(u=>{
      return `<div class="card"><div><strong>${u.standard}</strong> (unique)</div><div>${u.text}</div><div class="muted">${u.link?`<a href="${u.link}" target="_blank">Open</a>`:''}</div></div>`;
    }).join('');
    out.innerHTML = `
      <div class="card"><h3>Similarities</h3>${simHtml || '<div class="muted">None found</div>'}</div>
      <div class="card"><h3>Differences</h3>${diffHtml || '<div class="muted">None found</div>'}</div>
      <div class="card"><h3>Unique Points</h3>${uniqHtml || '<div class="muted">None found</div>'}</div>
    `;
  }catch(e){ out.innerHTML = `<div class="muted">${e.message}</div>`; }
});

// Book analysis scatter plots (no external libs)
function drawScatterInteractiveAnalysis(canvas, points, color){
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0,0,canvas.width,canvas.height);
  let xs = points.map(p=>p.x), ys = points.map(p=>p.y);
  const minX = Math.min(...xs, -1), maxX = Math.max(...xs, 1);
  const minY = Math.min(...ys, -1), maxY = Math.max(...ys, 1);
  const pad = 20;
  function sx(x){ return pad + (x - minX) * (canvas.width - 2*pad) / (maxX - minX || 1); }
  function sy(y){ return canvas.height - (pad + (y - minY) * (canvas.height - 2*pad) / (maxY - minY || 1)); }
  ctx.strokeStyle = '#32406f'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad, sy(0)); ctx.lineTo(canvas.width-pad, sy(0)); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(sx(0), pad); ctx.lineTo(sx(0), canvas.height-pad); ctx.stroke();
  const screenPoints = points.map(p=>({ ...p, sx: sx(p.x), sy: sy(p.y) }));
  ctx.fillStyle = color;
  screenPoints.forEach(p=>{ ctx.beginPath(); ctx.arc(p.sx, p.sy, 3, 0, Math.PI*2); ctx.fill(); });
  canvas.onclick = (ev)=>{
    const rect = canvas.getBoundingClientRect();
    const mx = ev.clientX - rect.left;
    const my = ev.clientY - rect.top;
    const hit = screenPoints.find(p=>{ const dx = p.sx - mx, dy = p.sy - my; return dx*dx + dy*dy <= 9*1.5; });
    if(hit){
      const url = `/view?standard=${encodeURIComponent(hit.standard)}&page=${encodeURIComponent(hit.page)}&text=${encodeURIComponent(hit.text)}&from_dot=true`;
      window.open(url, '_blank');
    }
  };
}

// Enhanced Book Analysis with Progress Bar and Interactive Features
document.getElementById('runAnalysisBtn').addEventListener('click', async ()=>{
  const progressSection = document.getElementById('bookAnalysisProgress');
  const resultsSection = document.getElementById('bookAnalysisResults');
  const progressFill = document.getElementById('bookProgressFill');
  const progressText = document.getElementById('bookProgressText');
  const progressStatus = document.getElementById('bookProgressStatus');
  const legend = document.getElementById('analysisLegend');
  
  // Show progress section
  progressSection.style.display = 'block';
  resultsSection.style.display = 'none';
  
  // Reset progress
  progressFill.style.width = '0%';
  progressText.textContent = '0%';
  progressStatus.textContent = 'Starting analysis...';
  
  try {
    // Simulate progress updates
    const progressSteps = [
      { progress: 10, text: 'Initializing analysis engine...' },
      { progress: 25, text: 'Loading embeddings from all books...' },
      { progress: 40, text: 'Computing similarity matrices...' },
      { progress: 60, text: 'Analyzing relationships...' },
      { progress: 80, text: 'Generating visualizations...' },
      { progress: 100, text: 'Analysis complete!' }
    ];
    
    for (const step of progressSteps) {
      await new Promise(resolve => setTimeout(resolve, 800));
      progressFill.style.width = step.progress + '%';
      progressText.textContent = step.progress + '%';
      progressStatus.textContent = step.text;
    }
    
    // Get analysis data
    const data = await fetchJSON(`/api/analysis`);
    const sim = (data.points||[]).filter(p=>p.label==='similar');
    const dis = (data.points||[]).filter(p=>p.label==='dissimilar');
    const unique = (data.points||[]).filter(p=>p.label==='unique');
    
    // Hide progress, show results
    progressSection.style.display = 'none';
    resultsSection.style.display = 'block';
    
    // Draw interactive charts
    const simCanvas = document.getElementById('chartSimilar');
    const disCanvas = document.getElementById('chartDissimilar');
    const uniqueCanvas = document.getElementById('chartUnique');
    
    drawEnhancedScatter(simCanvas, sim, '#5bc0be', 'similar');
    drawEnhancedScatter(disCanvas, dis, '#ff4d4d', 'dissimilar');
    drawEnhancedScatter(uniqueCanvas, unique, '#9d4edd', 'unique');
    
    // Enhanced legend with debug info and book statistics
    const debugInfo = data.debug_info || {};
    const bookStats = data.book_stats || {};
    
    // Build book statistics HTML
    let bookStatsHTML = '';
    if (Object.keys(bookStats).length > 0) {
      bookStatsHTML = '<div style="margin-top: 15px; padding: 10px; background: #11182f; border-radius: 6px;">';
      bookStatsHTML += '<strong>📚 Unique Content by Standard:</strong><br>';
      for (const [book, stats] of Object.entries(bookStats)) {
        const uniquePct = stats.unique_percentage.toFixed(1);
        bookStatsHTML += `<div style="margin-top: 5px;">
          <strong>${book}:</strong> ${stats.unique} unique (${uniquePct}%) | 
          ${stats.similar} similar | ${stats.dissimilar} dissimilar
        </div>`;
      }
      bookStatsHTML += '</div>';
    }
    
    legend.innerHTML = `
      <div style="margin-bottom: 10px;">
        <strong>✅ Analysis Complete!</strong><br>
        📊 <strong>Total Points:</strong> ${debugInfo.total_points || data.points?.length || 0}<br>
        🔵 <strong>Similarities:</strong> ${debugInfo.similar_count || sim.length} | 
        🔴 <strong>Dissimilarities:</strong> ${debugInfo.dissimilar_count || dis.length} |
        🟣 <strong>Unique:</strong> ${debugInfo.unique_count || unique.length}<br>
        ⚙️ <strong>Similar Threshold:</strong> ${debugInfo.threshold_used || '0.6'} | 
        <strong>Unique Threshold:</strong> ${debugInfo.unique_threshold_used || '0.35'}<br>
        🧠 <strong>Algorithm:</strong> ${data.algorithm || 'cross_book_similarity'}
      </div>
      ${bookStatsHTML}
      <div style="color: var(--muted); font-size: 12px; margin-top: 10px;">
        Click any dot to view details, or use expand buttons to enlarge graphs.<br>
        <span style="color: #9d4edd;">🟣 Purple dots represent content unique to one book (cross-book similarity < ${debugInfo.unique_threshold_used || '0.35'}).</span>
      </div>
    `;
    
  } catch(e) { 
    progressStatus.textContent = 'Error: ' + e.message;
    legend.textContent = e.message; 
  }
});



// Enhanced scatter plot function with dot preview functionality
function drawEnhancedScatter(canvas, points, color, type){
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0,0,canvas.width,canvas.height);
  
  if (points.length === 0) {
    ctx.fillStyle = '#a3a3a3';
    ctx.font = '14px Inter';
    ctx.textAlign = 'center';
    ctx.fillText('No data points', canvas.width/2, canvas.height/2);
    return;
  }
  
  let xs = points.map(p=>p.x), ys = points.map(p=>p.y);
  const minX = Math.min(...xs, -1), maxX = Math.max(...xs, 1);
  const minY = Math.min(...ys, -1), maxY = Math.max(...ys, 1);
  const pad = 20;
  
  function sx(x){ return pad + (x - minX) * (canvas.width - 2*pad) / (maxX - minX || 1); }
  function sy(y){ return canvas.height - (pad + (y - minY) * (canvas.height - 2*pad) / (maxY - minY || 1)); }
  
  // Draw axes
  ctx.strokeStyle = '#32406f'; 
  ctx.lineWidth = 1;
  ctx.beginPath(); 
  ctx.moveTo(pad, sy(0)); 
  ctx.lineTo(canvas.width-pad, sy(0)); 
  ctx.stroke();
  ctx.beginPath(); 
  ctx.moveTo(sx(0), pad); 
  ctx.lineTo(sx(0), canvas.height-pad); 
  ctx.stroke();
  
  const screenPoints = points.map(p=>({ ...p, sx: sx(p.x), sy: sy(p.y) }));
  
  // Draw points
  ctx.fillStyle = color;
  screenPoints.forEach(p=>{ 
    ctx.beginPath(); 
    ctx.arc(p.sx, p.sy, 4, 0, Math.PI*2); 
    ctx.fill();
    
    // Add hover effect
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.stroke();
  });
  
  // Click handler for dot preview
  canvas.onclick = (ev)=>{
    const rect = canvas.getBoundingClientRect();
    const mx = ev.clientX - rect.left;
    const my = ev.clientY - rect.top;
    const hit = screenPoints.find(p=>{ 
      const dx = p.sx - mx, dy = p.sy - my; 
      return dx*dx + dy*dy <= 16*1.5;
    });
    if(hit){
      showDotPreview(hit, type);
    }
  };
  
  // Hover effect
  canvas.onmousemove = (ev)=>{
    const rect = canvas.getBoundingClientRect();
    const mx = ev.clientX - rect.left;
    const my = ev.clientY - rect.top;
    const hit = screenPoints.find(p=>{ 
      const dx = p.sx - mx, dy = p.sy - my; 
      return dx*dx + dy*dy <= 16*1.5;
    });
    canvas.style.cursor = hit ? 'pointer' : 'default';
  };
}

// Dot preview functionality
function showDotPreview(point, type) {
  const preview = document.getElementById('dotPreview');
  const bookSpan = document.getElementById('previewBook');
  const pageSpan = document.getElementById('previewPage');
  const typeSpan = document.getElementById('previewType');
  const textSpan = document.getElementById('previewText');
  const viewBtn = document.getElementById('viewInBookBtn');
  
  // Populate preview data
  bookSpan.textContent = point.standard || 'Unknown';
  pageSpan.textContent = point.page || 'Unknown';
  
  // Enhanced type display with color coding
  let typeText = '';
  let typeClass = '';
  if (type === 'similar') {
    typeText = 'Similar';
    typeClass = 'similar-label';
  } else if (type === 'unique') {
    typeText = 'Unique';
    typeClass = 'unique-label';
  } else {
    typeText = 'Dissimilar';
    typeClass = 'dissimilar-label';
  }
  
  typeSpan.textContent = typeText;
  typeSpan.className = typeClass;
  textSpan.textContent = point.text || 'No text available';
  
  // Set up view button
  viewBtn.onclick = () => {
    const url = `/view?standard=${encodeURIComponent(point.standard)}&page=${encodeURIComponent(point.page)}&text=${encodeURIComponent(point.text)}&from_dot=true`;
    window.open(url, '_blank');
  };
  
  // Show preview
  preview.style.display = 'block';
  preview.scrollIntoView({ behavior: 'smooth' });
}

// Close preview
document.getElementById('closePreviewBtn').addEventListener('click', () => {
  document.getElementById('dotPreview').style.display = 'none';
});

// Expand/Contract functionality for graphs
function setupGraphExpansion() {
  // Similar graph expansion
  document.getElementById('expandSimilarBtn').addEventListener('click', () => {
    const card = document.querySelector('.analysis-card:first-child');
    const container = card.querySelector('.graph-container');
    const canvas = document.getElementById('chartSimilar');
    
    card.classList.add('expanded');
    container.classList.add('expanded');
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    
    document.getElementById('expandSimilarBtn').style.display = 'none';
    document.getElementById('contractSimilarBtn').style.display = 'inline-block';
  });
  
  document.getElementById('contractSimilarBtn').addEventListener('click', () => {
    const card = document.querySelector('.analysis-card:first-child');
    const container = card.querySelector('.graph-container');
    const canvas = document.getElementById('chartSimilar');
    
    card.classList.remove('expanded');
    container.classList.remove('expanded');
    canvas.width = 400;
    canvas.height = 300;
    
    document.getElementById('expandSimilarBtn').style.display = 'inline-block';
    document.getElementById('contractSimilarBtn').style.display = 'none';
  });
  
  // Dissimilar graph expansion
  document.getElementById('expandDissimilarBtn').addEventListener('click', () => {
    const cards = document.querySelectorAll('.analysis-card');
    const card = cards[1]; // Second card (dissimilar)
    const container = card.querySelector('.graph-container');
    const canvas = document.getElementById('chartDissimilar');
    
    card.classList.add('expanded');
    container.classList.add('expanded');
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    
    document.getElementById('expandDissimilarBtn').style.display = 'none';
    document.getElementById('contractDissimilarBtn').style.display = 'inline-block';
  });
  
  document.getElementById('contractDissimilarBtn').addEventListener('click', () => {
    const cards = document.querySelectorAll('.analysis-card');
    const card = cards[1]; // Second card (dissimilar)
    const container = card.querySelector('.graph-container');
    const canvas = document.getElementById('chartDissimilar');
    
    card.classList.remove('expanded');
    container.classList.remove('expanded');
    canvas.width = 400;
    canvas.height = 300;
    
    document.getElementById('expandDissimilarBtn').style.display = 'inline-block';
    document.getElementById('contractDissimilarBtn').style.display = 'none';
  });
  
  // Unique graph expansion
  document.getElementById('expandUniqueBtn').addEventListener('click', () => {
    const cards = document.querySelectorAll('.analysis-card');
    const card = cards[2]; // Third card (unique)
    const container = card.querySelector('.graph-container');
    const canvas = document.getElementById('chartUnique');
    
    card.classList.add('expanded');
    container.classList.add('expanded');
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    
    document.getElementById('expandUniqueBtn').style.display = 'none';
    document.getElementById('contractUniqueBtn').style.display = 'inline-block';
  });
  
  document.getElementById('contractUniqueBtn').addEventListener('click', () => {
    const cards = document.querySelectorAll('.analysis-card');
    const card = cards[2]; // Third card (unique)
    const container = card.querySelector('.graph-container');
    const canvas = document.getElementById('chartUnique');
    
    card.classList.remove('expanded');
    container.classList.remove('expanded');
    canvas.width = 400;
    canvas.height = 300;
    
    document.getElementById('expandUniqueBtn').style.display = 'inline-block';
    document.getElementById('contractUniqueBtn').style.display = 'none';
  });
}

// Scenario selection logic
document.getElementById('projectScenario').addEventListener('change', ()=>{
  const scenario = document.getElementById('projectScenario').value;
  const description = document.getElementById('scenarioDescription');
  
  const scenarios = {
    'custom': 'Configure your project manually using the form below.',
    'software': 'Well-defined requirements, <6 months, <7 team members. Optimized for speed and flexibility.',
    'innovative': 'R&D-heavy, uncertain outcomes, ~1 year duration. Balances innovation and stakeholder management.',
    'government': 'Civil, electrical, and IT components, 2-year duration. Comprehensive governance and compliance.'
  };
  
  description.textContent = scenarios[scenario] || '';
  
  // Auto-fill form based on scenario
  if (scenario !== 'custom') {
    const projectType = document.getElementById('projectType');
    const projectSize = document.getElementById('projectSize');
    const industry = document.getElementById('industry');
    const methodologyPreference = document.getElementById('methodologyPreference');
    
    if (scenario === 'software') {
      projectType.value = 'software';
      projectSize.value = 'small';
      industry.value = 'IT';
      methodologyPreference.value = 'PMBOK';
    } else if (scenario === 'innovative') {
      projectType.value = 'research';
      projectSize.value = 'medium';
      industry.value = 'IT';
      methodologyPreference.value = 'PMBOK';
    } else if (scenario === 'government') {
      projectType.value = 'infrastructure';
      projectSize.value = 'large';
      industry.value = 'construction';
      methodologyPreference.value = 'PRINCE2';
    }
  }
});

// Global variable to store current process data for PDF export
let currentProcessData = null;

// Status helpers
function ensureProcessVisible(){
  try {
    const resultsDiv = document.getElementById('processResults');
    if (resultsDiv) {
      resultsDiv.style.display = 'block';
      resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  } catch(_){}
}

function showProcessStatus(message){
  try{
    const recommendationsDiv = document.getElementById('processRecommendations');
    if (recommendationsDiv) recommendationsDiv.innerHTML = `<div class="muted">${message}</div>`;
    ensureProcessVisible();
  }catch(_){ }
}

function showProcessError(message){
  try{
    const recommendationsDiv = document.getElementById('processRecommendations');
    if (recommendationsDiv) recommendationsDiv.innerHTML = `<div class="card" style="border-left:4px solid #e63946;background:rgba(230,57,70,0.08);padding:10px;">${message}</div>`;
    ensureProcessVisible();
  }catch(_){ }
}

// Utilities for references rendering
function mapStandardToKey(std){
  const s = (std||'').toUpperCase();
  if (s.includes('PMBOK')) return 'PMBOK';
  if (s.includes('PRINCE')) return 'PRINCE2';
  if (s.includes('21500')) return 'ISO21500';
  if (s.includes('21502')) return 'ISO21502';
  return null;
}

function escapeHtml(str){
  return String(str||'')
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/\"/g,'&quot;')
    .replace(/'/g,'&#039;');
}

function buildReferencesHtml(refs){
  if (!Array.isArray(refs) || refs.length === 0) return '<div class="muted">No references available.</div>';
  const items = refs.map(r=>{
    const std = r.standard || 'Unknown';
    const page = r.page || '?';
    const score = (typeof r.score === 'number') ? r.score.toFixed(3) : (r.score||'');
    const text = escapeHtml(r.text || '');
    const mapped = mapStandardToKey(std);
    const viewHref = mapped ? `/view?standard=${encodeURIComponent(mapped)}&page=${encodeURIComponent(page)}&text=${encodeURIComponent((r.text||'').slice(0,160))}` : '';
    const pdfHref = r.link ? r.link : (mapped ? `/pdf/${mapped}#page=${page}` : '');
    const linkParts = [];
    if (pdfHref) linkParts.push(`<a href="${pdfHref}" target="_blank">Open PDF</a>`);
    if (viewHref) linkParts.push(`<a href="${viewHref}" target="_blank">Open View</a>`);
    const links = linkParts.join(' · ');
    return `
      <li style="margin-bottom:8px;">
        <strong>${escapeHtml(std)}</strong> · p.${escapeHtml(page)} ${score ? `· sim=${score}` : ''}<br>
        <span class="muted" style="font-size:12px;">${text}</span><br>
        <span>${links}</span>
      </li>`;
  }).join('');
  return `
    <div class="card">
      <h3>📑 Clickable References</h3>
      <ul style="padding-left:18px;">${items}</ul>
    </div>`;
}

// Append a footer line at the end of the displayed process
function appendProcessFooter(containerEl, code, sourceLabel){
  try{
    const footer = document.createElement('div');
    footer.className = 'muted';
    footer.style.marginTop = '10px';
    footer.style.fontSize = '12px';
    const suffix = sourceLabel ? ` | Source: ${sourceLabel}` : '';
    footer.textContent = `— End of process ${code || ''}${suffix}`.trim();
    containerEl.appendChild(footer);
  }catch(_){ /* ignore */ }
}

// Process Generator functionality
document.getElementById('generateProcessBtn').addEventListener('click', async ()=>{
  const projectType = document.getElementById('projectType').value;
  const projectSize = document.getElementById('projectSize').value;
  const industry = document.getElementById('industry').value;
  const methodologyPreference = document.getElementById('methodologyPreference').value;
  
  const resultsDiv = document.getElementById('processResults');
  const recommendationsDiv = document.getElementById('processRecommendations');
  const detailsDiv = document.getElementById('processDetails');
  
  resultsDiv.style.display = 'block';
  recommendationsDiv.innerHTML = '<div class="muted">🤖 Generating AI-powered process recommendations...</div>';
  detailsDiv.innerHTML = '';
  
  // Ensure buttons are visible when results div is shown
  const diagramBtn = document.getElementById('viewDiagramBtn');
  const pdfBtn = document.getElementById('exportPdfBtn');
  const actionContainer = document.getElementById('processActionButtons');
  if (diagramBtn) {
    diagramBtn.style.display = 'inline-block';
    diagramBtn.style.visibility = 'visible';
  }
  if (pdfBtn) {
    pdfBtn.style.display = 'inline-block';
    pdfBtn.style.visibility = 'visible';
  }
  if (actionContainer) {
    actionContainer.style.display = 'flex';
  }
  
  try {
    const url = `/api/process-recommendation?project_type=${encodeURIComponent(projectType)}&project_size=${encodeURIComponent(projectSize)}&industry=${encodeURIComponent(industry)}&methodology_preference=${encodeURIComponent(methodologyPreference)}&use_ai=false`;
    const data = await fetchJSON(url);

    // Check if AI-generated response
    if (data.mode === 'ai_generated' && data.ai_recommendation) {
      const evidence = data.evidence_base || { total_sources: 0, standards_consulted: [] };
      const rawProcess = (data.ai_recommendation && data.ai_recommendation.process) || '';
      const cleanedProcess = sanitizeAIText(rawProcess);
      const formattedContent = formatMarkdown(cleanedProcess);
      
      recommendationsDiv.innerHTML = `
        <div class="card" style="background: linear-gradient(135deg, #1c2541 0%, #0b132b 100%);">
          <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 15px;">
            <span style="font-size: 24px;">🤖</span>
            <div>
              <h3 style="margin: 0;">AI-Generated Process Recommendation</h3>
              <div class="muted" style="font-size: 12px;">
                Powered by GPT-2 AI | Based on ${evidence.total_sources} sources from ${(evidence.standards_consulted||[]).join(', ')}
              </div>
            </div>
          </div>
          <div class="ai-content" style="line-height: 1.7; font-size: 14px;">
            ${formattedContent}
          </div>
        </div>
      `;
      
      // Show standards evidence in details section
      const recommendations = data.recommendations || {};
      if (Object.keys(recommendations).length > 0) {
        detailsDiv.innerHTML = `
          <h3 style="margin-top: 20px;">📚 Evidence from PM Standards</h3>
          <div class="grid">
            ${Object.entries(recommendations).map(([standard, rec]) => `
              <div class="card">
                <h4>${standard}</h4>
                ${rec.processes && rec.processes.length > 0 ? `
                  <div class="muted">${rec.processes.length} sources found</div>
                  <ul style="font-size: 13px;">
                    ${rec.processes.slice(0, 3).map(process => `
                      <li>
                        ${process.description}<br>
                        ${process.link ? `<a href="${process.link}" target="_blank" style="font-size: 12px;">View in ${standard}</a>` : ''}
                      </li>
                    `).join('')}
                  </ul>
                ` : '<div class="muted">No specific sources found</div>'}
              </div>
            `).join('')}
          </div>
        `;
      }
      // Render structured process (phases/activities) and per-step citations if present
      if (data.ai_recommendation.structured) {
        const s = data.ai_recommendation.structured;
        const sc = data.ai_recommendation.step_citations || {};
        const traceRows = [];
        s.phases.forEach((ph, pi) => {
          (ph.activities||[]).forEach(act => {
            const cites = (sc[act.id]||[]).map(c => `${c.standard} p.${c.page}`).join('; ');
            traceRows.push(`<tr><td>${pi+1}. ${ph.title}</td><td>${act.title}</td><td>${cites||'-'}</td></tr>`);
          });
        });
        if (traceRows.length > 0) {
          detailsDiv.insertAdjacentHTML('beforeend', `
            <div class="card" style="margin-top: 16px;">
              <h3>🔗 Traceability (Step → Citations)</h3>
              <div style="overflow:auto">
              <table class="table" style="width:100%; font-size:13px; border-collapse: collapse;">
                <thead><tr><th style="text-align:left;">Phase</th><th style="text-align:left;">Activity</th><th style="text-align:left;">Citations</th></tr></thead>
                <tbody>${traceRows.join('')}</tbody>
              </table>
              </div>
            </div>
          `);
        }
        // Render roles and RACI
        const roles = data.ai_recommendation.roles || [];
        const raci = data.ai_recommendation.raci || {};
        if (roles.length > 0) {
          detailsDiv.insertAdjacentHTML('beforeend', `
            <div class="card" style="margin-top: 16px;">
              <h3>🧑‍🤝‍🧑 Roles</h3>
              <ul>${roles.map(r => `<li>${r}</li>`).join('')}</ul>
            </div>
          `);
        }
        const raciRows = [];
        s.phases.forEach((ph)=>{
          (ph.activities||[]).forEach(act => {
            const entries = raci[act.id] || [];
            const txt = entries.map(e=>`${e.role}:${e.assignment}`).join(', ');
            raciRows.push(`<tr><td>${act.title}</td><td>${txt||'-'}</td></tr>`);
          });
        });
        if (raciRows.length > 0) {
          detailsDiv.insertAdjacentHTML('beforeend', `
            <div class="card" style="margin-top: 16px;">
              <h3>📊 RACI Matrix</h3>
              <table class="table" style="width:100%; font-size:13px; border-collapse: collapse;">
                <thead><tr><th style="text-align:left;">Activity</th><th style="text-align:left;">Assignments</th></tr></thead>
                <tbody>${raciRows.join('')}</tbody>
              </table>
            </div>
          `);
        }
        // Decision Gates
        const gates = data.ai_recommendation.decision_gates || [];
        if (gates.length > 0) {
          detailsDiv.insertAdjacentHTML('beforeend', `
            <div class="card" style="margin-top: 16px;">
              <h3>🚦 Decision Gates</h3>
              <ul>
                ${gates.map(g=>`<li><strong>${g.name}</strong><br><small>Entry: ${(g.entry||[]).join(', ')} | Exit: ${(g.exit||[]).join(', ')}</small></li>`).join('')}
              </ul>
            </div>
          `);
        }
      }
      // Render structured citations if present
      if (Array.isArray(data.ai_recommendation.citations) && data.ai_recommendation.citations.length > 0) {
        const cites = data.ai_recommendation.citations;
        const citationsHTML = `
          <div class="card" style="margin-top: 16px;">
            <h3>📑 Citations</h3>
            <ol>
              ${cites.map(c => `
                <li>
                  <strong>${(c.standard||'').toString()}</strong> p.${c.page||'?'}
                  ${c.link ? ` - <a href="${c.link}" target="_blank">Open</a>` : ''}
                  <div class="muted" style="font-size: 12px;">${(c.excerpt||'').toString().substring(0,160)}${(c.excerpt||'').length>160?'…':''}</div>
                </li>
              `).join('')}
            </ol>
          </div>`;
        detailsDiv.insertAdjacentHTML('beforeend', citationsHTML);
      }
      
      // Remove references section from process text for PDF export
      let processTextForPdf = cleanedProcess || '';
      const referenceMarkers = [
        '\n### Note\n',
        '\n### Note:',
        '\n**Embeddings & Citations Section**',
        '\nEmbeddings & Citations Section',
        '\nEMBEDDING REFERENCES',
        '\nNOTE: Detailed book references',
        '\n-----\n'  // Check if followed by Note/References
      ];
      
      let cutIndex = processTextForPdf.length;
      for (const marker of referenceMarkers) {
        const idx = processTextForPdf.indexOf(marker);
        if (idx !== -1 && idx < cutIndex) {
          const afterMarker = processTextForPdf.substring(idx + marker.length, idx + marker.length + 100).toLowerCase();
          if (afterMarker.includes('ref ') || afterMarker.includes('reference') || 
              afterMarker.includes('citation') || afterMarker.includes('embedding') || 
              afterMarker.includes('note')) {
            cutIndex = idx;
          }
        }
      }
      
      // Also check for "-----" separator pattern
      const dashSepIdx = processTextForPdf.indexOf('\n-----\n');
      if (dashSepIdx !== -1) {
        const afterDash = processTextForPdf.substring(dashSepIdx + 7, dashSepIdx + 50).toLowerCase();
        if (afterDash.includes('note') || afterDash.includes('ref ') || 
            afterDash.includes('reference') || afterDash.includes('citation') || 
            afterDash.includes('embedding')) {
          if (dashSepIdx < cutIndex) {
            cutIndex = dashSepIdx;
          }
        }
      }
      
      if (cutIndex < processTextForPdf.length) {
        processTextForPdf = processTextForPdf.substring(0, cutIndex).trim();
      }
      
      // Store complete process data for PDF export (without references)
      currentProcessData = {
        projectType,
        projectSize,
        industry,
        methodologyPreference,
        processText: processTextForPdf,
        citations: data.ai_recommendation.citations || null,
        evidence: evidence,
        fullRecommendation: data.ai_recommendation,
        completeData: data,
        aiModelAnswer: processTextForPdf, // Store without references for PDF
        rawAiResponse: data.ai_recommendation // Store the raw AI response
      };
      
      // Show diagram and PDF export buttons for AI-generated content
      const diagramBtn = document.getElementById('viewDiagramBtn');
      const pdfBtn = document.getElementById('exportPdfBtn');
      if (diagramBtn) {
        diagramBtn.style.display = 'inline-block';
        diagramBtn.style.visibility = 'visible';
        diagramBtn.onclick = () => {
          const proc = (data.ai_recommendation && data.ai_recommendation.process) || '';
          generateProcessDiagram(proc);
        };
      }
      if (pdfBtn) {
        pdfBtn.style.display = 'inline-block';
        pdfBtn.style.visibility = 'visible';
      }
      return;
    }

    // Fallback (template-based) UI with safe defaults
    const recommendations = data.recommendations || { PMBOK:{processes:[]}, PRINCE2:{processes:[]}, ISO:{processes:[]} };
    const tailored = data.tailored_approach || {
      recommended_approach: 'No recommended approach available',
      process_phases: [],
      key_activities: [],
      critical_deliverables: [],
      tailoring_guidance: [],
      roles: [],
      decision_gates: []
    };

    const evidence = data.evidence_base || { total_sources: 0, standards_consulted: [] };
    recommendationsDiv.innerHTML = `
      <div class="card">
        <h3>🎯 Recommended Approach</h3>
        <p><strong>${tailored.recommended_approach}</strong></p>
        <div class="muted">Based on ${evidence.total_sources} sources from ${(evidence.standards_consulted||[]).join(', ')}</div>
      </div>
      
      <div class="card">
        <h3>📋 Process Phases</h3>
        <ul>
          ${tailored.process_phases.map(phase => `<li>${phase}</li>`).join('')}
        </ul>
      </div>
      
      <div class="card">
        <h3>🔧 Key Activities</h3>
        <ul>
          ${tailored.key_activities.map(activity => `<li>${activity}</li>`).join('')}
        </ul>
      </div>
      
      <div class="card">
        <h3>📄 Critical Deliverables</h3>
        <ul>
          ${tailored.critical_deliverables.map(deliverable => `<li>${deliverable}</li>`).join('')}
        </ul>
      </div>

      <div class="card">
        <h3>🧑‍🤝‍🧑 Roles</h3>
        <ul>
          ${(tailored.roles||[]).map(role => `<li>${role}</li>`).join('')}
        </ul>
      </div>

      <div class="card">
        <h3>🚦 Decision Gates</h3>
        <ul>
          ${(tailored.decision_gates||[]).map(g => `<li><strong>${g.name}</strong><br><small>Entry: ${(g.entry||[]).join(', ')} | Exit: ${(g.exit||[]).join(', ')}</small></li>`).join('')}
        </ul>
      </div>
    `;

    detailsDiv.innerHTML = `
      <h3>📚 Standards-Based Recommendations</h3>
      <div class="grid">
        ${Object.entries(recommendations).map(([standard, rec]) => `
          <div class="card">
            <h4>${standard}</h4>
            ${rec.processes.length > 0 ? `
              <div class="muted">${rec.processes.length} processes found</div>
              <ul>
                ${rec.processes.slice(0, 3).map(process => `
                  <li>
                    <strong>${process.name}</strong><br>
                    <small>${process.description}</small><br>
                    ${process.link ? `<a href="${process.link}" target="_blank">View in ${standard}</a>` : ''}
                  </li>
                `).join('')}
              </ul>
            ` : '<div class="muted">No specific processes found</div>'}
          </div>
        `).join('')}
      </div>
      
      <div class="card">
        <h3>🎨 Tailoring Guidance</h3>
        <ul>
          ${tailored.tailoring_guidance.map(guidance => `<li>${guidance}</li>`).join('')}
        </ul>
      </div>
    `;
    
    // Show diagram and PDF export buttons for template-based results
    const diagramBtn = document.getElementById('viewDiagramBtn');
    const pdfBtn = document.getElementById('exportPdfBtn');
    if (diagramBtn) {
      diagramBtn.style.display = 'inline-block';
      diagramBtn.style.visibility = 'visible';
    }
    if (pdfBtn) {
      pdfBtn.style.display = 'inline-block';
      pdfBtn.style.visibility = 'visible';
    }
    
    // Store process data for diagram and PDF export
    const templateProcessText = [
      `Recommended Approach: ${tailored.recommended_approach}`,
      '',
      'Process Phases:',
      ...tailored.process_phases.map((p, i) => `${i+1}. ${p}`),
      '',
      'Key Activities:',
      ...tailored.key_activities.map((a, i) => `- ${a}`),
      '',
      'Critical Deliverables:',
      ...tailored.critical_deliverables.map((d, i) => `- ${d}`),
      '',
      'Roles:',
      ...tailored.roles.map((r, i) => `- ${r}`),
      '',
      'Decision Gates:',
      ...tailored.decision_gates.map((g, i) => `${i+1}. ${g}`)
    ].join('\n');
    
    currentProcessData = {
      projectType,
      projectSize,
      industry,
      methodologyPreference,
      processText: templateProcessText,
      citations: null,
      evidence: evidence,
      fullRecommendation: null,
      completeData: data,
      aiModelAnswer: templateProcessText
    };
    
    // Set up diagram button for template-based results
    if (diagramBtn) {
      diagramBtn.onclick = () => {
        generateProcessDiagram(templateProcessText);
      };
    }
    
  } catch(e) {
    recommendationsDiv.innerHTML = `<div class="muted">Error: ${e.message}</div>`;
  }
  // Footer for template-based results
  appendProcessFooter(recommendationsDiv, '', 'Template');
});

// Reusable function to fetch+display by code
async function fetchAndDisplayByCode(code){
  const resultsDiv = document.getElementById('processResults');
  const recommendationsDiv = document.getElementById('processRecommendations');
  const detailsDiv = document.getElementById('processDetails');
  resultsDiv.style.display = 'block';
  showProcessStatus('📄 Fetching process from files…');
  detailsDiv.innerHTML = '';
  
  // Ensure buttons are visible when results div is shown
  const diagramBtn = document.getElementById('viewDiagramBtn');
  const pdfBtn = document.getElementById('exportPdfBtn');
  const actionContainer = document.getElementById('processActionButtons');
  if (diagramBtn) {
    diagramBtn.style.display = 'inline-block';
    diagramBtn.style.visibility = 'visible';
  }
  if (pdfBtn) {
    pdfBtn.style.display = 'inline-block';
    pdfBtn.style.visibility = 'visible';
  }
  if (actionContainer) {
    actionContainer.style.display = 'flex';
  }

  try{
    const url = window.location.origin + `/api/process-by-id?code=${encodeURIComponent(code)}`;
    const data = await fetchJSONWithTimeout(url, undefined, 15000);
    if(data.error){
      showProcessError(`Error: ${data.error}`);
      return;
    }
    const src = data.source === 'response' ? 'Without Embeddings' : 'With Embeddings';
    const refs = (data.references && data.references.references) ? data.references.references : (data.references || []);
    const refsHtml = buildReferencesHtml(refs);
    recommendationsDiv.innerHTML = `
      <div class="card">
        <h3>Process ${code} <span class="muted" style="font-size:12px;">(${src})</span></h3>
        <div style="white-space: pre-wrap;">${data.text}</div>
      </div>
    `;
    detailsDiv.innerHTML = refsHtml;
    try { resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' }); } catch (_) {}
    
    // Always show buttons when process results are displayed
    const diagramBtn = document.getElementById('viewDiagramBtn');
    const pdfBtn = document.getElementById('exportPdfBtn');
    if (diagramBtn) {
      diagramBtn.style.display = 'inline-block';
      diagramBtn.style.visibility = 'visible';
    }
    if (pdfBtn) {
      pdfBtn.style.display = 'inline-block';
      pdfBtn.style.visibility = 'visible';
    }
    
    try {
      // Remove references section from process text for PDF export
      let processTextForPdf = data.text || '';
      const referenceMarkers = [
        '\n### Note\n',
        '\n### Note:',
        '\n**Embeddings & Citations Section**',
        '\nEmbeddings & Citations Section',
        '\nEMBEDDING REFERENCES',
        '\nNOTE: Detailed book references',
        '\n-----\n'
      ];
      
      let cutIndex = processTextForPdf.length;
      for (const marker of referenceMarkers) {
        const idx = processTextForPdf.indexOf(marker);
        if (idx !== -1 && idx < cutIndex) {
          const afterMarker = processTextForPdf.substring(idx + marker.length, idx + marker.length + 100).toLowerCase();
          if (afterMarker.includes('ref ') || afterMarker.includes('reference') || 
              afterMarker.includes('citation') || afterMarker.includes('embedding') || 
              afterMarker.includes('note')) {
            cutIndex = idx;
          }
        }
      }
      
      // Also check for "-----" separator pattern
      const dashSepIdx = processTextForPdf.indexOf('\n-----\n');
      if (dashSepIdx !== -1) {
        const afterDash = processTextForPdf.substring(dashSepIdx + 7, dashSepIdx + 50).toLowerCase();
        if (afterDash.includes('note') || afterDash.includes('ref ') || 
            afterDash.includes('reference') || afterDash.includes('citation') || 
            afterDash.includes('embedding')) {
          if (dashSepIdx < cutIndex) {
            cutIndex = dashSepIdx;
          }
        }
      }
      
      if (cutIndex < processTextForPdf.length) {
        processTextForPdf = processTextForPdf.substring(0, cutIndex).trim();
      }
      
      // Set up diagram button
      if (diagramBtn) {
        diagramBtn.style.display = 'inline-block';
        diagramBtn.style.visibility = 'visible';
        diagramBtn.onclick = () => {
          generateProcessDiagram(data.text); // Use full text for diagram
        };
      }
      // Set up PDF button
      if (pdfBtn) {
        pdfBtn.style.display = 'inline-block';
        pdfBtn.style.visibility = 'visible';
      }
      
      // Store process data for PDF export (without references)
      currentProcessData = {
        projectType: 'Unknown',
        projectSize: 'Unknown',
        industry: 'Unknown',
        methodologyPreference: 'Unknown',
        processText: processTextForPdf,
        citations: refs,
        evidence: { total_sources: refs.length, standards_consulted: [] },
        fullRecommendation: null,
        completeData: data,
        aiModelAnswer: processTextForPdf // Store without references for PDF
      };
    } catch (_) {}
    // Footer for file-based fetch
    appendProcessFooter(recommendationsDiv, code, src);
  }catch(e){
    showProcessError(`Error: ${e.message}`);
  }
}

// Robust handler attachment for Fetch by Code
let _fetchByCodeHandler = null;
function deriveCodeFromForm(){
  const manualEl = document.getElementById('processCode');
  const manual = (manualEl && manualEl.value) ? manualEl.value.trim() : '';
  if (/^\d{5}$/.test(manual)) {
    return manual;
  }
  const scenarioVal = document.getElementById('projectScenario')?.value;
  const typeVal = document.getElementById('projectType')?.value;
  const sizeVal = document.getElementById('projectSize')?.value;
  const industryVal = document.getElementById('industry')?.value;
  const methodologyVal = document.getElementById('methodologyPreference')?.value;
  const scenarioMap = { custom: '1', software: '2', innovative: '3', government: '4' };
  const typeMap = { software: '1', construction: '2', research: '3', marketing: '4', infrastructure: '5' };
  const sizeMap = { small: '1', medium: '2', large: '3' };
  const industryMap = { IT: '1', construction: '2', healthcare: '3', finance: '4', education: '5' };
  const methodologyMap = { PMBOK: '1', PRINCE2: '2', ISO: '3' };
  const d1 = scenarioMap[scenarioVal];
  const d2 = typeMap[typeVal];
  const d3 = sizeMap[sizeVal];
  const d4 = industryMap[industryVal];
  const d5 = methodologyMap[methodologyVal];
  if(d1 && d2 && d3 && d4 && d5){ return `${d1}${d2}${d3}${d4}${d5}`; }
  return null;
}

function attachFetchByCodeHandler(){
  const btn = document.getElementById('fetchProcessByCodeBtn');
  const codeInput = document.getElementById('processCode');
  const statusEl = document.getElementById('fetchStatus');
  if(!btn){ showProcessStatus('Fetch button not available.'); return; }
  if (_fetchByCodeHandler) btn.removeEventListener('click', _fetchByCodeHandler);
  _fetchByCodeHandler = async ()=>{
    const original = btn.textContent;
    try{
      btn.disabled = true; btn.setAttribute('aria-busy','true'); btn.textContent = 'Fetching…';
      if (statusEl) statusEl.textContent = 'Validating code…';
      // Validate manual entry if present
      const manual = (codeInput && codeInput.value) ? codeInput.value.trim() : '';
      if (manual && !/^\d{5}$/.test(manual)) {
        showProcessError('Please enter a valid 5-digit code (e.g., 11111) or clear the field to derive from selections.');
        if (statusEl) statusEl.textContent = 'Invalid code. Expect 5 digits (e.g., 11111).';
        return;
      }
      const code = deriveCodeFromForm();
      if(!code){ showProcessError('Cannot derive code from selections. Please fill all fields.'); return; }
      if (statusEl) statusEl.textContent = `Code: ${code} — Getting info…`;
      await fetchAndDisplayByCode(code);
      if (statusEl) statusEl.textContent = `Code: ${code} — Loaded.`;
    } catch(e){
      showProcessError(`Error: ${e.message}`);
      if (statusEl) statusEl.textContent = '';
    } finally {
      btn.disabled = false; btn.setAttribute('aria-busy','false'); btn.textContent = original;
    }
  };
  btn.addEventListener('click', _fetchByCodeHandler);

  // Enter key on code input triggers fetch
  if (codeInput) {
    codeInput.addEventListener('keydown', (ev)=>{
      if (ev.key === 'Enter') {
        ev.preventDefault();
        btn.click();
      }
    });
  }
}

document.addEventListener('DOMContentLoaded', attachFetchByCodeHandler);

// Global error surfacing to avoid silent failures
window.addEventListener('error', (e)=>{
  try {
    showProcessError(`Runtime error: ${e.message || 'Unknown error'}`);
  } catch(_){ }
});

// Demo: if URL has ?demo=11111, auto-load that code and set form accordingly
document.addEventListener('DOMContentLoaded', ()=>{
  const params = new URLSearchParams(window.location.search);
  const demo = params.get('demo');
  if(demo && /^\d{5}$/.test(demo)){
    // Set form by digits
    const [d1,d2,d3,d4,d5] = demo.split('');
    const scenarioRev = { '1':'custom','2':'software','3':'innovative','4':'government' };
    const typeRev = { '1':'software','2':'construction','3':'research','4':'marketing','5':'infrastructure' };
    const sizeRev = { '1':'small','2':'medium','3':'large' };
    const industryRev = { '1':'IT','2':'construction','3':'healthcare','4':'finance','5':'education' };
    const methodologyRev = { '1':'PMBOK','2':'PRINCE2','3':'ISO' };
    try{
      document.getElementById('projectScenario').value = scenarioRev[d1] || 'custom';
      document.getElementById('projectType').value = typeRev[d2] || 'software';
      document.getElementById('projectSize').value = sizeRev[d3] || 'small';
      document.getElementById('industry').value = industryRev[d4] || 'IT';
      document.getElementById('methodologyPreference').value = methodologyRev[d5] || 'PMBOK';
    }catch(_){ }
    fetchAndDisplayByCode(demo);
  }
});

// PDF Export functionality
document.getElementById('exportPdfBtn').addEventListener('click', async () => {
  const projectType = document.getElementById('projectType').value;
  const projectSize = document.getElementById('projectSize').value;
  const industry = document.getElementById('industry').value;
  const methodologyPreference = document.getElementById('methodologyPreference').value;
  const scenarioDescription = document.getElementById('scenarioDescription').textContent;

  try {
    // Show loading state
    const exportBtn = document.getElementById('exportPdfBtn');
    const originalText = exportBtn.textContent;
    exportBtn.textContent = '📄 Generating PDF...';
    exportBtn.disabled = true;

    // Enhanced data extraction - always try to get data from displayed content
    let processText = '';
    let citationsJson = '';
    let aiModelAnswer = '';

    // First priority: Use stored process data if available
    if (currentProcessData) {
      console.log('Using stored currentProcessData for PDF');
      processText = currentProcessData.processText || '';
      aiModelAnswer = currentProcessData.aiModelAnswer ||
                     currentProcessData.rawAiResponse?.process ||
                     currentProcessData.completeData?.ai_recommendation?.process || '';

      if (currentProcessData.citations) {
        citationsJson = JSON.stringify(currentProcessData.citations);
      }

      // Add additional process details for comprehensive PDF
      const additionalDetails = [];
      if (currentProcessData.evidence) {
        additionalDetails.push(`Evidence Base: ${currentProcessData.evidence.total_sources} sources from ${(currentProcessData.evidence.standards_consulted || []).join(', ')}`);
      }
      if (currentProcessData.fullRecommendation) {
        const rec = currentProcessData.fullRecommendation;
        if (rec.justification) {
          additionalDetails.push(`Justification: ${rec.justification}`);
        }
        if (rec.recommendations) {
          additionalDetails.push(`Recommendations: ${rec.recommendations}`);
        }
      }

      if (additionalDetails.length > 0) {
        processText += '\n\n' + additionalDetails.join('\n');
      }
    }

    // Second priority: Extract from displayed DOM content if no stored data
    if (!processText.trim()) {
      console.log('Extracting data from DOM for PDF');

      // Get process text from recommendations section
      const processRecommendations = document.getElementById('processRecommendations');
      if (processRecommendations) {
        const recText = processRecommendations.textContent || processRecommendations.innerText || '';
        // Remove any UI elements from the text
        processText = recText.replace(/🤖|📊|📄|View Flowchart|Export Process Document|Generating AI-powered|Powered by GPT-2 AI|Based on \d+ sources/gi, '').trim();
        aiModelAnswer = processText;
      }

      // Get additional details from process details section
      const processDetails = document.getElementById('processDetails');
      if (processDetails) {
        const detailsText = processDetails.textContent || processDetails.innerText || '';
        if (detailsText.trim()) {
          processText += '\n\nReferences:\n' + detailsText.trim();
        }
      }

      // Try to extract citations if available
      const citationsSection = document.querySelector('[id*="citation"], [class*="citation"], .references');
      if (citationsSection) {
        const citationsData = {
          used_references: [],
          justification: 'Process based on PM standards'
        };
        citationsJson = JSON.stringify(citationsData);
      }
    }

    // Validate that we have content to generate PDF
    if (!processText.trim() && !aiModelAnswer.trim()) {
      throw new Error('No process content found. Please generate or fetch a process first.');
    }

    // Ensure we have at least basic process text
    if (!processText.trim()) {
      processText = aiModelAnswer || `Generated process for ${projectSize} ${projectType} project in ${industry} industry using ${methodologyPreference} methodology.`;
    }

    console.log('PDF generation data:', {
      hasProcessText: !!processText.trim(),
      hasAiModelAnswer: !!aiModelAnswer.trim(),
      hasCitations: !!citationsJson,
      projectType, projectSize, industry
    });

    // Build JSON payload for POST (avoids URL size limits)
    let citationsPayload = null;
    try {
      citationsPayload = citationsJson ? JSON.parse(citationsJson) : null;
    } catch (_) { citationsPayload = null; }

    const payload = {
      project_type: projectType,
      project_size: projectSize,
      industry: industry,
      methodology_preference: methodologyPreference,
      scenario_description: scenarioDescription,
      process_text: processText,
      ai_model_answer: aiModelAnswer,
      citations: citationsPayload,
      evidence_base: currentProcessData?.evidence || null
    };

    // Make POST request to PDF export endpoint
    let response = await fetch('/api/export-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      // Log and attempt a safe GET fallback with truncated text
      const errorText = await response.text();
      console.warn('PDF POST failed, falling back to GET. Error:', errorText);
      const fallbackParams = new URLSearchParams({
        project_type: projectType,
        project_size: projectSize,
        industry: industry,
        methodology_preference: methodologyPreference,
        scenario_description: scenarioDescription,
        process_text: (processText || '').slice(0, 1800),
        citations_json: citationsJson || '',
        ai_model_answer: (aiModelAnswer || '').slice(0, 1800)
      });
      response = await fetch(`/api/export-pdf?${fallbackParams}`);
      if (!response.ok) {
        const err2 = await response.text();
        throw new Error(`PDF generation failed: ${response.statusText} - ${err2}`);
      }
    }

    // Get the PDF blob
    let pdfBlob;
    try {
      pdfBlob = await response.blob();
    } catch (blobErr) {
      console.error('Blob conversion failed, opening direct download as fallback:', blobErr);
      // Final fallback with GET and truncated text to avoid URL size issues
      const fallbackParams = new URLSearchParams({
        project_type: projectType,
        project_size: projectSize,
        industry: industry,
        methodology_preference: methodologyPreference,
        scenario_description: scenarioDescription,
        process_text: (processText || '').slice(0, 1800),
        citations_json: citationsJson || '',
        ai_model_answer: (aiModelAnswer || '').slice(0, 1800)
      });
      window.open(`/api/export-pdf?${fallbackParams}`, '_blank');
      exportBtn.textContent = originalText;
      exportBtn.disabled = false;
      return;
    }

    // Fallback if blob is empty
    if (!pdfBlob || !pdfBlob.size) {
      console.warn('Empty PDF blob, opening direct download as fallback');
      const fallbackParams = new URLSearchParams({
        project_type: projectType,
        project_size: projectSize,
        industry: industry,
        methodology_preference: methodologyPreference,
        scenario_description: scenarioDescription,
        process_text: (processText || '').slice(0, 1800),
        citations_json: citationsJson || '',
        ai_model_answer: (aiModelAnswer || '').slice(0, 1800)
      });
      window.open(`/api/export-pdf?${fallbackParams}`, '_blank');
      exportBtn.textContent = originalText;
      exportBtn.disabled = false;
      return;
    }

    // Create download link
    const url = window.URL.createObjectURL(pdfBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `process_recommendation_${projectType}_${projectSize}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);

    // Show success message
    exportBtn.textContent = '✅ PDF Downloaded!';
    setTimeout(() => {
      exportBtn.textContent = originalText;
      exportBtn.disabled = false;
    }, 2000);

  } catch (error) {
    console.error('PDF export failed:', error);
    alert(`PDF export failed: ${error.message}`);

    // Reset button
    const exportBtn = document.getElementById('exportPdfBtn');
    exportBtn.textContent = '📄 Export Process Document (PDF)';
    exportBtn.disabled = false;
  }
});

// Initialize graph expansion functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', setupGraphExpansion);

// Optionally auto-run when tab opens if desired



// Summary generation with progress
document.addEventListener('DOMContentLoaded', ()=>{
  const btn = document.getElementById('generateSummaryBtn');
  if(!btn) return;
  btn.addEventListener('click', async ()=>{
    const std = document.getElementById('summaryStandard').value;
    const out = document.getElementById('summaryOutput');
    const prog = document.getElementById('summaryProgress');
    const fill = document.getElementById('summaryProgressFill');
    const text = document.getElementById('summaryProgressText');
    const status = document.getElementById('summaryProgressStatus');
    
    if(!std){
      alert('Please select a standard');
      return;
    }
    
    btn.disabled = true;
    out.innerHTML = '';
    prog.style.display = 'block';
    fill.style.width = '0%';
    text.textContent = '0%';
    status.textContent = 'Initializing AI…';
    
    let progress = 0;
    const steps = [15, 35, 55, 75, 90];
    let stepIndex = 0;
    const timer = setInterval(()=>{
      if(stepIndex < steps.length){
        progress = steps[stepIndex++];
        fill.style.width = progress + '%';
        text.textContent = progress + '%';
        const msgs = ['Initializing AI…','Loading content…','Analyzing with Gemini AI…','Structuring summary…','Finalizing…'];
        status.textContent = msgs[Math.min(stepIndex-1, msgs.length-1)];
      }
    }, 800);
    
    try{
      const data = await fetchJSON(`/api/summary?standard=${encodeURIComponent(std)}&use_ai=true`);
      clearInterval(timer);
      fill.style.width = '100%';
      text.textContent = '100%';
      status.textContent = 'Done';
      prog.style.display = 'none';
      
      // Display summary (plain text, no markdown)
      const aiPowered = data.ai_powered ? '🤖 AI-Powered (GPT-2)' : '📝 Template-Based';
      const header = `
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #2c355a;">
          <span style="font-size: 20px;">📚</span>
          <div style="flex: 1;">
            <div><strong>${data.standard} Summary</strong></div>
            <div class="muted" style="font-size: 12px;">${aiPowered} | Based on ${data.sources_count} source sections</div>
          </div>
        </div>
      `;
      
      out.innerHTML = header + `<div style="line-height: 1.8; padding: 15px; background: rgba(255,255,255,0.03); border-radius: 8px;">${data.summary}</div>`;
    }catch(e){
      clearInterval(timer);
      prog.style.display = 'none';
      out.innerHTML = `<div class="muted">Error: ${e.message}</div>`;
    }finally{
      btn.disabled = false;
    }
  });
});

// ==================== BOOKMARK EVENT LISTENERS ====================
// Clear all bookmarks
document.getElementById('clearAllBookmarksBtn').addEventListener('click', () => {
  bookmarkManager.clearAll();
});

// Export bookmarks
document.getElementById('exportBookmarksBtn').addEventListener('click', () => {
  bookmarkManager.exportBookmarks();
});

// Filter bookmarks by standard
document.getElementById('bookmarkFilterStandard').addEventListener('change', (e) => {
  bookmarkManager.updateBookmarksDisplay(e.target.value);
});

// Update bookmarks display when bookmarks tab is clicked
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    if (btn.getAttribute('data-tab') === 'bookmarks') {
      bookmarkManager.updateBookmarksDisplay();
    }
  });
});

// Process Diagram functionality
function stripReferencesFromText(text){
  if (!text) return '';
  let t = String(text);
  // Remove bracketed reference groups like [Ref 5, Ref 9]
  t = t.replace(/\[\s*Ref[^\]]*\]/gi, '');
  // Remove inline "Ref 7" or "Ref 5, Ref 9"
  t = t.replace(/Ref\s*\d+(\s*,\s*Ref\s*\d+)*/gi, '');
  // Remove similarity annotations
  t = t.replace(/\(\s*Similarity:\s*[^)]+\)/gi, '');
  // Remove metadata / embeddings lines entirely
  const dropLineRegex = /^(Ref\s*\d+\s*:.*|Generated with embeddings.*|Embedding Sources:.*|[-]{3,}|\s*###\s*Note.*|\s*\*\*Embeddings\s*&\s*Citations.*|EMBEDDING REFERENCES.*)$/i;
  t = t.split('\n').filter(line => !dropLineRegex.test(line.trim())).join('\n');
  // Collapse extra spaces
  t = t.replace(/\s{2,}/g, ' ').replace(/\s*:\s*$/gm, ':');
  return t;
}

// Build a simple project flow from text; if not found, return a standard flow
function buildSimpleStages(processText){
  const t = (processText || '').toLowerCase();
  const stages = [];
  const pushOnce = (label)=>{ if(!stages.includes(label)) stages.push(label); };
  // Keyword mappings
  if (/(initiat|starting up|start\s*(the)?\s*project)/i.test(processText)) pushOnce('Project Initiation');
  if (/(plan|planning)/i.test(processText)) pushOnce('Project Planning');
  if (/(execute|execution|develop|development|build|implement)/i.test(processText)) pushOnce('Development');
  if (/(test|qa|quality assurance|validate|verification|validation)/i.test(processText)) pushOnce('Testing');
  if (/(deploy|release|go[-\s]?live|implementation)/i.test(processText)) pushOnce('Deployment');
  if (/(monitor|control|track|report)/i.test(processText)) pushOnce('Monitoring & Control');
  if (/(close|closure|lessons learned|final acceptance)/i.test(processText)) pushOnce('Project Closure');
  // Fallback default order if too few detected
  const defaults = ['Project Initiation','Project Planning','Development','Testing','Deployment','Project Closure'];
  if (stages.length < 3){
    return defaults;
  }
  // Ensure canonical order based on defaults
  const order = new Map(defaults.map((n,i)=>[n,i]));
  return stages.sort((a,b)=>(order.get(a) ?? 999) - (order.get(b) ?? 999));
}

function buildMermaidFromStages(stages){
  // Force vertical top-to-bottom
  let code = '%%{init: {"flowchart": {"defaultRenderer": "elk", "nodeSpacing": 50, "rankSpacing": 100, "htmlLabels": true}} }%%\n';
  code += 'graph TB\n';
  code += '  classDef phaseNode fill:#e94560,stroke:#c73650,stroke-width:2px,color:#1a1a2e;\n';
  // Create nodes and connect sequentially
  stages.forEach((name, idx)=>{
    const id = `S${idx+1}`;
    const label = String(name).replace(/\"/g,'\\"');
    code += `  ${id}["${label}"]\n`;
    code += `  class ${id} phaseNode\n`;
    if (idx > 0) {
      code += `  S${idx} --> ${id}\n`;
    }
  });
  return code;
}

function generateProcessDiagram(processText) {
  const safeText = typeof processText === 'string' ? processText : (processText?.toString?.() || '');
  const modal = document.getElementById('diagramModal');
  const container = document.getElementById('diagramContainer');
  const downloadBtn = document.getElementById('downloadDiagram');
  
  modal.style.display = 'flex';
  container.innerHTML = '<div class="muted">Generating diagram...</div>';
  if (downloadBtn) downloadBtn.disabled = true;
  
  try {
    // Clean out references and metadata, then build simple stage flow
    const textForDiagram = stripReferencesFromText(safeText);
    const stages = buildSimpleStages(textForDiagram);
    const mermaidCode = buildMermaidFromStages(stages);
    
    container.innerHTML = `
      <div class="mermaid">
        ${mermaidCode}
      </div>
    `;
    
    // Initialize Mermaid
    mermaid.initialize({ 
      startOnLoad: true,
      theme: 'default',
      flowchart: { useMaxWidth: true, htmlLabels: true, nodeSpacing: 50, rankSpacing: 100, curve: 'basis' }
    });
    
    const mermaidElement = container.querySelector('.mermaid');
    if (mermaidElement) {
      mermaid.init(undefined, mermaidElement).then(() => {
        setTimeout(() => { if (downloadBtn) downloadBtn.disabled = false; }, 500);
      }).catch((err) => {
        console.error('Mermaid rendering error:', err);
        container.innerHTML = `<div class=\"muted\">Error rendering diagram: ${err.message}</div>`;
        if (downloadBtn) downloadBtn.disabled = true;
      });
    } else {
      container.innerHTML = `<div class=\"muted\">Error: Could not create diagram element</div>`;
      if (downloadBtn) downloadBtn.disabled = true;
    }
  } catch (error) {
    container.innerHTML = `<div class=\"muted\">Error generating diagram: ${error.message}</div>`;
    if (downloadBtn) downloadBtn.disabled = true;
  }
}

// Modal event handlers
document.getElementById('closeDiagram').addEventListener('click', () => {
  document.getElementById('diagramModal').style.display = 'none';
});

document.getElementById('closeDiagramBtn').addEventListener('click', () => {
  document.getElementById('diagramModal').style.display = 'none';
});

document.getElementById('downloadDiagram').addEventListener('click', async () => {
  const svg = document.querySelector('#diagramContainer .mermaid svg');
  if (!svg) {
    alert('Diagram not available. Please generate a process first.');
    return;
  }
  
  try {
    // Get SVG data
    const svgData = new XMLSerializer().serializeToString(svg);
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml' });
    
    // Create download link for SVG
    const svgUrl = URL.createObjectURL(svgBlob);
    const svgLink = document.createElement('a');
    svgLink.href = svgUrl;
    svgLink.download = 'process-diagram.svg';
    document.body.appendChild(svgLink);
    svgLink.click();
    document.body.removeChild(svgLink);
    URL.revokeObjectURL(svgUrl);
    
    // Also try to download as PNG
    try {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      const img = new Image();
      
      const svgUrl2 = URL.createObjectURL(svgBlob);
      img.onload = () => {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);
        canvas.toBlob((pngBlob) => {
          const pngUrl = URL.createObjectURL(pngBlob);
          const pngLink = document.createElement('a');
          pngLink.href = pngUrl;
          pngLink.download = 'process-diagram.png';
          document.body.appendChild(pngLink);
          pngLink.click();
          document.body.removeChild(pngLink);
          URL.revokeObjectURL(pngUrl);
          URL.revokeObjectURL(svgUrl2);
        }, 'image/png');
      };
      img.onerror = () => {
        URL.revokeObjectURL(svgUrl2);
      };
      img.src = svgUrl2;
    } catch (pngError) {
      console.log('PNG conversion failed, SVG downloaded:', pngError);
    }
  } catch (error) {
    alert(`Error downloading diagram: ${error.message}`);
  }
});

// View Diagram Button Click Handler
document.getElementById('viewDiagramBtn').addEventListener('click', () => {
  // Get the current process text from the displayed results
  const processRecommendations = document.getElementById('processRecommendations');
  const processDetails = document.getElementById('processDetails');

  let processText = '';
  if (processRecommendations) {
    processText += processRecommendations.textContent || processRecommendations.innerText || '';
  }
  if (processDetails) {
    processText += '\n' + (processDetails.textContent || processDetails.innerText || '');
  }

  // If we have stored process data, use that instead
  if (currentProcessData && currentProcessData.processText) {
    processText = currentProcessData.processText;
  }

  if (processText.trim()) {
    generateProcessDiagram(processText);
  } else {
    alert('No process text available to generate diagram. Please generate a process first.');
  }
});

// Close modal when clicking outside
document.getElementById('diagramModal').addEventListener('click', (e) => {
  if (e.target === document.getElementById('diagramModal')) {
    document.getElementById('diagramModal').style.display = 'none';
  }
});

// Multiple PDF upload handler
(function(){
  const uploadBtn = document.getElementById('uploadPdfsBtn');
  const fileInput = document.getElementById('pdfFiles');
  const statusEl = document.getElementById('uploadStatus');
  const resultsEl = document.getElementById('uploadResults');
  if (!uploadBtn || !fileInput) return;

  uploadBtn.addEventListener('click', async ()=>{
    try{
      resultsEl.style.display = 'none';
      resultsEl.textContent = '';
      const files = fileInput.files;
      if (!files || files.length === 0){
        statusEl.textContent = 'Please select one or more PDF files.';
        return;
      }
      statusEl.textContent = `Uploading ${files.length} file(s)...`;
      uploadBtn.disabled = true;

      const form = new FormData();
      for (let i=0;i<files.length;i++){
        const f = files[i];
        if (!f.name.toLowerCase().endsWith('.pdf')){
          continue; // skip non-pdf
        }
        form.append('files', f, f.name);
      }

      const res = await fetch('/api/upload-pdfs', { method: 'POST', body: form });
      if (!res.ok){
        const txt = await res.text();
        throw new Error(txt || res.statusText);
      }
      const data = await res.json();
      statusEl.textContent = `Uploaded ${data.saved_count} file(s). ${data.skipped_count>0? (data.skipped_count+ ' skipped.') : ''}`;
      const savedLines = (data.saved||[]).map(s=>`• ${s.file} → ${s.saved_as} (${s.size} bytes)`);
      const skippedLines = (data.skipped||[]).map(s=>`• ${s.file}: ${s.reason}`);
      const report = [
        savedLines.length? ('Saved:\n' + savedLines.join('\n')) : 'Saved:\n(none)',
        skippedLines.length? ('\n\nSkipped:\n' + skippedLines.join('\n')) : ''
      ].join('');
      resultsEl.textContent = report;
      resultsEl.style.display = 'block';
    }catch(e){
      statusEl.textContent = `Upload failed: ${e.message}`;
    }finally{
      uploadBtn.disabled = false;
    }
  });
})();

// Run Add-Book orchestrator handler
(function(){
  const btn = document.getElementById('runAddBookBtn');
  const dry = document.getElementById('addBookDryRun');
  const statusEl = document.getElementById('runAddBookStatus');
  const outEl = document.getElementById('runAddBookOutput');
  if (!btn) return;

  btn.addEventListener('click', async ()=>{
    try{
      statusEl.textContent = 'Running add_book.py... This may take several minutes.';
      outEl.style.display = 'none'; outEl.textContent='';
      btn.disabled = true;

      const params = new URLSearchParams({
        dry_run: dry && dry.checked ? 'true' : 'false',
        api_base: window.location.origin
      });
      const res = await fetch(`/api/run-add-book?${params.toString()}`, { method: 'POST' });
      if (!res.ok){
        const txt = await res.text();
        throw new Error(txt || res.statusText);
      }
      const data = await res.json();
      statusEl.textContent = `Completed with code ${data.returncode}`;
      const combined = [
        data.stdout ? `STDOUT:\n${data.stdout}` : 'STDOUT: (empty)',
        data.stderr ? `\n\nSTDERR:\n${data.stderr}` : '\n\nSTDERR: (empty)'
      ].join('');
      outEl.textContent = combined;
      outEl.style.display = 'block';
    }catch(e){
      statusEl.textContent = `Run failed: ${e.message}`;
    }finally{
      btn.disabled = false;
    }
  });
})();