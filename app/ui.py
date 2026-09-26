"""Complete user interface served by FastAPI."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from config import settings


def get_index_html() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{settings.app_name}</title>
  <style>
    :root {{ color-scheme: light; --bg:#f5f7fb; --card:#ffffff; --text:#182033; --muted:#667085; --brand:#2563eb; --ok:#047857; --warn:#b45309; --line:#e5e7eb; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background:var(--bg); color:var(--text); }}
    header {{ padding:28px 22px; background:linear-gradient(135deg,#1d4ed8,#0f172a); color:white; }}
    header h1 {{ margin:0 0 8px; font-size:32px; }}
    header p {{ margin:0; max-width:900px; opacity:.9; line-height:1.5; }}
    main {{ max-width:1180px; margin:0 auto; padding:22px; display:grid; grid-template-columns: 380px 1fr; gap:20px; }}
    @media (max-width: 880px) {{ main {{ grid-template-columns:1fr; }} }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:18px; padding:18px; box-shadow:0 8px 22px rgba(16,24,40,.06); }}
    label {{ display:block; font-weight:700; margin:12px 0 6px; }}
    input, textarea, button {{ width:100%; border-radius:12px; border:1px solid var(--line); padding:12px 13px; font:inherit; }}
    textarea {{ min-height:170px; resize:vertical; }}
    button {{ background:var(--brand); color:white; border:none; cursor:pointer; font-weight:800; margin-top:12px; }}
    button.secondary {{ background:#0f172a; }}
    button:disabled {{ opacity:.55; cursor:not-allowed; }}
    .hint {{ color:var(--muted); font-size:13px; line-height:1.45; }}
    .message {{ padding:14px; border-radius:14px; background:#eff6ff; border:1px solid #bfdbfe; line-height:1.55; }}
    .warning {{ background:#fffbeb; border-color:#fde68a; color:#78350f; }}
    .ok {{ color:var(--ok); font-weight:800; }}
    .pill {{ display:inline-block; border:1px solid var(--line); background:#f8fafc; padding:5px 9px; border-radius:999px; margin:3px; font-size:12px; }}
    .grid {{ display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:12px; }}
    @media (max-width: 1000px) {{ .grid {{ grid-template-columns:1fr; }} }}
    .metric {{ padding:12px; background:#f8fafc; border:1px solid var(--line); border-radius:14px; }}
    .metric b {{ display:block; font-size:20px; margin-top:4px; }}
    .day {{ border-left:4px solid var(--brand); padding:12px 14px; margin:12px 0; background:#fff; border-radius:12px; border-top:1px solid var(--line); border-right:1px solid var(--line); border-bottom:1px solid var(--line); }}
    .day h3 {{ margin:0 0 8px; }}
    ul {{ padding-left:20px; }}
    .small {{ font-size:12px; color:var(--muted); }}
    .row {{ display:flex; gap:8px; align-items:center; }}
    .row input {{ flex:1; }}
    pre {{ white-space:pre-wrap; background:#0f172a; color:#d1fae5; padding:14px; border-radius:12px; overflow:auto; }}
  </style>
</head>
<body>
  <header>
    <h1>AI Travel Agent</h1>
    <p>Plan realistic trips from natural language. The app researches local fallback data, compares options, builds itineraries, validates budgets and adapts plans without claiming live availability.</p>
  </header>
  <main>
    <section class="card">
      <label for="userId">User ID</label>
      <input id="userId" value="guest" />
      <label for="prompt">Travel request</label>
      <textarea id="prompt">Plan 8 days in Japan under ₹1.5 lakh for two people. We love food, culture and nature.</textarea>
      <button id="send">Plan trip</button>
      <label for="modify">Modify latest trip</label>
      <textarea id="modify" style="min-height:92px;">Make it cheaper.</textarea>
      <button id="modifyBtn" class="secondary">Modify trip</button>
      <p class="hint">Examples: “Remove museums”, “Add two beach days”, “It is going to rain tomorrow; change the plan.” Add an origin city for flight estimates.</p>
    </section>
    <section class="card">
      <div id="status" class="hint">Ready.</div>
      <div id="output"></div>
    </section>
  </main>
<script>
const el = (id) => document.getElementById(id);
let currentTripId = null;
function money(m) {{ return m ? `${{m.currency || ''}} ${{Math.round(m.amount || 0).toLocaleString()}}` : '—'; }}
function esc(s) {{ return String(s ?? '').replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c])); }}
function setBusy(busy) {{ el('send').disabled = busy; el('modifyBtn').disabled = busy; el('status').textContent = busy ? 'Working…' : 'Ready.'; }}
async function postJSON(url, body) {{
  const userId = el('userId').value || 'guest';
  const res = await fetch(url, {{ method:'POST', headers:{{'Content-Type':'application/json', 'X-User-ID':userId}}, body: JSON.stringify(body) }});
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}}
function render(data) {{
  const out = el('output');
  const trip = data.trip;
  if (!trip) {{
    out.innerHTML = `<div class="message">${{esc(data.message)}}</div>` + (data.questions?.length ? `<h3>Questions</h3><ul>${{data.questions.map(q=>`<li>${{esc(q)}}</li>`).join('')}}</ul>` : '');
    return;
  }}
  currentTripId = trip.id;
  const itinerary = trip.itinerary;
  const days = itinerary.days || [];
  const warnings = [...(data.warnings||[]), ...(itinerary.warnings||[])];
  const assumptions = [...(data.assumptions||[])];
  out.innerHTML = `
    <div class="message">${{esc(data.message)}}</div>
    <div class="grid" style="margin-top:14px;">
      <div class="metric">Trip ID<b>${{esc(trip.id)}}</b></div>
      <div class="metric">Budget status<b>${{esc((itinerary.budget_status||'unknown').replace('_',' '))}}</b></div>
      <div class="metric">Estimated total<b>${{money(itinerary.total_estimated_cost)}}</b></div>
    </div>
    <h2>${{esc(trip.title)}}</h2>
    <div>${{days.map(d => `<div class="day"><h3>Day ${{d.day}} — ${{esc(d.theme)}}</h3><p>${{esc(d.summary)}}</p><p class="small">${{esc(d.weather?.summary || '')}}</p><b>Activities</b><ul>${{(d.activities||[]).map(a=>`<li><b>${{esc(a.start_time || '')}}</b> ${{esc(a.name)}} <span class="small">(${{esc(a.category)}}; ${{money(a.estimated_cost)}})</span><br><span class="small">${{esc(a.opening_hours || '')}} — ${{esc(a.description || '')}}</span></li>`).join('')}}</ul><b>Meals</b><ul>${{(d.meals||[]).map(m=>`<li>${{esc(m.meal)}}: ${{esc(m.name)}} <span class="small">${{money(m.estimated_cost)}}</span></li>`).join('')}}</ul></div>`).join('')}}</div>
    <h3>Hotels / stays</h3><div>${{(trip.hotels||[]).map(h=>`<span class="pill">${{esc(h.name)}} — ${{esc(h.city)}} — ${{money(h.price_per_night)}}/night</span>`).join('') || '<span class="small">No hotel estimates.</span>'}}</div>
    <h3>Flights</h3><div>${{(trip.flights||[]).map(f=>`<span class="pill">${{esc(f.origin)}} → ${{esc(f.destination)}} — ${{money(f.estimated_price)}} — not live</span>`).join('') || '<span class="small">No flight estimate; add origin city.</span>'}}</div>
    ${{warnings.length ? `<div class="message warning"><b>Warnings</b><ul>${{[...new Set(warnings)].map(w=>`<li>${{esc(w)}}</li>`).join('')}}</ul></div>` : ''}}
    ${{assumptions.length ? `<h3>Assumptions</h3><ul>${{[...new Set(assumptions)].map(a=>`<li>${{esc(a)}}</li>`).join('')}}</ul>` : ''}}
    <details><summary>Raw JSON</summary><pre>${{esc(JSON.stringify(data, null, 2))}}</pre></details>
  `;
}}
el('send').addEventListener('click', async () => {{
  setBusy(true);
  try {{ render(await postJSON('/api/chat', {{ message: el('prompt').value, user_id: el('userId').value }})); }}
  catch (e) {{ el('output').innerHTML = `<div class="message warning">${{esc(e.message)}}</div>`; }}
  finally {{ setBusy(false); }}
}});
el('modifyBtn').addEventListener('click', async () => {{
  setBusy(true);
  try {{ render(await postJSON('/api/chat', {{ message: el('modify').value, user_id: el('userId').value, trip_id: currentTripId }})); }}
  catch (e) {{ el('output').innerHTML = `<div class="message warning">${{esc(e.message)}}</div>`; }}
  finally {{ setBusy(false); }}
}});
</script>
</body>
</html>"""


def register_ui_routes(app: FastAPI) -> None:
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index() -> HTMLResponse:
        return HTMLResponse(get_index_html())

    @app.get("/app", response_class=HTMLResponse, include_in_schema=False)
    async def app_index() -> HTMLResponse:
        return HTMLResponse(get_index_html())
