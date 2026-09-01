"""Smoldyn composite documents + composite-spec discovery.

Two flavors of composite construction live in this package:

1. **Hand-coded factories** — `make_smoldyn_document(...)` builds a PBG
   state-dict programmatically for callers that want full control over
   species / reactions / wiring. Used by `demo/demo_report.py`.

2. **Declarative `*.composite.yaml`** — sibling files in this directory
   follow the viva-superpowers composite-spec convention.
   `build_composite()` loads one by name and instantiates
   `process_bigraph.Composite` with parameter substitution.

Both flavors are equivalent — pick the one that fits your use case.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any

import yaml
from process_bigraph import allocate_core
from process_bigraph.emitter import RAMEmitter

from viva_smoldyn.processes import SmoldynProcess


# ---------------------------------------------------------------------------
# Hand-coded composite factories (legacy / programmatic API)
# ---------------------------------------------------------------------------


def register_smoldyn(core=None):
    """Return a core with SmoldynProcess, the RAM emitter, and the
    SmoldynPlots Visualization registered."""
    if core is None:
        core = allocate_core()
    core.register_link('SmoldynProcess', SmoldynProcess)
    core.register_link('ram-emitter', RAMEmitter)
    # Register Visualization Steps so composites can wire them by name.
    from viva_smoldyn.visualizations import SmoldynPlots
    core.register_link('SmoldynPlots', SmoldynPlots)
    return core


def make_smoldyn_document(
    dimensions=2,
    bounds=None,
    boundary_type='r',
    dt=0.01,
    seed=-1,
    species=None,
    reactions=None,
    interval=1.0,
):
    """Create a composite document for a Smoldyn simulation.

    Returns a document dict ready for use with Composite().

    Args:
        dimensions: Spatial dimensionality (2 or 3)
        bounds: Per-dimension [low, high] boundaries
        boundary_type: Boundary type string ('r', 'p', 'a')
        dt: Simulation timestep
        seed: Random seed (-1 = random)
        species: Dict of {name: {difc, count}} species definitions
        reactions: List of {name, subs, prds, rate} reaction definitions
        interval: Time interval between process updates

    Returns:
        dict: Composite document with Smoldyn process, stores, and emitter
    """
    if bounds is None:
        bounds = [[0, 100]] * dimensions
    if species is None:
        species = {}
    if reactions is None:
        reactions = []

    return {
        'smoldyn': {
            '_type': 'process',
            'address': 'local:SmoldynProcess',
            'config': {
                'dimensions': dimensions,
                'bounds': bounds,
                'boundary_type': boundary_type,
                'dt': dt,
                'seed': seed,
                'species': species,
                'reactions': reactions,
            },
            'interval': interval,
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
            'config': {
                'emit': {
                    'molecule_counts': 'map[integer]',
                    'time': 'float',
                },
            },
            'inputs': {
                'molecule_counts': ['stores', 'molecule_counts'],
                'time': ['stores', 'time'],
            },
        },
    }


# ---------------------------------------------------------------------------
# Declarative composite-spec loader (*.composite.yaml)
# ---------------------------------------------------------------------------

_COMPOSITES_DIR = Path(__file__).parent

_FULL_PLACEHOLDER = re.compile(r"^\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}$")
_INLINE_PLACEHOLDER = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _cast(value: Any, declared_type: str | None) -> Any:
    if declared_type is None:
        return value
    if declared_type == "float":
        return float(value)
    if declared_type == "int":
        return int(value)
    if declared_type in ("string", "str"):
        return str(value)
    if declared_type == "bool":
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes")
        return bool(value)
    return value


def _substitute(state: Any, params: dict, overrides: dict) -> Any:
    if isinstance(state, dict):
        return {k: _substitute(v, params, overrides) for k, v in state.items()}
    if isinstance(state, list):
        return [_substitute(v, params, overrides) for v in state]
    if isinstance(state, str):
        m = _FULL_PLACEHOLDER.match(state)
        if m:
            pname = m.group(1)
            pdef = params.get(pname, {})
            raw = overrides.get(pname, pdef.get("default"))
            return _cast(raw, pdef.get("type"))
        if _INLINE_PLACEHOLDER.search(state):
            return _INLINE_PLACEHOLDER.sub(
                lambda mm: str(overrides.get(mm.group(1), params.get(mm.group(1), {}).get("default", ""))),
                state,
            )
    return state


def list_composite_specs() -> list[str]:
    """Return short names of every `*.composite.yaml` shipped in this package."""
    out: list[str] = []
    for path in sorted(_COMPOSITES_DIR.glob("*.composite.yaml")):
        out.append(path.name[: -len(".composite.yaml")])
    return out


def load_composite_spec(name: str) -> dict:
    """Load and parse a named composite spec. `name` is the stem (no suffix)."""
    path = _COMPOSITES_DIR / f"{name}.composite.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"composite spec not found: {path}")
    return yaml.safe_load(path.read_text())


def build_composite(name: str, *, overrides: dict | None = None, core=None):
    """Load a *.composite.yaml by name and instantiate process_bigraph.Composite.

    overrides: parameter overrides (keys must match spec.parameters)
    core:      optional pre-built core; otherwise register_smoldyn() is used
    """
    from process_bigraph import Composite

    spec = load_composite_spec(name)
    if not isinstance(spec, dict) or "state" not in spec or "name" not in spec:
        raise ValueError(f"composite '{name}' missing required keys (name, state)")

    if core is None:
        core = register_smoldyn()

    params = spec.get("parameters") or {}
    state = _substitute(spec.get("state") or {}, params, overrides or {})
    return Composite({"state": state}, core=core)
