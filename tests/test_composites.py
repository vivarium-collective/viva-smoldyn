"""Integration tests for Smoldyn composites."""

import pytest
from process_bigraph import Composite, allocate_core, gather_emitter_results
from process_bigraph.emitter import RAMEmitter
from pbg_smoldyn.processes import SmoldynProcess
from pbg_smoldyn.composites import make_smoldyn_document


@pytest.fixture
def core():
    c = allocate_core()
    c.register_link('SmoldynProcess', SmoldynProcess)
    c.register_link('ram-emitter', RAMEmitter)
    return c


def test_composite_assembly(core):
    doc = make_smoldyn_document(
        species={'A': {'difc': 1.0, 'count': 100}},
        interval=5.0)
    sim = Composite({'state': doc}, core=core)
    assert sim is not None


def test_composite_short_run(core):
    doc = make_smoldyn_document(
        species={
            'A': {'difc': 1.0, 'count': 100},
            'B': {'difc': 0.5, 'count': 50},
        },
        reactions=[
            {'name': 'convert', 'subs': ['A'], 'prds': ['B'], 'rate': 0.01},
        ],
        interval=5.0)
    sim = Composite({'state': doc}, core=core)
    sim.run(10.0)

    stores = sim.state['stores']
    assert 'molecule_counts' in stores
    assert stores['time'] > 0
    total = sum(stores['molecule_counts'].values())
    assert total == 150  # conserved


def test_emitter_collects_timeseries(core):
    doc = make_smoldyn_document(
        species={'A': {'difc': 1.0, 'count': 200}},
        interval=5.0)
    sim = Composite({'state': doc}, core=core)
    sim.run(20.0)

    raw_results = gather_emitter_results(sim)
    emitter_data = raw_results[('emitter',)]
    assert len(emitter_data) >= 2
    assert 'molecule_counts' in emitter_data[0]
    assert 'time' in emitter_data[0]


def test_document_factory_params(core):
    doc = make_smoldyn_document(
        dimensions=2,
        bounds=[[0, 50], [0, 50]],
        boundary_type='p',
        species={
            'X': {'difc': 2.0, 'count': 300},
            'Y': {'difc': 0.1, 'count': 10},
        },
        dt=0.005,
        interval=2.0)
    sim = Composite({'state': doc}, core=core)
    sim.run(4.0)
    stores = sim.state['stores']
    total = sum(stores['molecule_counts'].values())
    assert total == 310  # no reactions, conserved
