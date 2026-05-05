"""Validate edge visibility toggling across local and remote views."""

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

state.trame__title = 'Toggle Edges'

mesh = pv.Wavelet()

pl = pv.Plotter()
actor = pl.add_mesh(mesh)
pl.reset_camera()


def toggle_edges():
    actor.prop.show_edges = not actor.prop.show_edges
    ctrl.view_update()


with SinglePageLayout(server) as layout:
    layout.icon.click = ctrl.view_reset_camera
    layout.title.set_text(state.trame__title)

    with layout.toolbar:
        vuetify3.VSpacer()
        vuetify3.VBtn('Toggle edges', click=toggle_edges)

    with (
        layout.content,
        vuetify3.VContainer(fluid=True, classes='pa-0 fill-height'),
    ):
        with vuetify3.VCol(classes='fill-height'):
            local = PyVistaLocalView(pl)
        with vuetify3.VCol(classes='fill-height'):
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
