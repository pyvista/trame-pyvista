"""Validate ``interactive_ratio`` and ``still_ratio`` on a remote view.

Increasing both ratios trades performance for higher-resolution server
renderings during and after interaction.
"""

from __future__ import annotations

import pyvista as pv
from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3

from trame_pyvista.widgets import PyVistaRemoteView

pv.OFF_SCREEN = True

server = get_server(client_type='vue3')
state, ctrl = server.state, server.controller

state.trame__title = 'Remote View Ratios'

mesh = pv.Wavelet()

pl = pv.Plotter()
pl.add_mesh(mesh)
pl.set_background('lightgrey')
pl.show_grid()
pl.view_isometric()


with SinglePageLayout(server) as layout:
    layout.icon.click = ctrl.view_reset_camera
    layout.title.set_text(state.trame__title)

    with layout.toolbar:
        vuetify3.VSpacer()

    with (
        layout.content,
        vuetify3.VContainer(fluid=True, classes='pa-0 fill-height'),
    ):
        view = PyVistaRemoteView(pl, interactive_ratio=2, still_ratio=2)
        ctrl.view_update = view.update
        ctrl.view_reset_camera = view.reset_camera

server.start()
