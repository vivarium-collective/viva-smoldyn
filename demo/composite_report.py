"""Composite-driven demo: load a *.composite.yaml, run it, render a report.

Demonstrates the viva-superpowers composite-spec convention end-to-end:

    1. List composite specs shipped with the wrapper package.
    2. Load one by name; instantiate a process_bigraph.Composite via the
       package's `build_composite()` loader.
    3. Drive it forward N steps with `composite.update()`.
    4. Collect emitter results via `gather_emitter_results()`.
    5. Render a small self-contained HTML report (Plotly + a bigraph-viz
       architecture diagram + a YAML source preview).

This is intentionally small. Wrappers should treat it as a template for
their own composite-driven reports: copy the structure, swap the
package import, swap the chart panels for whatever signals matter for
that simulator.
"""
from __future__ import annotations
import base64
import html as _html
import os
import tempfile

from process_bigraph import gather_emitter_results

from viva_smoldyn.composites import (
    _COMPOSITES_DIR,
    build_composite,
    list_composite_specs,
    load_composite_spec,
)


def run(spec_name: str, n_steps: int = 20, interval: float | None = None):
    """Build the composite, step it n_steps times, return collected results.

    Also extracts the latest 'viz_html' store value (if the composite wires
    a Visualization Step to a store named 'viz_html'), so the report can
    embed the live figure produced by the running simulation.
    """
    sim = build_composite(spec_name)
    spec = load_composite_spec(spec_name)
    step_interval = float(interval if interval is not None else
                           (spec.get("parameters") or {})
                           .get("interval", {}).get("default", 1.0))
    for _ in range(n_steps):
        sim.update({}, step_interval)
    results = gather_emitter_results(sim)
    state = sim.state.get("state", sim.state)
    viz_html = (state.get("stores") or {}).get("viz_html", "")
    return spec, results, step_interval, viz_html


def _bigraph_png(spec: dict) -> str:
    """Render a bigraph-viz architecture diagram from the spec's state."""
    try:
        from bigraph_viz import plot_bigraph
    except ImportError:
        return ""
    out = tempfile.mkdtemp()
    plot_bigraph(
        state=spec.get("state") or {},
        out_dir=out, filename="arch",
        file_format="png",
        rankdir="LR",
    )
    with open(os.path.join(out, "arch.png"), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def render_html(spec: dict, results: dict, step_interval: float,
                spec_path: str, viz_html: str = "") -> str:
    """Return a self-contained HTML report for the run."""
    # Flatten the first emitter's rows into time-series
    rows = next(iter(results.values()), [])
    times = [r.get("time", i * step_interval) for i, r in enumerate(rows)]
    # Identify scalar signals (including flattened map values)
    scalars: set[str] = set()
    for r in rows:
        for k, v in r.items():
            if k == "time":
                continue
            if isinstance(v, (int, float)):
                scalars.add(k)
            elif isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    if isinstance(sub_v, (int, float)):
                        scalars.add(f"{k}.{sub_k}")
    traces_js = []
    for s in sorted(scalars):
        if "." in s:
            top, sub = s.split(".", 1)
            ys = [(r.get(top) or {}).get(sub) for r in rows]
        else:
            ys = [r.get(s) for r in rows]
        traces_js.append(
            f'{{x:{times!r}, y:{ys!r}, type:"scatter", mode:"lines", name:{s!r}}}'
        )

    yaml_src = _html.escape(open(spec_path).read())
    arch_img = _bigraph_png(spec)
    arch_html = (
        f'<img src="{arch_img}" alt="bigraph architecture" '
        f'style="max-width:100%;border:1px solid #e2e8f0;border-radius:8px;padding:8px;background:#fafafa">'
        if arch_img else "<em>bigraph-viz not installed; skipping diagram</em>"
    )

    viz_block = (
        f'<h2>Visualization Step output</h2>'
        f'<p class="lead">Live HTML produced by the wired <code>Visualization</code> Step '
        f'(consumes per-step state, accumulates internally, renders Plotly each update).</p>'
        f'<div style="border:1px solid #e2e8f0;border-radius:6px;padding:1rem">{viz_html}</div>'
    ) if viz_html else ""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{spec.get('name', spec_path)}</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 980px;
         margin: 2rem auto; color: #1e293b; line-height: 1.55; padding: 0 1rem; }}
  h1 {{ margin-bottom: 0.2rem }}
  .lead {{ color: #64748b }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;
           margin-top: 1.5rem }}
  pre {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;
         padding: .9rem 1.1rem; overflow: auto; font-size: .8rem }}
  h2 {{ margin-top: 2rem; padding-bottom: .3rem; border-bottom: 1px solid #e2e8f0 }}
  #chart {{ height: 380px }}
</style></head>
<body>
  <h1>{spec.get('name')}</h1>
  <p class="lead">{spec.get('description', '')}</p>
  <p><small>Source: <code>{spec_path}</code> · {len(rows)} emitter rows ·
     interval {step_interval}</small></p>

  {viz_block}

  <h2>Emitter time-series</h2>
  <div id="chart"></div>
  <script>
    Plotly.newPlot('chart', [{','.join(traces_js)}], {{
      margin: {{l:55, r:15, t:25, b:40}},
      legend: {{orientation: 'h', y: -0.2}},
      xaxis: {{title: 'time'}},
    }}, {{responsive: true, displayModeBar: false}});
  </script>

  <div class="grid">
    <div>
      <h2>Bigraph architecture</h2>
      {arch_html}
    </div>
    <div>
      <h2>Composite spec (YAML)</h2>
      <pre>{yaml_src}</pre>
    </div>
  </div>
</body></html>
"""


def main(spec_name: str | None = None, n_steps: int = 20,
         output_path: str | None = None):
    if spec_name is None:
        specs = list_composite_specs()
        if not specs:
            raise SystemExit("No *.composite.yaml found in viva_smoldyn/composites/")
        spec_name = specs[0]

    print(f"Running composite '{spec_name}' for {n_steps} steps...")
    spec, results, step_interval, viz_html = run(spec_name, n_steps=n_steps)
    spec_path = str(_COMPOSITES_DIR / f"{spec_name}.composite.yaml")
    html = render_html(spec, results, step_interval, spec_path, viz_html=viz_html)

    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"{spec_name}-report.html",
        )
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Report saved to {output_path}")
    return output_path


if __name__ == "__main__":
    main()
