"""Pre-built composite document factories for Smoldyn simulations."""


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
