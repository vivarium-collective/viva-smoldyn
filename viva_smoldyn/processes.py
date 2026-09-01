"""Smoldyn Process wrapper for process-bigraph.

Wraps the Smoldyn particle-based spatial stochastic simulator as a
time-driven Process using the bridge pattern. The internal Smoldyn
Simulation is lazily initialized on first update() call. Each update
advances the simulation by the requested time interval using runUntil(),
then reads back molecule counts and (optionally) positions.
"""

import contextlib
import os
import sys

from process_bigraph import Process


@contextlib.contextmanager
def _suppress_c_output():
    """Silence Smoldyn's C-level stdout/stderr (its "Simulating" / "setting up"
    spam) for the duration of a call, at the file-descriptor level so it also
    catches prints from the compiled library — not just Python's sys.stdout.

    Essential when the process runs inside a subprocess runner (e.g. the
    vivarium-workbench) that parses a JSON result from the child's stdout: an
    unsilenced Smoldyn corrupts that stream and the run "can't be parsed".
    """
    import ctypes
    try:
        _libc = ctypes.CDLL(None)
    except Exception:  # noqa: BLE001 — no libc handle; Python-level flush only
        _libc = None
    sys.stdout.flush()
    sys.stderr.flush()
    saved = (os.dup(1), os.dup(2))
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        yield
    finally:
        # Flush the C stdio buffers WHILE devnull is still on fd 1/2 — Smoldyn's
        # output is fully-buffered under a pipe and would otherwise flush to the
        # restored real stdout after this block, defeating the suppression.
        if _libc is not None:
            try:
                _libc.fflush(None)
            except Exception:  # noqa: BLE001
                pass
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(saved[0], 1)
        os.dup2(saved[1], 2)
        os.close(saved[0])
        os.close(saved[1])
        os.close(devnull)


