"""Side-by-side local and remote views for validating PyVista's ``light kit``."""

from __future__ import annotations

import pyvista as pv
from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3

from trame_pyvista.widgets import PyVistaLocalView
from trame_pyvista.widgets import PyVistaRemoteView

pv.OFF_SCREEN = True

server = get_server(client_type='vue3')
state, ctrl = server.state, server.controller

state.trame__title = 'Lighting'

mesh = pv.Cone()

pl = pv.Plotter(lighting='light kit')
pl.add_mesh(mesh, color='white')
pl.set_background('paraview')
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
        with vuetify3.VContainer(fluid=True, classes='pa-0 fill-height', style='width: 50%;'):
            local = PyVistaLocalView(pl)
        with vuetify3.VContainer(fluid=True, classes='pa-0 fill-height', style='width: 50%;'):
            remote = PyVistaRemoteView(pl)

    def view_update(**kwargs):
        local.update(**kwargs)
        remote.update(**kwargs)

    def view_reset_camera(**kwargs):
        local.reset_camera(**kwargs)
        remote.reset_camera(**kwargs)

    ctrl.view_update = view_update
    ctrl.view_reset_camera = view_reset_camera
    ctrl.on_server_ready.add(view_update)

    layout.footer.hide()

server.start()
