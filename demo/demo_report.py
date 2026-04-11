"""Demo: Smoldyn multi-configuration spatial stochastic simulation report.

Runs three distinct particle-based simulations (diffusion gradient,
predator-prey dynamics, enzymatic reaction), generates interactive 2D
particle viewers, Plotly charts, bigraph-viz diagrams, and navigatable
PBG document trees -- all in a single self-contained HTML.
"""

import json
import os
import base64
import tempfile
import time as _time
from process_bigraph import allocate_core
from pbg_smoldyn.processes import SmoldynProcess
from pbg_smoldyn.composites import make_smoldyn_document


# ── Simulation Configs ──────────────────────────────────────────────

CONFIGS = [
    {
        'id': 'diffusion',
        'title': 'Two-Species Diffusion',
        'subtitle': 'Fast vs. slow Brownian motion in a reflective box',
        'description': (
            'Two molecular species diffuse in a 2D domain with reflective '
            'boundaries. Species A (red) has a high diffusion coefficient '
            '(D=3.0) while species B (blue) diffuses slowly (D=0.3). '
            'Starting from a concentrated cluster in the center, this '
            'demonstrates how diffusion rate governs spatial spreading. '
            'No reactions occur -- total molecule counts are conserved.'
        ),
        'config': {
            'dimensions': 2,
            'bounds': [[0, 100], [0, 100]],
            'boundary_type': 'r',
            'dt': 0.01,
            'seed': 42,
            'species': {
                'A': {'difc': 3.0, 'count': 300, 'color': 'red'},
                'B': {'difc': 0.3, 'count': 300, 'color': 'blue'},
            },
            'reactions': [],
        },
        'n_snapshots': 30,
        'total_time': 60.0,
        'color_scheme': 'indigo',
    },
    {
        'id': 'lotka',
        'title': 'Lotka-Volterra Predator-Prey',
        'subtitle': 'Spatial oscillations in a stochastic predator-prey system',
        'description': (
            'A classic predator-prey model with three reactions: '
            'prey reproduction (A -> A + A), predation (A + B -> B + B), '
            'and predator death (B -> 0). In a well-mixed system these '
            'produce sustained oscillations; in this spatial version, '
            'stochastic fluctuations and diffusion create complex '
            'spatiotemporal patterns. Prey (green) and predators (red) '
            'chase each other across the domain.'
        ),
        'config': {
            'dimensions': 2,
            'bounds': [[0, 100], [0, 100]],
            'boundary_type': 'p',
            'dt': 0.005,
            'seed': 7,
            'species': {
                'prey': {'difc': 3.0, 'count': 300, 'color': 'green'},
                'predator': {'difc': 3.0, 'count': 300, 'color': 'red'},
            },
            'reactions': [
                {'name': 'reproduce', 'subs': ['prey'], 'prds': ['prey', 'prey'], 'rate': 0.1},
                {'name': 'predation', 'subs': ['prey', 'predator'], 'prds': ['predator', 'predator'], 'rate': 2.0},
                {'name': 'death', 'subs': ['predator'], 'prds': [], 'rate': 0.2},
            ],
        },
        'n_snapshots': 30,
        'total_time': 30.0,
        'color_scheme': 'emerald',
    },
    {
        'id': 'enzyme',
        'title': 'Michaelis-Menten Enzyme Kinetics',
        'subtitle': 'Spatial enzyme-substrate binding and product formation',
        'description': (
            'An enzyme (E, purple) binds substrate (S, blue) to form '
            'a complex (ES, orange), which then releases product (P, green). '
            'The reversible binding step (E + S <-> ES) with forward rate '
            'k_f and backward rate k_b, followed by irreversible catalysis '
            '(ES -> E + P), produces classic Michaelis-Menten kinetics. '
            'In this spatial model, diffusion-limited encounters between '
            'enzyme and substrate create local depletion zones.'
        ),
        'config': {
            'dimensions': 2,
            'bounds': [[0, 80], [0, 80]],
            'boundary_type': 'r',
            'dt': 0.005,
            'seed': 123,
            'species': {
                'E': {'difc': 1.0, 'count': 50, 'color': 'purple'},
                'S': {'difc': 2.0, 'count': 500, 'color': 'blue'},
                'ES': {'difc': 0.5, 'count': 0, 'color': 'orange'},
                'P': {'difc': 2.0, 'count': 0, 'color': 'green'},
            },
            'reactions': [
                {'name': 'bind', 'subs': ['E', 'S'], 'prds': ['ES'], 'rate': 0.5, 'kb': 0.1},
                {'name': 'catalyze', 'subs': ['ES'], 'prds': ['E', 'P'], 'rate': 0.8},
            ],
        },
        'n_snapshots': 30,
        'total_time': 30.0,
        'color_scheme': 'rose',
    },
]

