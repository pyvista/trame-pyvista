"""Minimal trame app driving a PyVista plotter via :func:`plotter_ui`."""

from __future__ import annotations

import pyvista as pv
from pyvista import examples
from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout

from trame_pyvista.ui import plotter_ui

pv.OFF_SCREEN = True

server = get_server(client_type='vue3')
state, ctrl = server.state, server.controller

state.trame__title = 'Simple'

mesh = examples.load_random_hills()

pl = pv.Plotter()
pl.add_mesh(mesh)

with SinglePageLayout(server) as layout, layout.content:
    view = plotter_ui(pl)
    ctrl.view_update = view.update

server.start()
