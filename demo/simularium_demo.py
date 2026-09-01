"""Faithful Smoldyn -> Simularium demo.

Runs a real Smoldyn 3D reaction-diffusion simulation through the
process-bigraph Engine (``Composite``), records ``molecule_positions`` +
``molecule_counts`` + ``time`` with a RAM emitter, then converts the emitted
trajectory to a ``.simularium`` file via ``viva_simularium.SimulariumAnalysis``
— the same Analysis a workbench study runs in its post-sim flush.

Nothing here is fabricated: every particle position comes from Smoldyn's own
Brownian dynamics. Open the resulting ``.simularium`` in
https://simularium.allencell.org/ .

Usage:
    python demo/simularium_demo.py [output_path] [--steps N] [--json]
"""
from __future__ import annotations

import sys
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from viva_smoldyn.composites import register_smoldyn
from viva_simularium import SimulariumAnalysis
from bigraph_schema import allocate_core

# --- A faithful Smoldyn 3D reaction-diffusion system --------------------------
BOX = [50.0, 50.0, 50.0]
SPECIES = {
    "A": {"difc": 3.0, "count": 200, "color": "#ff5500", "display_size": 1.0},
    "B": {"difc": 1.0, "count": 0, "color": "#0088ff", "display_size": 1.6},
}
REACTIONS = [
    # Irreversible dimerization A + A -> B (a real bimolecular Smoldyn reaction).
    {"name": "dimerize", "subs": ["A", "A"], "prds": ["B"], "rate": 2.0},
]
DISPLAY = {
    "A": {"color": "#ff5500", "radius": 1.0},
    "B": {"color": "#0088ff", "radius": 1.6},
}


def _document(interval: float) -> dict:
    """A SmoldynProcess -> RAM-emitter composite that records positions."""
    return {
        "smoldyn": {
            "_type": "process",
            "address": "local:SmoldynProcess",
            "config": {
                "dimensions": 3,
                "bounds": [[0, BOX[0]], [0, BOX[1]], [0, BOX[2]]],
                "boundary_type": "r",
                "dt": 0.01,
                "seed": 1,
                "species": SPECIES,
                "reactions": REACTIONS,
            },
            "interval": interval,
            "inputs": {},
            "outputs": {
                "molecule_counts": ["stores", "molecule_counts"],
                "molecule_positions": ["stores", "molecule_positions"],
                "time": ["stores", "time"],
            },
        },
        "stores": {},
        "emitter": {
            "_type": "step",
            "address": "local:ram-emitter",
            "config": {
                "emit": {
                    "molecule_counts": "map[integer]",
                    "molecule_positions": "list",
                    "time": "float",
                },
            },
            "inputs": {
                "molecule_counts": ["stores", "molecule_counts"],
                "molecule_positions": ["stores", "molecule_positions"],
                "time": ["stores", "time"],
            },
        },
    }


def run(output_path: str, n_steps: int = 40, interval: float = 0.5,
        fmt: str = "binary") -> Path:
    core = register_smoldyn()
    sim = Composite({"state": _document(interval)}, core=core)
    for _ in range(n_steps):
        sim.update({}, interval)

    results = gather_emitter_results(sim)
    rows = next(iter(results.values()), [])
    print(f"Smoldyn run: {len(rows)} emitted frames")

    analysis = SimulariumAnalysis(
        {
            "output_path": output_path,
            "box_size": BOX,
            "display": DISPLAY,
            "title": "Smoldyn 3D reaction-diffusion",
            "spatial_unit": "nm",
            "time_unit": "s",
            "fmt": fmt,
        },
        core=allocate_core(),
    )
    out = analysis.analyze(rows)
    print(f"wrote {out['simularium_path']} "
          f"({out['n_frames']} frames, up to {out['n_agents_max']} agents/frame)")
    return Path(out["simularium_path"])


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out_path = args[0] if args else str(Path(__file__).parent / "smoldyn_reaction_diffusion")
    steps = 40
    if "--steps" in sys.argv:
        steps = int(sys.argv[sys.argv.index("--steps") + 1])
    fmt = "json" if "--json" in sys.argv else "binary"
    run(out_path, n_steps=steps, fmt=fmt)
