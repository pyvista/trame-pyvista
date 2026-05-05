"""Validate camera-sync behaviour between a remote and a local view.

Click "Push camera" to broadcast the local view's camera to the remote
view. "Push position" jumps to a hard-coded camera position before the push.
"""

from __future__ import annotations

import pyvista as pv
from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import html
from trame.widgets import vuetify3

from trame_pyvista.widgets import PyVistaLocalView
from trame_pyvista.widgets import PyVistaRemoteView

pv.OFF_SCREEN = True

server = get_server(client_type='vue3')
state, ctrl = server.state, server.controller

state.trame__title = 'Camera Sync - Many Actors'

pl = pv.Plotter()
for i in range(50):
    for j in range(50):
        pl.add_mesh(pv.Cone(center=(i, j, 0)))
pl.reset_camera()


def push_camera():
    ctrl.view_push_camera()


def push_position():
    pl.camera.position = (28.670, 11.922, -2.988)
    ctrl.view_push_camera()


with SinglePageLayout(server) as layout:
    layout.icon.click = ctrl.view_reset_camera
    layout.title.set_text(state.trame__title)

    with layout.toolbar:
        vuetify3.VSpacer()
        vuetify3.VBtn('Push camera', click=push_camera)
        vuetify3.VBtn('Push position', click=push_position)

    with (
        layout.content,
        vuetify3.VContainer(
            fluid=True,
            classes='pa-0 fill-height',
            style='display: grid; grid-template-columns: 1fr 1fr;',
        ),
    ):
        with html.Div(style='height: 100%;'):
            remote = PyVistaRemoteView(pl)
            ctrl.view_update = remote.update
            ctrl.view_reset_camera = remote.reset_camera

        with html.Div(style='height: 100%;'):
            local = PyVistaLocalView(pl)
            ctrl.view_push_camera = local.push_camera

server.start()
