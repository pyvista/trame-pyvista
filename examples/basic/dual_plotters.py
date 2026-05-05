"""Two synchronized plotters: drive a slice in one with a plane widget in the other."""

from __future__ import annotations

import pyvista as pv
from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3

from trame_pyvista.widgets import PyVistaRemoteView

pv.OFF_SCREEN = True

server = get_server(client_type='vue3')
state, ctrl = server.state, server.controller

state.trame__title = 'Dual Plotters'

mesh = pv.Wavelet()

pl1 = pv.Plotter()
pl1.add_mesh(mesh.contour())
pl1.view_isometric()

pl2 = pv.Plotter()
pl2.add_mesh(mesh.outline(), color='black')
pl2.view_isometric()


def slice_callback(normal, origin):
    pl2.add_mesh(mesh.slice(normal, origin), name='slice')
    pl2.add_timer_event(max_steps=1, duration=1000, callback=ctrl.view2_update)


pl1.add_plane_widget(slice_callback)


with SinglePageLayout(server) as layout:
    layout.title.set_text(state.trame__title)

    with (
        layout.content,
        vuetify3.VContainer(fluid=True, classes='pa-0 fill-height'),
    ):
        with vuetify3.VCol(classes='pa-0 fill-height'):
            view1 = PyVistaRemoteView(pl1)
            ctrl.view1_update = view1.update
        with vuetify3.VCol(classes='pa-0 fill-height'):
            view2 = PyVistaRemoteView(pl2)
            ctrl.view2_update = view2.update

server.start()
