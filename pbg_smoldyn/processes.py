"""Smoldyn Process wrapper for process-bigraph.

Wraps the Smoldyn particle-based spatial stochastic simulator as a
time-driven Process using the bridge pattern. The internal Smoldyn
Simulation is lazily initialized on first update() call. Each update
advances the simulation by the requested time interval using runUntil(),
then reads back molecule counts and (optionally) positions.
"""

from process_bigraph import Process


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
        self._current_time = 0.0
        self._counts_initialized = False

    def inputs(self):
        return {}

    def outputs(self):
        return {
            'molecule_counts': 'overwrite[map[integer]]',
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
        low = [b[0] for b in cfg['bounds']]
        high = [b[1] for b in cfg['bounds']]

        self._sim = smoldyn.Simulation(
            low=low,
            high=high,
            boundary_type=cfg['boundary_type'],
            seed=cfg['seed'],
        )

        # Add species
        for name, spec in cfg['species'].items():
            difc = spec.get('difc', 1.0)
            color = spec.get('color', 'black')
            display_size = spec.get('display_size', 3)
            sp = self._sim.addSpecies(
                name, difc=difc, color=color, display_size=display_size)
            count = spec.get('count', 0)
            if count > 0:
                sp.addToSolution(count)
            self._species_names.append(name)
            self._species_objects[name] = sp

        # Add reactions
        for rxn in cfg['reactions']:
            subs = [self._species_objects[s] for s in rxn.get('subs', [])]
            prds = [self._species_objects[p] for p in rxn.get('prds', [])]
            rate = rxn.get('rate', 0.0)
            name = rxn.get('name', 'rxn')
            if 'kb' in rxn:
                self._sim.addBidirectionalReaction(
                    name, subs=subs, prds=prds,
                    kf=rate, kb=rxn['kb'])
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
        self._sim.updateSim()
        self._current_time = 0.0

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
            'time': self._current_time,
        }

    def get_molecule_positions(self):
        """Return current molecule positions as a list of dicts.

        Each dict has keys: species (str), x (float), y (float),
        and z (float) for 3D simulations. Must be called after
        initial_state() or update().

        Returns:
            list[dict]: Molecule positions at current time.
        """
        self._build_simulation()
        dim = self.config['dimensions']

        # Read the position data buffer (from most recent interval)
        mol_data = self._sim.getOutputData('molpos', True)
        if not mol_data:
            return []

        # Species index -> name mapping
        # Smoldyn species indices: 0=empty, 1=first_species, ...
        name_map = {0: 'empty'}
        for i, name in enumerate(self._species_names):
            name_map[i + 1] = name

        # Take only the last snapshot (last timestep in the buffer)
        # Group by step number (first column)
        last_step = mol_data[-1][0]
        positions = []
        for row in mol_data:
            if row[0] != last_step:
                continue
            species_idx = int(row[1])
            species_name = name_map.get(species_idx, f'unknown_{species_idx}')
            if species_name == 'empty':
                continue
            pos = {'species': species_name, 'x': row[3], 'y': row[4]}
            if dim >= 3:
                pos['z'] = row[5]
            positions.append(pos)

        return positions

    def update(self, state, interval):
        self._build_simulation()

        target_time = self._current_time + interval
        self._sim.runUntil(
            stop=target_time,
            dt=self.config['dt'],
            display=False,
        )
        self._current_time = target_time

        # Clear counts data buffer (we use direct queries instead)
        self._sim.getOutputData('counts', True)

        return self._read_state()
