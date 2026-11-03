"""The default build path must not import the optional viva_superpowers package.

viva-superpowers requires bigraph-schema>=1.8.2, which conflicts with the
bigraph-schema==1.8.1 pin of the composed environment, so the default
core/composite path has to run with it absent. Runs in a subprocess so the
blocked import cannot leak into other tests.
"""

import subprocess
import sys
import textwrap


def test_default_path_runs_without_viva_superpowers():
    script = textwrap.dedent(
        """
        import sys
        sys.modules["viva_superpowers"] = None  # any import of it now raises ImportError
        from viva_smoldyn.core import build_core
        from viva_smoldyn.composites import build_composite

        core = build_core()
        sim = build_composite("reversible-dimerization", core=core)
        sim.run(1.0)
        sim = build_composite("reversible-dimerization")  # core=None branch
        sim.run(1.0)
        print("DEFAULT_PATH_OK")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert "DEFAULT_PATH_OK" in result.stdout
