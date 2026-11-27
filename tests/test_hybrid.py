"""Tests for SmoldynHybridProcess — the field-coupled (pyhybrid) Smoldyn process.

The interface/registration checks always run. The functional check needs a
Smoldyn build with the hybrid API (``smoldyn._smoldyn.HybridGrid``; the vcell
fork) and is skipped otherwise — the deep hybrid PDE/particle coupling is
exercised end-to-end in viva-pde-particle, which reuses this process.
"""
import pytest

from viva_smoldyn import SmoldynHybridProcess, build_core


def _hybrid_available():
    try:
        import smoldyn._smoldyn as _s
        return hasattr(_s, "HybridGrid")
    except Exception:
        return False


def test_registers_additively():
    core = build_core()
    assert "SmoldynHybridProcess" in core.link_registry
    # the existing process is untouched
    assert "SmoldynProcess" in core.link_registry


def test_interface():
    # Ports are declared from the class, independent of the engine build.
    assert set(SmoldynHybridProcess.config_schema) == {
        "grid", "config_text", "particle_species", "field_species",
        "dt", "step_multiplier", "quiet", "emit_positions",
    }
    inst = SmoldynHybridProcess.__new__(SmoldynHybridProcess)
    assert inst.inputs() == {"fields": "map[array[float]]"}
    outs = inst.outputs()
    assert outs["particle_counts"] == "map[overwrite[array[float]]]"
    assert "particle_totals" in outs and "particle_positions" in outs


@pytest.mark.skipif(not _hybrid_available(),
                    reason="Smoldyn build lacks the hybrid API (HybridGrid); vcell fork required")
def test_grid_binned_counts_sum_to_total():
    """A minimal hybrid model: no reactions, a fixed count, advanced one step —
    the per-node histogram must sum to the molecule total."""
    core = build_core()
    config_text = "\n".join([
        "dim 2",
        "boundaries 0 0 10",
        "boundaries 1 0 10",
        "species A",
        "difc A 1",
        "time_start 0",
        "time_stop 1",
        "time_step 0.01",
        "mol 100 A u u",
        "end_file",
    ])
    proc = SmoldynHybridProcess({
        "grid": {"origin": [0.0, 0.0], "size": [10.0, 10.0], "num": [11, 11]},
        "config_text": config_text,
        "particle_species": ["A"],
        "field_species": [],
        "dt": 0.01,
        "step_multiplier": 1,
    }, core=core)
    state = proc.initial_state()
    counts = state["particle_counts"]["A"]
    assert float(counts.sum()) == pytest.approx(state["particle_totals"]["A"])
