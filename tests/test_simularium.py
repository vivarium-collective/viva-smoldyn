"""Integration: a Smoldyn composite run -> emitted positions -> .simularium.

Exercises the real seam viva-smoldyn ships for: SmoldynProcess emits
molecule_positions in the point-agent shape, and viva_simularium's
SimulariumAnalysis turns a run's emitted rows into a Simularium file.
"""
from bigraph_schema import allocate_core
from process_bigraph import Composite, gather_emitter_results

from viva_simularium import SimulariumAnalysis
from viva_smoldyn.composites import register_smoldyn


def _document(interval):
    return {
        "smoldyn": {
            "_type": "process",
            "address": "local:SmoldynProcess",
            "config": {
                "dimensions": 3,
                "bounds": [[0, 20], [0, 20], [0, 20]],
                "boundary_type": "r",
                "dt": 0.01,
                "seed": 1,
                "species": {"A": {"difc": 2.0, "count": 25, "display_size": 1.0}},
                "reactions": [],
            },
            "interval": interval,
            "inputs": {},
            "outputs": {
                "molecule_positions": ["stores", "molecule_positions"],
                "molecule_counts": ["stores", "molecule_counts"],
                "time": ["stores", "time"],
            },
        },
        "stores": {},
        "emitter": {
            "_type": "step",
            "address": "local:ram-emitter",
            "config": {"emit": {"molecule_positions": "list",
                                "molecule_counts": "map[integer]",
                                "time": "float"}},
            "inputs": {
                "molecule_positions": ["stores", "molecule_positions"],
                "molecule_counts": ["stores", "molecule_counts"],
                "time": ["stores", "time"],
            },
        },
    }


def test_smoldyn_run_to_simularium(tmp_path):
    sim = Composite({"state": _document(0.5)}, core=register_smoldyn())
    for _ in range(5):
        sim.update({}, 0.5)
    rows = next(iter(gather_emitter_results(sim).values()), [])
    assert rows, "expected emitted rows"

    out = tmp_path / "run"
    analysis = SimulariumAnalysis(
        {"output_path": str(out), "box_size": [20, 20, 20]},
        core=allocate_core())
    result = analysis.analyze(rows)

    written = tmp_path / "run.simularium"
    assert written.exists()
    assert result["n_agents_max"] == 25
    assert result["n_frames"] >= 5
    with open(written, "rb") as fh:
        assert fh.read(16) == b"SIMULARIUMBINARY"
