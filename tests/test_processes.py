"""Unit tests for SmoldynProcess."""

import pytest
from process_bigraph import allocate_core
from pbg_smoldyn.processes import SmoldynProcess


@pytest.fixture
def core():
    c = allocate_core()
    c.register_link('SmoldynProcess', SmoldynProcess)
    return c


def test_instantiation(core):
    proc = SmoldynProcess(
        config={
            'species': {'A': {'difc': 1.0, 'count': 100}},
        },
        core=core)
    assert proc.config['dimensions'] == 2
    assert proc.config['dt'] == 0.01
    assert 'A' in proc.config['species']


def test_initial_state(core):
    proc = SmoldynProcess(
        config={
            'species': {
                'A': {'difc': 1.0, 'count': 200},
                'B': {'difc': 0.5, 'count': 50},
            },
        },
        core=core)
    state = proc.initial_state()
    assert 'molecule_counts' in state
    assert 'time' in state
    assert state['molecule_counts']['A'] == 200
    assert state['molecule_counts']['B'] == 50
    assert state['time'] == 0.0


def test_single_update(core):
    proc = SmoldynProcess(
        config={
            'species': {
                'A': {'difc': 1.0, 'count': 100},
                'B': {'difc': 0.5, 'count': 50},
            },
            'reactions': [
                {'name': 'convert', 'subs': ['A'], 'prds': ['B'], 'rate': 0.01},
            ],
        },
        core=core)
    proc.initial_state()
    result = proc.update({}, interval=5.0)
    assert 'molecule_counts' in result
    assert 'time' in result
    assert isinstance(result['molecule_counts']['A'], int)
    assert isinstance(result['molecule_counts']['B'], int)
    assert result['time'] == 5.0


def test_conservation_no_reaction(core):
    """Without reactions, total molecule count stays constant."""
    proc = SmoldynProcess(
        config={
            'species': {
                'A': {'difc': 1.0, 'count': 100},
                'B': {'difc': 2.0, 'count': 75},
            },
        },
        core=core)
    state0 = proc.initial_state()
    total0 = sum(state0['molecule_counts'].values())

    result = proc.update({}, interval=10.0)
    total1 = sum(result['molecule_counts'].values())
    assert total1 == total0


def test_reaction_changes_counts(core):
    """With A->B reaction, A should decrease and B should increase."""
    proc = SmoldynProcess(
        config={
            'species': {
                'A': {'difc': 1.0, 'count': 500},
                'B': {'difc': 1.0, 'count': 0},
            },
            'reactions': [
                {'name': 'decay', 'subs': ['A'], 'prds': ['B'], 'rate': 0.1},
            ],
        },
        core=core)
    state0 = proc.initial_state()
    result = proc.update({}, interval=20.0)

    assert result['molecule_counts']['A'] < state0['molecule_counts']['A']
    assert result['molecule_counts']['B'] > state0['molecule_counts']['B']


def test_molecule_positions(core):
    proc = SmoldynProcess(
        config={
            'species': {'A': {'difc': 1.0, 'count': 50}},
            'bounds': [[0, 100], [0, 100]],
        },
        core=core)
    proc.initial_state()
    proc.update({}, interval=1.0)

    positions = proc.get_molecule_positions()
    assert len(positions) == 50
    for p in positions:
        assert 'species' in p
        assert 'x' in p
        assert 'y' in p
        assert p['species'] == 'A'
        assert 0 <= p['x'] <= 100
        assert 0 <= p['y'] <= 100


def test_outputs_schema(core):
    proc = SmoldynProcess(
        config={'species': {'A': {'difc': 1.0, 'count': 10}}},
        core=core)
    outputs = proc.outputs()
    assert 'molecule_counts' in outputs
    assert 'time' in outputs


def test_config_defaults(core):
    proc = SmoldynProcess(config={}, core=core)
    assert proc.config['dimensions'] == 2
    assert proc.config['dt'] == 0.01
    assert proc.config['boundary_type'] == 'r'
    assert proc.config['seed'] == -1


def test_multiple_updates(core):
    """Time advances correctly across multiple updates."""
    proc = SmoldynProcess(
        config={
            'species': {'A': {'difc': 1.0, 'count': 100}},
        },
        core=core)
    proc.initial_state()

    r1 = proc.update({}, interval=5.0)
    assert r1['time'] == 5.0

    r2 = proc.update({}, interval=5.0)
    assert r2['time'] == 10.0

    r3 = proc.update({}, interval=5.0)
    assert r3['time'] == 15.0
