"""Core builder for the viva-smoldyn workspace.

The dashboard and every runner call :func:`build_core` (not a bare
``allocate_core()``) so the workspace's own Process, emitter, visualization,
and post-sim analysis are registered regardless of how the editable install was
made. See viva-superpowers docs/conventions/discovery.md.
"""
from __future__ import annotations

from process_bigraph import allocate_core
from process_bigraph.emitter import RAMEmitter

from .processes import SmoldynProcess
from .types import register_types


def build_core(core=None):
    if core is None:
        core = allocate_core()
    register_types(core)
    core.register_link("SmoldynProcess", SmoldynProcess)
    core.register_link("ram-emitter", RAMEmitter)

    from .visualizations import SmoldynPlots
    core.register_link("SmoldynPlots", SmoldynPlots)

    # Post-sim Simularium converter (viva_simularium). Importing it registers
    # it in viva_superpowers' ANALYSIS_REGISTRY (name "simularium") so a study's
    # Evaluate-stage flush can run it; also expose it as a link for wiring.
    try:
        from viva_simularium import SimulariumAnalysis
        core.register_link("SimulariumAnalysis", SimulariumAnalysis)
    except Exception:  # noqa: BLE001 — viva_simularium optional at import time
        pass

    return core
