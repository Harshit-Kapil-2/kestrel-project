const SAMPLES = [
  "flat 4b nr big bazar opp sbi koramangla 5th blk blr 560034",
  "h no 12 gandhi nagar near hanuman mandir ludhiana punjab",
  "nit hamirpur anu hamirpur himachal",
  "sector 62 noida UP 20130"
];

const map = L.map('map').setView([22.5, 79], 4);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap'
}).addTo(map);

// Invalidate map size on window resize
window.addEventListener('resize', () => {
  map.invalidateSize();
});

let layers = [];
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]
));

// sample address buttons
SAMPLES.forEach(s => {
  const b = document.createElement('button');
  b.className = 'chip';
  b.textContent = s;
  b.onclick = () => { $('addr').value = s; run(); };
  $('chips').appendChild(b);
});

$('go').onclick = run;

// Trigger on Ctrl+Enter or Cmd+Enter
$('addr').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    run();
  }
});

async function run() {
  const address = $('addr').value.trim();
  if (!address) return;
  $('go').disabled = true;
  $('go').textContent = 'Matching...';
  try {
    const apiBase = window.location.protocol === 'file:' ? 'http://127.0.0.1:8000' : '';
    const r = await fetch(`${apiBase}/api/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address })
    });
    show(await r.json());
  } catch (e) {
    $('result').innerHTML = '<h2>Result</h2><p class="err">Could not reach the server. Is uvicorn running?</p>';
  }
  $('go').disabled = false;
  $('go').textContent = 'Find post office';
}

function show(d) {
  layers.forEach(l => map.removeLayer(l));
  layers = [];

  if (d.error) {
    $('result').innerHTML = `<h2>Result</h2><p class="err">${esc(d.error)}</p>`;
    return;
  }
  if (!d.best) {
    $('result').innerHTML = `<h2>Result</h2><p class="err">No match found. Add a locality or city.</p>`;
    return;
  }

  const b = d.best;
  const pct = Math.round(d.confidence * 100);

  $('result').innerHTML = `
    <h2>Nearest serviceable post office</h2>
    <p class="big">${esc(b.office)} <span style="color:var(--red)">${esc(b.pincode)}</span></p>
    <p class="meta">${esc(b.type)} · ${esc(b.district)}, ${esc(b.state)}${d.distance_km != null ? ` · ${d.distance_km} km from address` : ''}</p>
    <div class="cleaned"><b>Cleaned:</b> ${esc(d.parsed.cleaned_address || '')}</div>
    <p class="meta">Confidence ${pct}%</p>
    <div class="bar"><i style="width:${pct}%"></i></div>
    <ul class="trace">${d.trace.map(t => `<li>${esc(t)}</li>`).join('')}</ul>`;

  const pts = [];

  if (b.lat != null) {
    layers.push(
      L.marker([b.lat, b.lon]).addTo(map)
        .bindPopup(`<b>${esc(b.office)}</b><br>${esc(b.pincode)}`).openPopup()
    );
    pts.push([b.lat, b.lon]);
  }

  if (d.query_point) {
    const q = [d.query_point.lat, d.query_point.lon];
    layers.push(
      L.circleMarker(q, { radius: 8, color: '#14213d', fillOpacity: .8 }).addTo(map).bindPopup('Address')
    );
    pts.push(q);
    if (b.lat != null) {
      layers.push(L.polyline([q, [b.lat, b.lon]], { color: '#d7263d', dashArray: '6' }).addTo(map));
    }
  }

  (d.alternatives || []).forEach(a => {
    if (a.lat != null) {
      layers.push(
        L.circleMarker([a.lat, a.lon], { radius: 6, color: '#8d99ae' }).addTo(map)
          .bindPopup(`${esc(a.office)} (${a.score})`)
      );
      pts.push([a.lat, a.lon]);
    }
  });

  if (pts.length) {
    map.fitBounds(pts, { maxZoom: 14, padding: [30, 30] });
  }

  setTimeout(() => {
    map.invalidateSize();
  }, 150);
}