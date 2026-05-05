"""Export the current scene as a ``.vtksz`` archive for offline playback.

The companion viewer is hosted at
https://kitware.github.io/vtk-js/examples/OfflineLocalView.html.
"""

from __future__ import annotations

import pyvista as pv
from pyvista import examples
from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3

from trame_pyvista.widgets import PyVistaLocalView

pv.OFF_SCREEN = True

server = get_server(client_type='vue3')
state, ctrl = server.state, server.controller

state.trame__title = 'Export Scene'

mesh = examples.load_random_hills()

pl = pv.Plotter()
pl.add_mesh(mesh)
pl.set_background('lightgrey')


@ctrl.trigger('export')
def export_scene():
    data = ctrl.view_export(format='zip')
    return server.protocol.addAttachment(memoryview(data))


with SinglePageLayout(server) as layout:
    layout.icon.click = ctrl.view_reset_camera
    layout.title.set_text(state.trame__title)

    with layout.toolbar:
        vuetify3.VSpacer()
        vuetify3.VBtn(
            'Export',
            click=(
                "utils.download('scene-export.vtksz', "
                "trigger('export'), 'application/octet-stream')"
            ),
        )

    with (
        layout.content,
        vuetify3.VContainer(fluid=True, classes='pa-0 fill-height'),
        vuetify3.VCol(classes='pa-0 ma-1 fill-height'),
    ):
        view = PyVistaLocalView(pl)
        ctrl.view_export = view.export
        ctrl.view_update = view.update
        ctrl.view_reset_camera = view.reset_camera

server.start()
