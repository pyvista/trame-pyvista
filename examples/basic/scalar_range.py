"""Drive a mapper's scalar range from a ``VRangeSlider`` in the toolbar.

Uses a synthetic opacity transfer function over the cell index so the
widget produces a visible change without bundling a 900-line opacity table.
"""

from __future__ import annotations

import numpy as np
import pyvista as pv
from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3

from trame_pyvista.ui import plotter_ui

pv.OFF_SCREEN = True

server = get_server(client_type='vue3')
state, ctrl = server.state, server.controller

state.trame__title = 'Scalar Range'
ctrl.on_server_ready.add(ctrl.view_update)


mesh = pv.Wavelet()
mesh['foo'] = np.arange(mesh.n_cells)

# Sparse opacity ramp: mostly transparent, with a high-density tail.
opacity = np.zeros(mesh.n_cells)
opacity[mesh.n_cells // 2 :] = np.linspace(0.0, 1.0, mesh.n_cells - mesh.n_cells // 2)

pl = pv.Plotter()
actor = pl.add_mesh(mesh, scalars='foo', opacity=opacity, use_transparency=True)


@state.change('scalar_range')
def set_scalar_range(scalar_range=None, **kwargs):
    if scalar_range is None:
        scalar_range = mesh.get_data_range('foo')
    actor.mapper.scalar_range = scalar_range
    ctrl.view_update()


with SinglePageLayout(server) as layout:
    layout.title.set_text(state.trame__title)
    layout.icon.click = ctrl.view_reset_camera

    with layout.toolbar:
        vuetify3.VSpacer()
        vuetify3.VRangeSlider(
            thumb_size=16,
            thumb_label=True,
            label='Range',
            v_model=('scalar_range', [0, mesh.n_cells]),
            min=0,
            max=mesh.n_cells,
            density='compact',
            hide_details=True,
            style='max-width: 400px',
        )

    with (
        layout.content,
        vuetify3.VContainer(fluid=True, classes='pa-0 fill-height'),
    ):
        view = plotter_ui(pl, default_server_rendering=True)
        ctrl.view_update = view.update

server.start()
