"""Packaged wheels must ship the declarative composite specs.

build_composite() loads composites/<name>.composite.yaml from the installed
package directory; a wheel without them raises FileNotFoundError at runtime.
"""

import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_declares_composite_package_data():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    package_data = data["tool"]["setuptools"]["package-data"]
    assert "composites/*.yaml" in package_data["viva_smoldyn"]


def test_built_wheel_contains_composite_specs(tmp_path):
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path), str(ROOT)],
        check=True,
        capture_output=True,
        timeout=600,
    )
    (wheel,) = tmp_path.glob("viva_smoldyn-*.whl")
    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
    specs = {n for n in names if n.startswith("viva_smoldyn/composites/") and n.endswith(".composite.yaml")}
    assert "viva_smoldyn/composites/reversible-dimerization.composite.yaml" in specs
    assert len(specs) == 5, sorted(specs)