# Per-species display colors for the canvas viewer
SPECIES_COLORS = {
    'A': '#ef4444',      # red
    'B': '#3b82f6',      # blue
    'prey': '#22c55e',   # green
    'predator': '#ef4444',  # red
    'E': '#a855f7',      # purple
    'S': '#3b82f6',      # blue
    'ES': '#f97316',     # orange
    'P': '#22c55e',      # green
}


def run_simulation(cfg_entry):
    """Run a single simulation, returning snapshots and wall-clock runtime."""
    core = allocate_core()
    core.register_link('SmoldynProcess', SmoldynProcess)

    t0 = _time.perf_counter()
    proc = SmoldynProcess(config=cfg_entry['config'], core=core)
    state0 = proc.initial_state()

    interval = cfg_entry['total_time'] / cfg_entry['n_snapshots']
    snapshots = []

    t = 0.0
    for i in range(cfg_entry['n_snapshots'] + 1):
        if i == 0:
            # First step: run a tiny interval just to capture initial positions
            dt = cfg_entry['config'].get('dt', 0.01)
            proc.update({}, interval=dt)
            positions = proc.get_molecule_positions()
            snapshots.append(_snap(0.0, state0, positions))
            # Adjust remaining time for subsequent steps
        else:
            step_interval = interval if i > 1 else interval - cfg_entry['config'].get('dt', 0.01)
            result = proc.update({}, interval=step_interval)
            t = round(i * interval, 3)
            positions = proc.get_molecule_positions()
            snapshots.append(_snap(t, result, positions))

    runtime = _time.perf_counter() - t0
    return snapshots, runtime


def _snap(t, state, positions):
    return {
        'time': t,
        'counts': dict(state['molecule_counts']),
        'positions': positions,
    }


