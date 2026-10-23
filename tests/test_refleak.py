"""Check that loading trame-pyvista through PyVista leaves no VTK objects behind."""

from __future__ import annotations

import os
import subprocess
import sys

# PyVista's per-test leak check reports these against whichever test first loads the entry point.
_LOAD_ENTRY_POINT = """
import pyvista as pv
from refleak.testing import Snapshot
from vtkmodules.vtkCommonCore import vtkObjectBase

snapshot = Snapshot(vtkObjectBase, freeze=True)
pv.registered_plotter_components()
snapshot.assert_no_new('loading the trame-pyvista entry point')
"""


def test_entry_point_import_creates_no_vtk_objects():
    """Load the entry point in a fresh interpreter; conftest already imported it here."""
    result = subprocess.run(
        [sys.executable, '-c', _LOAD_ENTRY_POINT],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
        env={**os.environ, 'PYVISTA_OFF_SCREEN': 'true'},
    )
    assert result.returncode == 0, result.stderr
