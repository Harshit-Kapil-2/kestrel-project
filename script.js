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
const esc = s => String(s || '').replace(/[&<>"]/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]
));

// Sample address buttons
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
  $('go').textContent = 'Geocoding & Finding Post Office...';
  try {
    const apiBase = window.location.protocol === 'file:' ? 'http://127.0.0.1:8000' : '';
    const r = await fetch(`${apiBase}/api/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address })
    });
    show(await r.json());
  } catch (e) {
    $('result').innerHTML = '<h2>Result</h2><p class="err">Could not reach the server. Is PostFinder desktop backend running?</p>';
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
    $('result').innerHTML = `<h2>Result</h2><p class="err">No matching post office found. Try including city or district name.</p>`;
    return;
  }

  const b = d.best;
  const q = d.query_point;
  const pct = Math.round(d.confidence * 100);

  // Geological location card (Google Maps style)
  let geoHtml = '';
  if (q) {
    geoHtml = `
      <div class="geo-box">
        <div class="geo-title">📍 User Geological Location (via Geopy)</div>
        <div>${esc(q.formatted_address || d.parsed.cleaned_address)}</div>
        <div class="geo-coords">Lat: ${q.lat.toFixed(5)}, Lon: ${q.lon.toFixed(5)}</div>
      </div>
    `;
  }

  // Services pills
  let servicesHtml = '';
  if (b.services && b.services.length) {
    servicesHtml = `
      <div class="services-container">
        <div class="services-title">Available Postal Services</div>
        <div class="services-list">
          ${b.services.map(s => `<span class="service-pill">${esc(s)}</span>`).join('')}
        </div>
      </div>
    `;
  }

  // Directions button
  let navHtml = '';
  if (b.directions_url) {
    navHtml = `
      <a href="${b.directions_url}" target="_blank" class="nav-btn">
        🧭 Open Directions in Google Maps ↗
      </a>
    `;
  }

  $('result').innerHTML = `
    <h2>Nearest Serviceable Post Office</h2>
    <p class="big">
      ${esc(b.office)} 
      <span style="color:var(--red)">PIN ${esc(b.pincode)}</span>
    </p>

    <div style="margin: 6px 0;">
      <span class="badge badge-green">${esc(b.type)}</span>
      ${b.distance_km != null ? `<span class="badge badge-red" style="margin-left:4px;">${b.distance_km} km away</span>` : ''}
    </div>

    ${geoHtml}

    <div class="details-grid">
      <div class="details-item">
        <b>Postal Circle</b>
        ${esc(b.circle || 'India Post')}
      </div>
      <div class="details-item">
        <b>Division & Region</b>
        ${esc(b.division || b.district + ' Division')}
      </div>
      <div class="details-item">
        <b>Delivery Jurisdiction</b>
        ${esc(b.district)}, ${esc(b.state)}
      </div>
      <div class="details-item">
        <b>Operating Hours</b>
        ${esc(b.timings || 'Mon - Sat: 9:00 AM - 5:00 PM')}
      </div>
    </div>

    ${servicesHtml}
    ${navHtml}

    <div style="margin-top:14px;">
      <p class="meta" style="margin-bottom:2px;">Proximity & Beat Match Confidence: ${pct}%</p>
      <div class="bar"><i style="width:${pct}%"></i></div>
    </div>

    <ul class="trace">
      ${d.trace.map(t => `<li>${esc(t)}</li>`).join('')}
    </ul>
  `;

  const pts = [];

  // Post office marker (Red)
  if (b.lat != null && b.lon != null) {
    const poMarker = L.marker([b.lat, b.lon]).addTo(map)
      .bindPopup(`
        <div style="font-family:'IBM Plex Sans',sans-serif;">
          <b style="font-size:14px;color:#d7263d;">${esc(b.office)}</b><br>
          <b>PIN:</b> ${esc(b.pincode)}<br>
          <b>Type:</b> ${esc(b.type)}<br>
          <b>Distance:</b> ${b.distance_km != null ? `${b.distance_km} km` : 'Near'}<br>
          <small>${esc(b.district)}, ${esc(b.state)}</small>
        </div>
      `).openPopup();
    layers.push(poMarker);
    pts.push([b.lat, b.lon]);
  }

  // User location marker (Blue circle)
  if (q && q.lat != null && q.lon != null) {
    const userPoint = [q.lat, q.lon];
    const userMarker = L.circleMarker(userPoint, {
      radius: 9,
      color: '#14213d',
      fillColor: '#1d3557',
      fillOpacity: 0.9,
      weight: 2
    }).addTo(map).bindPopup(`
      <div style="font-family:'IBM Plex Sans',sans-serif;">
        <b>📍 User Address Location</b><br>
        <small>${esc(q.formatted_address || 'Geocoded point')}</small>
      </div>
    `);
    layers.push(userMarker);
    pts.push(userPoint);

    // Trajectory Polyline connecting user to post office
    if (b.lat != null && b.lon != null) {
      const line = L.polyline([userPoint, [b.lat, b.lon]], {
        color: '#d7263d',
        dashArray: '6, 6',
        weight: 3,
        opacity: 0.85
      }).addTo(map);
      layers.push(line);
    }
  }

  // Alternative nearby post offices (Gray circle markers)
  (d.alternatives || []).forEach(a => {
    if (a.lat != null && a.lon != null) {
      const altMarker = L.circleMarker([a.lat, a.lon], {
        radius: 6,
        color: '#8d99ae',
        fillColor: '#8d99ae',
        fillOpacity: 0.65
      }).addTo(map).bindPopup(`
        <div style="font-family:'IBM Plex Sans',sans-serif;">
          <b>${esc(a.office)}</b><br>
          Score: ${esc(a.score)}<br>
          ${a.distance_km != null ? `Distance: ${a.distance_km} km` : ''}
        </div>
      `);
      layers.push(altMarker);
      pts.push([a.lat, a.lon]);
    }
  });

  if (pts.length) {
    map.fitBounds(pts, { maxZoom: 15, padding: [40, 40] });
  }

  setTimeout(() => {
    map.invalidateSize();
  }, 150);
}