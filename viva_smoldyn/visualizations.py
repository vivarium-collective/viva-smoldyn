"""Visualization Step subclasses for viva-smoldyn.

Visualizations follow the new-style viva-superpowers convention: each
subclass consumes per-step state via wires (like an Emitter), buffers the
per-step history in ``accumulate(state)`` (no rendering), and builds the
Plotly figure ONCE in ``render() -> str``. The baseclass orchestrator owns
``update()`` — subclasses do NOT override it. The composite spec wires the
input ports to store paths.

See viva_superpowers.visualization for the base-class contract.
"""
from __future__ import annotations

from viva_superpowers.visualization import Visualization


class SmoldynPlots(Visualization):
    """Time-series HTML plot of Smoldyn's per-species molecule counts.

    Consumes the wrapper's `molecule_counts` (a map of species -> count) and
    `time` at each step, buffering them across calls in ``accumulate``. The
    Plotly HTML figure is built once in ``render`` at end-of-run (instead of
    rebuilt on every tick). Downstream consumers (dashboards, notebook
    viewers) read the rendered 'html' from the wired store.
    """

    config_schema = {
        'title': {'_type': 'string', '_default': 'Smoldyn molecule counts'},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: list[float] = []
        # species_name -> list of counts aligned with self.times
        self.history: dict[str, list[int]] = {}

    def inputs(self):
        return {
            'molecule_counts': 'map[integer]',
            'time': 'float',
        }

    def accumulate(self, state):
        """Buffer one step of counts — no figure build."""
        t = float(state.get('time', len(self.times)))
        self.times.append(t)

        counts = state.get('molecule_counts') or {}
        # Ensure every observed species has a list of the right length.
        idx = len(self.times) - 1
        for sp, val in counts.items():
            if sp not in self.history:
                # Back-fill zeros for steps before this species first appeared.
                self.history[sp] = [0] * idx
            # Pad in case some prior step skipped this species.
            while len(self.history[sp]) < idx:
                self.history[sp].append(0)
            self.history[sp].append(int(val) if val is not None else 0)
        # Pad any species not present this step.
        for sp, ys in self.history.items():
            while len(ys) < len(self.times):
                ys.append(0)

    def render(self) -> str:
        """Build the Plotly figure once from the accumulated history."""
        title = (self.config or {}).get('title', 'Smoldyn molecule counts')
        traces = []
        for sp, ys in sorted(self.history.items()):
            traces.append(
                '{"x":' + repr(self.times) + ',"y":' + repr(ys) +
                ',"type":"scatter","mode":"lines","name":"' + sp + '"}'
            )
        html = (
            f'<div id="smoldyn-counts" style="height:380px"></div>'
            f'<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>'
            f'<script>Plotly.newPlot("smoldyn-counts",[{",".join(traces)}],'
            f'{{title:"{title}",margin:{{l:55,r:15,t:35,b:40}},'
            f'xaxis:{{title:"time"}},yaxis:{{title:"molecule count"}},'
            f'legend:{{orientation:"h",y:-0.2}}}},'
            f'{{responsive:true,displayModeBar:false}});</script>'
        )
        return html
