# viva-smoldyn

Process-bigraph wrapper for the [Smoldyn](http://www.smoldyn.org/) particle-based
spatial stochastic simulator, with **[Simularium](https://simularium.allencell.org/)
trajectory export** so a run's particle motion can be replayed in 3D.

**▶ [Open the read-only dashboard](https://vivarium-collective.github.io/viva-smoldyn/)**
— browse the `smoldyn-simularium` investigation (reversible dimerization,
differential diffusion, enzyme kinetics), inspect each model's config, and open
its trajectory in the **Simularium Viewer** right in the browser.

Smoldyn simulates biochemical reaction networks with spatial resolution at the
single-molecule level using Brownian dynamics. This package wraps Smoldyn as a
`process-bigraph` Process, so it composes with other simulators and runs through
the [vivarium-workbench](https://github.com/vivarium-collective/vivarium-workbench)
as Studies.

## What's inside

- **`SmoldynProcess`** (`viva_smoldyn/processes.py`) — a time-driven Process that
  builds a Smoldyn simulation from config (species, reactions, boundary geometry),
  advances it with `runUntil()`, and emits `molecule_counts`, per-molecule
  `molecule_positions` (`{type, x, y, z, radius}`), and `time` each step.
- **Simularium export** — the per-step positions feed
  [viva-simularium](https://github.com/vivarium-collective/viva-simularium)'s
  `SimulariumAnalysis`, a post-sim analysis that writes a `.simularium`
  trajectory. In a workbench Study it runs automatically in the Evaluate-stage
  flush; the **Simularium Viewer** analysis tool opens the result.
- **A workspace + studies** — this repo is also a process-bigraph workspace
  (`workspace.yaml`, `viva_smoldyn.build_core`). The `smoldyn-simularium`
  investigation ships three studies, each with a `.simularium` trajectory:
  | Study | Model |
  |---|---|
  | `smoldyn-dimerization` | reversible dimerization `A + A ⇌ B` (3D) |
  | `smoldyn-crowding` | three species diffusing at different rates, demixing by mobility (3D) |
  | `smoldyn-enzyme-kinetics` | Michaelis–Menten `E + S ⇌ ES → E + P` (3D) |

## Installation

```bash
git clone https://github.com/vivarium-collective/viva-smoldyn.git
cd viva-smoldyn
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Apple Silicon (arm64) note

`viva-smoldyn` depends on `smoldyn` (from PyPI). **The PyPI `smoldyn` wheel for
macOS is x86_64-only** — the wheel tagged for Apple Silicon actually ships an
x86_64 binary (`_smoldyn…darwin.so: Mach-O … x86_64`), and there is no Python
3.12 wheel — so on an arm64 Mac a plain `pip install` gives
`import smoldyn` → `ImportError: incompatible architecture`. Two ways to get a
working Smoldyn first, then install viva-smoldyn on top:

**A. Native arm64 (recommended) — build Smoldyn from source.** Requires CMake and
a C/C++ toolchain (`xcode-select --install`):

```bash
# in the same venv, BEFORE `pip install -e .`
git clone https://github.com/ssandrews/Smoldyn.git
pip install ./Smoldyn            # builds the smoldyn Python module natively for arm64
python -c "import smoldyn; print(smoldyn.__version__)"   # verify it imports
pip install -e .                 # smoldyn is already satisfied; won't re-pull the wheel
```

(See <https://www.smoldyn.org/download.html> if the source layout changes.)

**B. Stopgap — run under an x86_64 (Rosetta) Python.** The x86_64 wheel *does*
work in an x86_64 interpreter:

```bash
softwareupdate --install-rosetta --agree-to-license   # once, if needed
arch -x86_64 /usr/bin/python3 -m venv .venv-x86
source .venv-x86/bin/activate
arch -x86_64 pip install -e ".[dev]"                  # pulls the x86_64 smoldyn wheel
```

The underlying wheel bug is upstream in Smoldyn, tracked at
<https://github.com/ssandrews/Smoldyn>.

## Quick start

```python
from process_bigraph import Composite, gather_emitter_results
from viva_smoldyn.composites import build_composite

sim = build_composite("reversible-dimerization")
for _ in range(40):
    sim.update({}, 0.5)

rows = next(iter(gather_emitter_results(sim).values()))
print(rows[-1]["molecule_counts"])           # {'A': ..., 'B': ...}
print(len(rows[-1]["molecule_positions"]))   # per-molecule positions
```

### A Simularium trajectory from a Smoldyn run

```bash
python demo/simularium_demo.py out/reaction_diffusion
# -> out/reaction_diffusion.simularium  (open at simularium.allencell.org, or via
#    the workbench's Simularium Viewer tool)
```

Every particle position is Smoldyn's own Brownian dynamics — nothing is
fabricated.

## Run the dashboard locally

```bash
pip install vivarium-workbench
vivarium-workbench serve --workspace .
```

Then, per Study:
- **Model** tab — the composite card plus a **Configuration** block showing the
  Smoldyn model (species / reactions / bounds) that generates the run.
- **Simulation** tab / **Runs** — each run advertises the **Simularium Viewer**
  tool; click it to replay the trajectory.
- **Analysis** tab — the Simularium Viewer, matched to every study with a
  trajectory.

## `SmoldynProcess` reference

**Config:** `dimensions` (2/3), `bounds` (per-dim `[low, high]`), `boundary_type`
(`r`/`p`/`a`), `dt`, `seed`, `species` (`{name: {difc, count, color, display_size}}`),
`reactions` (`[{name, subs, prds, rate, kb?}]`). Numeric fields are coerced, so
string-valued params from a dashboard/JSON override work unchanged.

**Outputs:** `molecule_counts` (`map[integer]`), `molecule_positions`
(`list` of `{type, x, y, z, radius}`), `time` (`float`).

## Tests

```bash
pytest tests/ -v
```
