"""Minimal trame app driving a PyVista plotter."""

from __future__ import annotations

import pyvista as pv
from pyvista import examples

from trame_pyvista.apps import SimpleViewer

pv.OFF_SCREEN = True

mesh = examples.load_random_hills()

pl = pv.Plotter()
pl.add_mesh(mesh)

# Create viewer application and start it
app = SimpleViewer(pl, theme='light')  # theme can be set to 'light' or 'dark'
app.server.start()
