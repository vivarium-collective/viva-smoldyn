"""Visualization Step subclasses for pbg-smoldyn.

Visualizations follow the pbg-superpowers convention (v0.4.15+):
each subclass overrides `update()` to consume per-step state via wires
(like an Emitter), accumulates history internally, and returns
``{'html': '<rendered figure>'}`` each step. The composite spec wires
the input ports to store paths.

See viva_superpowers.visualization for the base-class contract.
"""
from __future__ import annotations

from viva_superpowers.visualization import Visualization


class SmoldynPlots(Visualization):
    """Time-series HTML plot of Smoldyn's per-species molecule counts.

    Consumes the wrapper's `molecule_counts` (a map of species -> count) and
    `time` at each step, accumulates them across calls, and emits a Plotly
    HTML figure on every update. Downstream consumers (dashboards, notebook
    viewers) read the latest 'html' from the wired store.
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

    def update(self, state, interval=1.0):
        t = float(state.get('time', len(self.times) * (interval or 1.0)))
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
        return {'html': html}