class SmoldynProcess(Process):
    """Bridge Process wrapping a Smoldyn spatial stochastic simulation.

    Builds a Smoldyn simulation programmatically from config parameters
    (species definitions, reactions, boundary geometry) and advances it
    incrementally via runUntil(). Returns molecule counts as overwrite
    outputs after each interval.

    Config:
        dimensions: Spatial dimensionality (2 or 3)
        bounds: Per-dimension [low, high] boundaries
        boundary_type: Boundary condition string ('r'=reflect, 'p'=periodic, 'a'=absorb)
        dt: Simulation timestep
        seed: Random seed (-1 = random)
        species: Dict of {name: {difc: float, count: int}} species definitions
        reactions: List of {name, subs, prds, rate} reaction definitions
    """

    config_schema = {
        'dimensions': {'_type': 'integer', '_default': 2},
        'bounds': {'_type': 'overwrite[list]', '_default': [[0, 100], [0, 100]]},
        'boundary_type': {'_type': 'string', '_default': 'r'},
        'dt': {'_type': 'float', '_default': 0.01},
        'seed': {'_type': 'integer', '_default': -1},
        'species': {'_type': 'overwrite[map]', '_default': {}},
        'reactions': {'_type': 'overwrite[list]', '_default': []},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._sim = None
        self._species_names = []
        self._species_objects = {}
        self._species_radius = {}
        self._current_time = 0.0
        self._counts_initialized = False
        self._last_positions = []

    def inputs(self):
        return {}

    def outputs(self):
        return {
            'molecule_counts': 'overwrite[map[integer]]',
            # Per-step point agents [{type, x, y, z, radius}, ...] — the shape
            # viva_simularium's SimulariumAnalysis consumes to build a trajectory.
            'molecule_positions': 'overwrite[list]',
            'time': 'overwrite[float]',
        }

    def initial_state(self):
        self._build_simulation()
        return self._read_state()

    def _build_simulation(self):
        """Lazily initialize the Smoldyn simulation from config."""
        if self._sim is not None:
            return

        import smoldyn

        cfg = self.config
        # Config values may arrive as strings (e.g. from a dashboard's ${param}
        # substitution or JSON overrides); coerce numeric fields defensively so
        # the process runs identically regardless of how it was built.
        low = [float(b[0]) for b in cfg['bounds']]
        high = [float(b[1]) for b in cfg['bounds']]

        self._sim = smoldyn.Simulation(
            low=low,
            high=high,
            boundary_type=cfg['boundary_type'],
            seed=int(cfg['seed']),
        )

        # Add species
        for name, spec in cfg['species'].items():
            difc = float(spec.get('difc', 1.0))
            color = spec.get('color', 'black')
            display_size = float(spec.get('display_size', 3))
            sp = self._sim.addSpecies(
                name, difc=difc, color=color, display_size=display_size)
            count = int(spec.get('count', 0))
            if count > 0:
                sp.addToSolution(count)
            self._species_names.append(name)
            self._species_objects[name] = sp
            # Radius surfaced on emitted positions (viewer sphere size).
            self._species_radius[name] = display_size

        # Add reactions
        for rxn in cfg['reactions']:
            subs = [self._species_objects[s] for s in rxn.get('subs', [])]
            prds = [self._species_objects[p] for p in rxn.get('prds', [])]
            rate = float(rxn.get('rate', 0.0))
            name = rxn.get('name', 'rxn')
            if 'kb' in rxn:
                self._sim.addBidirectionalReaction(
                    name, subs=subs, prds=prds,
                    kf=rate, kb=float(rxn['kb']))
            else:
                self._sim.addReaction(
                    name, subs=subs, prds=prds, rate=rate)

        # Set up data collection for counts
        self._sim.addOutputData('counts')
        self._sim.addCommand(cmd='molcount counts', cmd_type='E')

        # Position data collection (single-step snapshot approach)
        self._sim.addOutputData('molpos')
        self._sim.addCommand(cmd='listmols2 molpos', cmd_type='E')

        self._sim.setGraphics('none')
        with _suppress_c_output():
            self._sim.updateSim()
        self._current_time = 0.0
        # NOTE: do NOT read the 'molpos' buffer here — Smoldyn's getOutputData
        # segfaults on it before the first runUntil populates it. Positions
        # start empty and are filled by the first update().
        self._last_positions = []

    def _read_counts(self):
        """Read current molecule counts for all species."""
        from smoldyn._smoldyn import MolecState
        counts = {}
        for name in self._species_names:
            counts[name] = self._sim.getMoleculeCount(name, MolecState.all)
        return counts

    def _read_state(self):
        """Read current simulation state."""
        return {
            'molecule_counts': self._read_counts(),
            'molecule_positions': list(self._last_positions),
            'time': self._current_time,
        }

    def _read_positions(self):
        """Read + clear the molpos buffer and return the CURRENT snapshot as a
        list of point agents ``{type, x, y, z, radius}``.

        Consumes the buffer (``getOutputData(..., True)`` clears it) so each
        interval yields only that interval's molecules, and keeps just the last
        timestep in the buffer (the state at ``_current_time``). Caches the
        result in ``self._last_positions``.
        """
        # Species index -> name mapping (Smoldyn: 0=empty, 1=first_species, ...)
        name_map = {0: 'empty'}
        for i, name in enumerate(self._species_names):
            name_map[i + 1] = name

        mol_data = self._sim.getOutputData('molpos', True)
        positions = []
        if mol_data:
            last_step = mol_data[-1][0]
            dim = int(self.config['dimensions'])
            for row in mol_data:
                if row[0] != last_step:
                    continue
                species_name = name_map.get(int(row[1]), f'unknown_{int(row[1])}')
                if species_name == 'empty':
                    continue
                positions.append({
                    'type': species_name,
                    'x': float(row[3]),
                    'y': float(row[4]),
                    'z': float(row[5]) if dim >= 3 else 0.0,
                    'radius': self._species_radius.get(species_name, 1.0),
                })
        self._last_positions = positions
        return positions

    def get_molecule_positions(self):
        """Return the most recent molecule positions as a list of point agents
        ``{type, x, y, z, radius}``. Populated by ``initial_state()`` /
        ``update()``; ``z`` is 0.0 for 2D simulations."""
        self._build_simulation()
        return list(self._last_positions)

    def update(self, state, interval):
        self._build_simulation()

        target_time = self._current_time + interval
        with _suppress_c_output():
            self._sim.runUntil(
                stop=target_time,
                dt=float(self.config['dt']),
                display=False,
            )
        self._current_time = target_time

        # Clear counts data buffer (we use direct queries instead)
        self._sim.getOutputData('counts', True)
        # Refresh the current molecule-position snapshot for this interval.
        self._read_positions()

        return self._read_state()
