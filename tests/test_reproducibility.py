"""Seeded runs are reproducible: same seed gives the same counts, another seed differs."""

from process_bigraph import Composite, allocate_core

from viva_smoldyn.composites import make_smoldyn_document, register_smoldyn

CHECKPOINTS = (5.0, 10.0, 15.0)


def _counts_at_checkpoints(seed):
    doc = make_smoldyn_document(
        dimensions=2,
        bounds=[[0, 50], [0, 50]],
        boundary_type="r",
        dt=0.01,
        seed=seed,
        species={
            "A": {"difc": 1.0, "count": 200},
            "B": {"difc": 1.0, "count": 0},
        },
        reactions=[
            {"name": "convert", "subs": ["A"], "prds": ["B"], "rate": 0.1},
        ],
        interval=5.0,
    )
    sim = Composite({"state": doc}, core=register_smoldyn(allocate_core()))
    out = []
    for _ in CHECKPOINTS:
        sim.run(5.0)
        out.append(dict(sim.state["stores"]["molecule_counts"]))
    return out


def test_same_seed_gives_identical_counts():
    assert _counts_at_checkpoints(7) == _counts_at_checkpoints(7)


def test_different_seed_gives_different_counts():
    assert _counts_at_checkpoints(7) != _counts_at_checkpoints(8)
