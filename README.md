# viva-smoldyn

Process-bigraph wrapper for the [Smoldyn](http://www.smoldyn.org/) particle-based spatial stochastic simulator.

**[View Interactive Demo Report](https://vivarium-collective.github.io/viva-smoldyn/)** -- MinDE oscillations, Lotka-Volterra, and gene expression with 3D particle viewers, Plotly charts, and bigraph architecture diagrams.

Smoldyn simulates biochemical reaction networks with spatial resolution at the single-molecule level using Brownian dynamics. This package wraps Smoldyn as a `process-bigraph` Process, enabling it to be composed with other simulation tools in modular, hierarchical simulations.

## Installation

Smoldyn requires building from source on Apple Silicon. After building:

```bash
git clone https://github.com/vivarium-collective/viva-smoldyn.git
cd viva-smoldyn
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quick Start

```python
from process_bigraph import Composite, allocate_core, gather_emitter_results
from process_bigraph.emitter import RAMEmitter
from viva_smoldyn import SmoldynProcess, make_smoldyn_document

core = allocate_core()
core.register_link('SmoldynProcess', SmoldynProcess)
core.register_link('ram-emitter', RAMEmitter)

doc = make_smoldyn_document(
    species={
        'A': {'difc': 1.0, 'count': 200},
        'B': {'difc': 0.5, 'count': 50},
    },
    reactions=[
        {'name': 'convert', 'subs': ['A'], 'prds': ['B'], 'rate': 0.01},
    ],
    interval=5.0,
)

sim = Composite({'state': doc}, core=core)
sim.run(50.0)

results = gather_emitter_results(sim)
for entry in results[('emitter',)]:
    print(f"t={entry['time']:.0f}  counts={entry['molecule_counts']}")
```

## API Reference

### SmoldynProcess

A time-driven `Process` that wraps a Smoldyn simulation using the bridge pattern.

**Config:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dimensions` | int | 2 | Spatial dimensionality (2 or 3) |
| `bounds` | list | [[0,100],[0,100]] | Per-dimension [low, high] boundaries |
| `boundary_type` | str | 'r' | Boundary condition ('r'=reflect, 'p'=periodic, 'a'=absorb) |
| `dt` | float | 0.01 | Simulation timestep |
| `seed` | int | -1 | Random seed (-1 = random) |
| `species` | dict | {} | Species definitions: `{name: {difc, count, color}}` |
| `reactions` | list | [] | Reactions: `[{name, subs, prds, rate, kb(optional)}]` |

**Outputs:**

| Port | Type | Description |
|------|------|-------------|
| `molecule_counts` | map[integer] | Current count per species |
| `molecule_positions` | list | Per-step point agents `[{type, x, y, z, radius}, ...]` (the shape [viva-simularium](https://github.com/vivarium-collective/viva-simularium) consumes) |
| `time` | float | Current simulation time |

**Additional methods:**

- `get_molecule_positions()` — Returns the current positions as a list of point agents `{type, x, y, z, radius}` (`z` is 0.0 for 2D sims).

### make_smoldyn_document()

Factory function that returns a composite document dict with `SmoldynProcess`, stores, and a RAM emitter pre-wired.

## Architecture

```
                    ┌─────────────────────┐
                    │   SmoldynProcess    │
                    │  (bridge pattern)    │
                    │                     │
  config ──────────►│  _build_simulation() │
  (species,         │  runUntil(interval)  │
   reactions,       │  getMoleculeCount()  │
   bounds, dt)      └─────────┬───────────┘
                              │
                    ┌─────────▼───────────┐
                    │       stores        │
                    │  molecule_counts: {} │
                    │  time: float        │
                    └─────────┬───────────┘
                              │
                    ┌─────────▼───────────┐
                    │    ram-emitter       │
                    │  (time series data)  │
                    └─────────────────────┘
```

The wrapper uses Smoldyn's `runUntil()` for incremental time-stepping, and `getMoleculeCount()` for efficient state readout. The simulation is lazily initialized on first `update()` call.

## Demo

Generate the interactive HTML report:

```bash
python demo/demo_report.py
```

This runs three simulations — two-species diffusion, Lotka-Volterra predator-prey, and Michaelis-Menten enzyme kinetics — and produces `demo/report.html` with:

- Animated 2D particle viewers with time slider
- Species count time series (Plotly)
- Phase portraits
- Bigraph architecture diagrams
- Interactive PBG document trees

## Simularium export

`SmoldynProcess` emits `molecule_positions` each step, so a run's trajectory can
be converted to a [Simularium](https://simularium.allencell.org/) file via
[viva-simularium](https://github.com/vivarium-collective/viva-simularium)'s
`SimulariumAnalysis` — a post-sim `AnalysisStep` that reads a run's emitted rows
and writes a `.simularium`. Faithful demo (a real Smoldyn 3D reaction-diffusion
run through the Engine, no fabricated positions):

```bash
python demo/simularium_demo.py out/smoldyn_reaction_diffusion
# -> out/smoldyn_reaction_diffusion.simularium  (open at simularium.allencell.org)
```

In a workbench study, declare it as an analysis and it runs in the Evaluate-stage
flush over the emitter output.

## Workspace

This repo is also a process-bigraph **workspace** (`workspace.yaml`, package
`viva_smoldyn`, entry `viva_smoldyn.build_core`), so it can be served by the
[vivarium-workbench](https://github.com/vivarium-collective/vivarium-workbench)
and drive Studies. `build_core()` registers the Smoldyn process, RAM emitter,
the `SmoldynPlots` visualization, and the `simularium` analysis.

## Tests

```bash
pytest tests/ -v
```
