async function fetchJSON(url){
	const res = await fetch(url);
	if(!res.ok) throw new Error(await res.text());
	return res.json();
}

function drawScatterInteractive(canvas, points, color){
	const ctx = canvas.getContext('2d');
	ctx.clearRect(0,0,canvas.width,canvas.height);
	let xs = points.map(p=>p.x), ys = points.map(p=>p.y);
	const minX = Math.min(...xs, -1), maxX = Math.max(...xs, 1);
	const minY = Math.min(...ys, -1), maxY = Math.max(...ys, 1);
	const pad = 24;
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
		const hit = screenPoints.find(p=>{
			const dx = p.sx - mx, dy = p.sy - my; return dx*dx + dy*dy <= 9*1.5; // radius^2 with tolerance
		});
		if(hit){
			const url = `/view?standard=${encodeURIComponent(hit.standard)}&page=${encodeURIComponent(hit.page)}&text=${encodeURIComponent(hit.text)}`;
			window.open(url, '_blank');
		}
	};
}

// Utility: safe data normalization for points
function normalizePoints(points){
    if(!Array.isArray(points)) return [];
    return points
        .filter(p=>p && typeof p==='object')
        .map(p=>({
            x: Number.isFinite(p.x) ? p.x : 0,
            y: Number.isFinite(p.y) ? p.y : 0,
            label: typeof p.label==='string' ? p.label : '',
            standard: p.standard || 'Unknown',
            page: p.page || 0,
            text: typeof p.text==='string' ? p.text : ''
        }));
}

// Retry helper with exponential backoff
async function retry(fn, {retries=2, baseDelayMs=400}={}){
    let attempt = 0; let lastErr;
    while(attempt <= retries){
        try{ return await fn(); }
        catch(err){ lastErr = err; }
        const delay = baseDelayMs * Math.pow(2, attempt++);
        await new Promise(r=>setTimeout(r, delay));
    }
    throw lastErr;
}

function showLegendError(message, withRetry){
    const legend = document.getElementById('graphsLegend');
    const safeMsg = (message && String(message)) || 'Unknown error';
    if(withRetry){
        legend.innerHTML = `${safeMsg} <button id="graphsRetryBtn" style="margin-left:8px">Retry</button>`;
        const btn = document.getElementById('graphsRetryBtn');
        if(btn){ btn.onclick = triggerGraphsLoad; }
    }else{
        legend.textContent = safeMsg;
    }
}

async function triggerGraphsLoad(){
    const topic = (document.getElementById('graphsTopic').value || '').trim();
    const legend = document.getElementById('graphsLegend');
    if(!topic){
        showLegendError('Please enter a topic to load graphs.', false);
        return;
    }
    legend.textContent = 'Loading…';

    const fetchGraphs = async ()=>{
        const url = `/api/graphs?topic=${encodeURIComponent(topic)}`;
        return await fetchJSON(url);
    };

    try{
        const data = await retry(fetchGraphs, {retries: 2, baseDelayMs: 300});
        const points = normalizePoints(data.points || []);
        const sim = points.filter(p=>p.label==='similar');
        const dis = points.filter(p=>p.label==='dissimilar');
        const uniq = points.filter(p=>p.label==='unique');

        drawScatterInteractive(document.getElementById('canvasSimilar'), sim, '#5bc0be');
        drawScatterInteractive(document.getElementById('canvasDifferent'), dis, '#ff4d4d');
        const uniqueCanvas = document.getElementById('canvasUnique');
        if(uniqueCanvas){
            drawScatterInteractive(uniqueCanvas, uniq, '#9d4edd');
        }

        const threshold = (Number.isFinite(data.threshold) ? data.threshold : '?');
        const uThresh = (Number.isFinite(data.unique_threshold) ? data.unique_threshold : '?');
        legend.textContent = `Blue = similar (≥ ${threshold}), Red = dissimilar, Purple = unique (< ${uThresh}). Click a dot to open its page.`;
    }catch(e){
        showLegendError(e && (e.message || String(e)) , true);
    }
}

document.getElementById('graphsRunBtn').addEventListener('click', triggerGraphsLoad);


