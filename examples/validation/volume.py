"""Volume rendering through ``PyVistaLocalView`` (smart volume mapper)."""

from __future__ import annotations

import pyvista as pv
from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3

from trame_pyvista.widgets import PyVistaLocalView

pv.OFF_SCREEN = True

server = get_server(client_type='vue3')
state, ctrl = server.state, server.controller

state.trame__title = 'Volume'

vol = pv.Wavelet()

pl = pv.Plotter()
pl.add_volume(vol, mapper='smart')
pl.set_background('lightgrey')


with SinglePageLayout(server) as layout:
    layout.icon.click = ctrl.view_reset_camera
    layout.title.set_text(state.trame__title)

    with layout.toolbar:
        vuetify3.VSpacer()

    with (
        layout.content,
        vuetify3.VContainer(fluid=True, classes='pa-0 fill-height'),
    ):
        view = PyVistaLocalView(pl)
        ctrl.view_update = view.update
        ctrl.view_reset_camera = view.reset_camera

    layout.footer.hide()

server.start()
