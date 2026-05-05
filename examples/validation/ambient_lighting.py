"""Side-by-side local and remote views for visually validating ambient lighting.

Useful when comparing how PyVista lighting parameters round-trip through
``vtk.js`` (local rendering) versus server-side VTK (remote rendering).
"""

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

state.trame__title = 'Ambient Lighting'

mesh = pv.Cone()

pl = pv.Plotter(lighting='none')
actor = pl.add_mesh(
    mesh,
    ambient=0.5,
    specular=0.5,
    specular_power=100,
    color='lightblue',
)
pl.set_background('paraview')
pl.view_isometric()
pl.add_light(pv.Light(position=(0, 1, 0), light_type='scene light'))


@state.change('color')
def set_color(color='lightblue', **kwargs):
    actor.prop.color = color
    ctrl.view_update()


with SinglePageLayout(server) as layout:
    layout.icon.click = ctrl.view_reset_camera
    layout.title.set_text(state.trame__title)

    with layout.toolbar:
        vuetify3.VSpacer()
        vuetify3.VSelect(
            label='Color',
            v_model=('color', 'lightblue'),
            items=('array_list', ['lightblue', '#0000ff', 'white']),
            hide_details=True,
            density='compact',
            variant='outlined',
            classes='pt-1 ml-2',
            style='max-width: 250px',
        )

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