def generate_bigraph_image(cfg_entry):
    """Generate a colored bigraph-viz PNG for the composite document."""
    from bigraph_viz import plot_bigraph

    species_names = list(cfg_entry['config']['species'].keys())
    count_ports = {s: ['stores', 'molecule_counts', s] for s in species_names[:4]}

    doc = {
        'smoldyn': {
            '_type': 'process',
            'address': 'local:SmoldynProcess',
            'config': {'species': list(species_names)},
            'interval': cfg_entry['total_time'] / cfg_entry['n_snapshots'],
            'inputs': {},
            'outputs': {
                'molecule_counts': ['stores', 'molecule_counts'],
                'time': ['stores', 'time'],
            },
        },
        'stores': {},
        'emitter': {
            '_type': 'step',
            'address': 'local:ram-emitter',
            'inputs': {
                'molecule_counts': ['stores', 'molecule_counts'],
                'time': ['global_time'],
            },
        },
    }

    node_colors = {
        ('smoldyn',): '#6366f1',
        ('emitter',): '#8b5cf6',
        ('stores',): '#e0e7ff',
    }

    outdir = tempfile.mkdtemp()
    plot_bigraph(
        state=doc,
        out_dir=outdir,
        filename='bigraph',
        file_format='png',
        remove_process_place_edges=True,
        rankdir='LR',
        node_fill_colors=node_colors,
        node_label_size='16pt',
        port_labels=False,
        dpi='150',
    )
    png_path = os.path.join(outdir, 'bigraph.png')
    with open(png_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    return f'data:image/png;base64,{b64}'


def build_pbg_document(cfg_entry):
    """Build the PBG composite document dict for display."""
    cfg = cfg_entry['config']
    doc = make_smoldyn_document(
        dimensions=cfg.get('dimensions', 2),
        bounds=cfg.get('bounds', [[0, 100], [0, 100]]),
        boundary_type=cfg.get('boundary_type', 'r'),
        dt=cfg.get('dt', 0.01),
        species=cfg.get('species', {}),
        reactions=cfg.get('reactions', []),
        interval=cfg_entry['total_time'] / cfg_entry['n_snapshots'],
    )
    return doc


COLOR_SCHEMES = {
    'indigo': {'primary': '#6366f1', 'light': '#e0e7ff', 'dark': '#4338ca',
               'bg': '#eef2ff', 'accent': '#818cf8', 'text': '#312e81'},
    'emerald': {'primary': '#10b981', 'light': '#d1fae5', 'dark': '#059669',
                'bg': '#ecfdf5', 'accent': '#34d399', 'text': '#064e3b'},
    'rose': {'primary': '#f43f5e', 'light': '#ffe4e6', 'dark': '#e11d48',
             'bg': '#fff1f2', 'accent': '#fb7185', 'text': '#881337'},
}


def generate_html(sim_results, output_path):
    """Generate comprehensive HTML report."""

    sections_html = []
    all_js_data = {}

    for idx, (cfg, (snapshots, runtime)) in enumerate(sim_results):
        sid = cfg['id']
        cs = COLOR_SCHEMES[cfg['color_scheme']]
        species_names = list(cfg['config']['species'].keys())
        bounds = cfg['config']['bounds']

        # Time series
        times = [s['time'] for s in snapshots]
        counts_series = {sp: [s['counts'].get(sp, 0) for s in snapshots]
                         for sp in species_names}

        # Total molecules
        totals = [sum(s['counts'].values()) for s in snapshots]

        # JS data for particle viewer
        all_js_data[sid] = {
            'snapshots': [{
                'time': s['time'],
                'positions': s['positions'],
            } for s in snapshots],
            'bounds': bounds,
            'species_names': species_names,
            'charts': {
                'times': times,
                'counts': counts_series,
                'totals': totals,
            },
        }

        # Bigraph PNG
        print(f'  Generating bigraph diagram for {sid}...')
        bigraph_img = generate_bigraph_image(cfg)

        # PBG document JSON
        pbg_doc = build_pbg_document(cfg)

        # Stats
        n_molecules = totals[0]
        n_species = len(species_names)
        n_reactions = len(cfg['config']['reactions'])

        # Species legend items
        legend_items = ''.join(
            f'<span class="legend-item">'
            f'<span class="legend-dot" style="background:{SPECIES_COLORS.get(sp, "#666")};"></span>'
            f'{sp}</span>'
            for sp in species_names
        )

        # Count change summary
        initial_counts = ' | '.join(
            f'{sp}: {snapshots[0]["counts"].get(sp, 0)}'
            for sp in species_names)
        final_counts = ' | '.join(
            f'{sp}: {snapshots[-1]["counts"].get(sp, 0)}'
            for sp in species_names)

        section = f"""
    <div class="sim-section" id="sim-{sid}">
      <div class="sim-header" style="border-left: 4px solid {cs['primary']};">
        <div class="sim-number" style="background:{cs['light']}; color:{cs['dark']};">{idx+1}</div>
        <div>
          <h2 class="sim-title">{cfg['title']}</h2>
          <p class="sim-subtitle">{cfg['subtitle']}</p>
        </div>
      </div>
      <p class="sim-description">{cfg['description']}</p>

      <div class="metrics-row">
        <div class="metric"><span class="metric-label">Species</span><span class="metric-value">{n_species}</span></div>
        <div class="metric"><span class="metric-label">Reactions</span><span class="metric-value">{n_reactions}</span></div>
        <div class="metric"><span class="metric-label">Initial Molecules</span><span class="metric-value">{n_molecules:,}</span></div>
        <div class="metric"><span class="metric-label">Final Molecules</span><span class="metric-value">{totals[-1]:,}</span></div>
        <div class="metric"><span class="metric-label">Snapshots</span><span class="metric-value">{len(snapshots)}</span></div>
        <div class="metric"><span class="metric-label">Runtime</span><span class="metric-value">{runtime:.2f}s</span></div>
      </div>

      <h3 class="subsection-title">Particle Viewer</h3>
      <div class="viewer-wrap">
        <canvas id="canvas-{sid}" class="particle-canvas"></canvas>
        <div class="viewer-info">
          {legend_items}
        </div>
        <div class="slider-controls">
          <button class="play-btn" style="border-color:{cs['primary']}; color:{cs['primary']};" onclick="togglePlay('{sid}')">Play</button>
          <label>Time</label>
          <input type="range" class="time-slider" id="slider-{sid}" min="0" max="{len(snapshots)-1}" value="0" step="1"
                 style="accent-color:{cs['primary']};">
          <span class="time-val" id="tval-{sid}">t = 0</span>
        </div>
      </div>

      <h3 class="subsection-title">Species Dynamics</h3>
      <div class="charts-row">
        <div class="chart-box"><div id="chart-counts-{sid}" class="chart"></div></div>
        <div class="chart-box"><div id="chart-total-{sid}" class="chart"></div></div>
        <div class="chart-box"><div id="chart-phase-{sid}" class="chart"></div></div>
        <div class="chart-box"><div id="chart-ratio-{sid}" class="chart"></div></div>
      </div>

      <div class="pbg-row">
        <div class="pbg-col">
          <h3 class="subsection-title">Bigraph Architecture</h3>
          <div class="bigraph-img-wrap">
            <img src="{bigraph_img}" alt="Bigraph architecture diagram">
          </div>
        </div>
        <div class="pbg-col">
          <h3 class="subsection-title">Composite Document</h3>
          <div class="json-tree" id="json-{sid}"></div>
        </div>
      </div>
    </div>
"""
        sections_html.append(section)

    # Navigation
    nav_items = ''.join(
        f'<a href="#sim-{c["id"]}" class="nav-link" '
        f'style="border-color:{COLOR_SCHEMES[c["color_scheme"]]["primary"]};">'
        f'{c["title"]}</a>'
        for c in [r[0] for r in sim_results])

    # PBG docs for JSON viewer
    pbg_docs = {r[0]['id']: build_pbg_document(r[0]) for r in sim_results}

    # Species colors JSON for JS
    species_colors_json = json.dumps(SPECIES_COLORS)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Smoldyn Spatial Stochastic Simulation Report</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       background:#fff; color:#1e293b; line-height:1.6; }}
.page-header {{
  background:linear-gradient(135deg,#f8fafc 0%,#eef2ff 50%,#fdf2f8 100%);
  border-bottom:1px solid #e2e8f0; padding:3rem;
}}
.page-header h1 {{ font-size:2.2rem; font-weight:800; color:#0f172a; margin-bottom:.3rem; }}
.page-header p {{ color:#64748b; font-size:.95rem; max-width:700px; }}
.nav {{ display:flex; gap:.8rem; padding:1rem 3rem; background:#f8fafc;
        border-bottom:1px solid #e2e8f0; position:sticky; top:0; z-index:100; }}
.nav-link {{ padding:.4rem 1rem; border-radius:8px; border:1.5px solid;
             text-decoration:none; font-size:.85rem; font-weight:600;
             transition:all .15s; }}
.nav-link:hover {{ transform:translateY(-1px); box-shadow:0 2px 8px rgba(0,0,0,.08); }}
.sim-section {{ padding:2.5rem 3rem; border-bottom:1px solid #e2e8f0; }}
.sim-header {{ display:flex; align-items:center; gap:1rem; margin-bottom:.8rem;
               padding-left:1rem; }}
.sim-number {{ width:36px; height:36px; border-radius:10px; display:flex;
               align-items:center; justify-content:center; font-weight:800; font-size:1.1rem; }}
.sim-title {{ font-size:1.5rem; font-weight:700; color:#0f172a; }}
.sim-subtitle {{ font-size:.9rem; color:#64748b; }}
.sim-description {{ color:#475569; font-size:.9rem; margin-bottom:1.5rem; max-width:800px; }}
.subsection-title {{ font-size:1.05rem; font-weight:600; color:#334155;
                     margin:1.5rem 0 .8rem; }}
.metrics-row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
                gap:.8rem; margin-bottom:1.5rem; }}
.metric {{ background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px;
           padding:.8rem; text-align:center; }}
.metric-label {{ display:block; font-size:.7rem; text-transform:uppercase;
                 letter-spacing:.06em; color:#94a3b8; margin-bottom:.2rem; }}
.metric-value {{ display:block; font-size:1.3rem; font-weight:700; color:#1e293b; }}
.metric-sub {{ display:block; font-size:.7rem; color:#94a3b8; }}
.viewer-wrap {{ position:relative; background:#0f172a; border:1px solid #334155;
                border-radius:14px; overflow:hidden; margin-bottom:1rem; }}
.particle-canvas {{ width:100%; height:500px; display:block; }}
.viewer-info {{ position:absolute; top:.8rem; left:.8rem; background:rgba(15,23,42,.85);
                border:1px solid #334155; border-radius:8px; padding:.5rem .8rem;
                font-size:.78rem; color:#94a3b8; backdrop-filter:blur(4px);
                display:flex; gap:1rem; align-items:center; }}
.legend-item {{ display:flex; align-items:center; gap:.3rem; }}
.legend-dot {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
.slider-controls {{ position:absolute; bottom:0; left:0; right:0;
                    background:linear-gradient(transparent,rgba(15,23,42,.95));
                    padding:1.5rem 1.5rem 1rem; display:flex; align-items:center; gap:.8rem; }}
.slider-controls label {{ font-size:.8rem; color:#94a3b8; }}
.time-slider {{ flex:1; height:5px; }}
.time-val {{ font-size:.95rem; font-weight:600; color:#e2e8f0; min-width:100px; text-align:right; }}
.play-btn {{ background:rgba(15,23,42,.8); border:1.5px solid; padding:.3rem .8rem; border-radius:7px;
             cursor:pointer; font-size:.8rem; font-weight:600; transition:all .15s; }}
.play-btn:hover {{ transform:scale(1.05); }}
.charts-row {{ display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-bottom:1rem; }}
.chart-box {{ background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; overflow:hidden; }}
.chart {{ height:280px; }}
.pbg-row {{ display:grid; grid-template-columns:1fr 1fr; gap:1.5rem; margin-top:1rem; }}
.pbg-col {{ min-width:0; }}
.bigraph-img-wrap {{ background:#fafafa; border:1px solid #e2e8f0; border-radius:10px;
                     padding:1.5rem; text-align:center; }}
.bigraph-img-wrap img {{ max-width:100%; height:auto; }}
.json-tree {{ background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px;
              padding:1rem; max-height:500px; overflow-y:auto; font-family:'SF Mono',
              Menlo,Monaco,'Courier New',monospace; font-size:.78rem; line-height:1.5; }}
.jt-key {{ color:#7c3aed; font-weight:600; }}
.jt-str {{ color:#059669; }}
.jt-num {{ color:#2563eb; }}
.jt-bool {{ color:#d97706; }}
.jt-null {{ color:#94a3b8; }}
.jt-toggle {{ cursor:pointer; user-select:none; color:#94a3b8; margin-right:.3rem; }}
.jt-toggle:hover {{ color:#1e293b; }}
.jt-collapsed {{ display:none; }}
.jt-bracket {{ color:#64748b; }}
.footer {{ text-align:center; padding:2rem; color:#94a3b8; font-size:.8rem;
           border-top:1px solid #e2e8f0; }}
@media(max-width:900px) {{
  .charts-row,.pbg-row {{ grid-template-columns:1fr; }}
  .sim-section,.page-header {{ padding:1.5rem; }}
}}
</style>
</head>
<body>

<div class="page-header">
  <h1>Smoldyn Spatial Stochastic Simulation Report</h1>
  <p>Three particle-based spatial stochastic simulations wrapped as <strong>process-bigraph</strong>
  Processes using the Smoldyn simulator. Each configuration demonstrates
  a distinct reaction-diffusion scenario with interactive particle visualization.</p>
</div>

<div class="nav">{nav_items}</div>

{''.join(sections_html)}

<div class="footer">
  Generated by <strong>pbg-smoldyn</strong> &mdash;
  Smoldyn + process-bigraph &mdash;
  Particle-Based Spatial Stochastic Simulation
</div>

<script>
const DATA = {json.dumps(all_js_data)};
const DOCS = {json.dumps(pbg_docs, indent=2)};
const SPECIES_COLORS = {species_colors_json};

// ---- JSON Tree Viewer ----
function renderJson(obj, depth) {{
  if (depth === undefined) depth = 0;
  if (obj === null) return '<span class="jt-null">null</span>';
  if (typeof obj === 'boolean') return '<span class="jt-bool">' + obj + '</span>';
  if (typeof obj === 'number') return '<span class="jt-num">' + obj + '</span>';
  if (typeof obj === 'string') return '<span class="jt-str">"' + obj.replace(/</g,'&lt;') + '"</span>';
  if (Array.isArray(obj)) {{
    if (obj.length === 0) return '<span class="jt-bracket">[]</span>';
    if (obj.length <= 5 && obj.every(x => typeof x !== 'object' || x === null)) {{
      const items = obj.map(x => renderJson(x, depth+1)).join(', ');
      return '<span class="jt-bracket">[</span>' + items + '<span class="jt-bracket">]</span>';
    }}
    const id = 'jt' + Math.random().toString(36).slice(2,9);
    let html = '<span class="jt-toggle" onclick="toggleJt(\\'' + id + '\\')">&blacktriangledown;</span>';
    html += '<span class="jt-bracket">[</span> <span style="color:#94a3b8;font-size:.7rem;">' + obj.length + ' items</span>';
    html += '<div id="' + id + '" style="margin-left:1.2rem;">';
    obj.forEach((v, i) => {{ html += '<div>' + renderJson(v, depth+1) + (i < obj.length-1 ? ',' : '') + '</div>'; }});
    html += '</div><span class="jt-bracket">]</span>';
    return html;
  }}
  if (typeof obj === 'object') {{
    const keys = Object.keys(obj);
    if (keys.length === 0) return '<span class="jt-bracket">{{}}</span>';
    const id = 'jt' + Math.random().toString(36).slice(2,9);
    const collapsed = depth >= 2;
    let html = '<span class="jt-toggle" onclick="toggleJt(\\'' + id + '\\')">' +
               (collapsed ? '&blacktriangleright;' : '&blacktriangledown;') + '</span>';
    html += '<span class="jt-bracket">{{</span>';
    html += '<div id="' + id + '"' + (collapsed ? ' class="jt-collapsed"' : '') + ' style="margin-left:1.2rem;">';
    keys.forEach((k, i) => {{
      html += '<div><span class="jt-key">' + k + '</span>: ' +
              renderJson(obj[k], depth+1) + (i < keys.length-1 ? ',' : '') + '</div>';
    }});
    html += '</div><span class="jt-bracket">}}</span>';
    return html;
  }}
  return String(obj);
}}
function toggleJt(id) {{
  const el = document.getElementById(id);
  if (el.classList.contains('jt-collapsed')) {{
    el.classList.remove('jt-collapsed');
    const prev = el.previousElementSibling;
    if (prev && prev.previousElementSibling && prev.previousElementSibling.classList.contains('jt-toggle'))
      prev.previousElementSibling.innerHTML = '&blacktriangledown;';
  }} else {{
    el.classList.add('jt-collapsed');
    const prev = el.previousElementSibling;
    if (prev && prev.previousElementSibling && prev.previousElementSibling.classList.contains('jt-toggle'))
      prev.previousElementSibling.innerHTML = '&blacktriangleright;';
  }}
}}
Object.keys(DOCS).forEach(sid => {{
  const el = document.getElementById('json-' + sid);
  if (el) el.innerHTML = renderJson(DOCS[sid], 0);
}});

// ---- 2D Particle Canvas Viewer ----
const viewers = {{}};
const playStates = {{}};

function initViewer(sid) {{
  const d = DATA[sid];
  const canvas = document.getElementById('canvas-' + sid);
  const W = canvas.parentElement.clientWidth;
  const H = 500;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  canvas.style.width = W + 'px';
  canvas.style.height = H + 'px';

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const bx = d.bounds[0], by = d.bounds[1];
  const domainW = bx[1] - bx[0], domainH = by[1] - by[0];

  // Fit domain into canvas with padding
  const pad = 30;
  const scale = Math.min((W - 2*pad) / domainW, (H - 2*pad) / domainH);
  const offX = (W - domainW * scale) / 2;
  const offY = (H - domainH * scale) / 2;

  function toCanvas(x, y) {{
    return [offX + (x - bx[0]) * scale, offY + (by[1] - y) * scale];  // flip y
  }}

  function drawFrame(idx) {{
    const snap = d.snapshots[idx];
    ctx.clearRect(0, 0, W, H);

    // Domain boundary
    const [x0, y0] = toCanvas(bx[0], by[1]);
    const [x1, y1] = toCanvas(bx[1], by[0]);
    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);

    // Grid lines
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 0.3;
    const gridStep = domainW / 5;
    for (let g = 1; g < 5; g++) {{
      const [gx, gy1] = toCanvas(bx[0] + g * gridStep, by[0]);
      const [gx2, gy2] = toCanvas(bx[0] + g * gridStep, by[1]);
      ctx.beginPath(); ctx.moveTo(gx, gy1); ctx.lineTo(gx2, gy2); ctx.stroke();
      const [gx3, gy3] = toCanvas(bx[0], by[0] + g * (domainH / 5));
      const [gx4, gy4] = toCanvas(bx[1], by[0] + g * (domainH / 5));
      ctx.beginPath(); ctx.moveTo(gx3, gy3); ctx.lineTo(gx4, gy4); ctx.stroke();
    }}

    // Particles
    if (!snap.positions || snap.positions.length === 0) return;
    const radius = Math.max(2, Math.min(5, 1500 / snap.positions.length));

    // Group by species for batch rendering
    const groups = {{}};
    snap.positions.forEach(p => {{
      if (!groups[p.species]) groups[p.species] = [];
      groups[p.species].push(p);
    }});

    for (const [sp, mols] of Object.entries(groups)) {{
      const color = SPECIES_COLORS[sp] || '#999';
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.75;
      ctx.beginPath();
      mols.forEach(p => {{
        const [cx, cy] = toCanvas(p.x, p.y);
        ctx.moveTo(cx + radius, cy);
        ctx.arc(cx, cy, radius, 0, 2 * Math.PI);
      }});
      ctx.fill();
    }}
    ctx.globalAlpha = 1.0;
  }}

  drawFrame(0);

  const slider = document.getElementById('slider-' + sid);
  const tval = document.getElementById('tval-' + sid);
  slider.addEventListener('input', () => {{
    const idx = parseInt(slider.value);
    drawFrame(idx);
    tval.textContent = 't = ' + d.snapshots[idx].time.toFixed(1);
  }});

  viewers[sid] = {{ drawFrame, slider, tval }};
  playStates[sid] = {{ playing: false, interval: null }};
}}

function togglePlay(sid) {{
  const ps = playStates[sid];
  const v = viewers[sid];
  const d = DATA[sid];
  const btn = event.target;
  ps.playing = !ps.playing;
  if (ps.playing) {{
    btn.textContent = 'Pause';
    ps.interval = setInterval(() => {{
      let idx = parseInt(v.slider.value) + 1;
      if (idx >= d.snapshots.length) idx = 0;
      v.slider.value = idx;
      v.drawFrame(idx);
      v.tval.textContent = 't = ' + d.snapshots[idx].time.toFixed(1);
    }}, 250);
  }} else {{
    btn.textContent = 'Play';
    clearInterval(ps.interval);
  }}
}}

// Init all viewers
Object.keys(DATA).forEach(sid => initViewer(sid));

// ---- Plotly Charts ----
const pLayout = {{
  paper_bgcolor:'#f8fafc', plot_bgcolor:'#f8fafc',
  font:{{ color:'#64748b', family:'-apple-system,sans-serif', size:11 }},
  margin:{{ l:55, r:15, t:35, b:40 }},
  xaxis:{{ gridcolor:'#e2e8f0', zerolinecolor:'#e2e8f0',
           title:{{ text:'Time', font:{{ size:10 }} }} }},
  yaxis:{{ gridcolor:'#e2e8f0', zerolinecolor:'#e2e8f0' }},
}};
const pCfg = {{ responsive:true, displayModeBar:false }};

const chartColors = ['#6366f1','#10b981','#f43f5e','#f59e0b','#8b5cf6','#06b6d4'];

Object.keys(DATA).forEach(sid => {{
  const c = DATA[sid].charts;
  const species = DATA[sid].species_names;

  // Species counts
  const countTraces = species.map((sp, i) => ({{
    x: c.times, y: c.counts[sp], type:'scatter', mode:'lines+markers',
    line:{{ color: SPECIES_COLORS[sp] || chartColors[i % chartColors.length], width:2 }},
    marker:{{ size:4 }}, name: sp,
  }}));
  Plotly.newPlot('chart-counts-'+sid, countTraces, {{
    ...pLayout,
    title:{{ text:'Species Counts', font:{{ size:12, color:'#334155' }} }},
    yaxis:{{...pLayout.yaxis, title:{{ text:'Count', font:{{ size:10 }} }} }},
    legend:{{ font:{{ size:9 }}, bgcolor:'rgba(0,0,0,0)' }}, showlegend:true
  }}, pCfg);

  // Total molecules
  Plotly.newPlot('chart-total-'+sid, [{{
    x:c.times, y:c.totals, type:'scatter', mode:'lines+markers',
    line:{{ color:'#6366f1', width:2 }}, marker:{{ size:4 }},
    fill:'tozeroy', fillcolor:'rgba(99,102,241,0.06)',
  }}], {{
    ...pLayout,
    title:{{ text:'Total Molecules', font:{{ size:12, color:'#334155' }} }},
    yaxis:{{...pLayout.yaxis, title:{{ text:'Count', font:{{ size:10 }} }} }},
    showlegend:false
  }}, pCfg);

  // Phase portrait (first two species)
  if (species.length >= 2) {{
    Plotly.newPlot('chart-phase-'+sid, [{{
      x:c.counts[species[0]], y:c.counts[species[1]],
      type:'scatter', mode:'lines+markers',
      line:{{ color:'#8b5cf6', width:1.5 }},
      marker:{{ size:4, color:c.times, colorscale:'Viridis', showscale:true,
                colorbar:{{ title:'Time', thickness:10, len:0.6 }} }},
    }}], {{
      ...pLayout,
      title:{{ text:'Phase Portrait', font:{{ size:12, color:'#334155' }} }},
      xaxis:{{...pLayout.xaxis, title:{{ text:species[0]+' count', font:{{ size:10 }} }} }},
      yaxis:{{...pLayout.yaxis, title:{{ text:species[1]+' count', font:{{ size:10 }} }} }},
      showlegend:false
    }}, pCfg);
  }} else {{
    document.getElementById('chart-phase-'+sid).innerHTML =
      '<div style="display:flex;align-items:center;justify-content:center;height:280px;color:#94a3b8;">Need 2+ species for phase portrait</div>';
  }}

  // Normalized species fractions
  const fractionTraces = species.map((sp, i) => {{
    const fracs = c.counts[sp].map((v, j) => c.totals[j] > 0 ? v / c.totals[j] : 0);
    return {{
      x: c.times, y: fracs, type:'scatter', mode:'lines',
      line:{{ color: SPECIES_COLORS[sp] || chartColors[i % chartColors.length], width:2 }},
      name: sp, stackgroup:'one',
    }};
  }});
  Plotly.newPlot('chart-ratio-'+sid, fractionTraces, {{
    ...pLayout,
    title:{{ text:'Species Fractions', font:{{ size:12, color:'#334155' }} }},
    yaxis:{{...pLayout.yaxis, title:{{ text:'Fraction', font:{{ size:10 }} }}, range:[0,1] }},
    legend:{{ font:{{ size:9 }}, bgcolor:'rgba(0,0,0,0)' }}, showlegend:true
  }}, pCfg);
}});

</script>
</body>
</html>"""

    with open(output_path, 'w') as f:
        f.write(html)
    print(f'Report saved to {output_path}')


def run_demo():
    demo_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(demo_dir, 'report.html')

    sim_results = []
    for cfg in CONFIGS:
        print(f'Running: {cfg["title"]}...')
        snapshots, runtime = run_simulation(cfg)
        sim_results.append((cfg, (snapshots, runtime)))
        print(f'  Runtime: {runtime:.2f}s')
        print(f'  {len(snapshots)} snapshots collected')

    print('Generating HTML report...')
    generate_html(sim_results, output_path)

    # Open in Safari
    import subprocess
    subprocess.run(['open', '-a', 'Safari', output_path])


if __name__ == '__main__':
    run_demo()
