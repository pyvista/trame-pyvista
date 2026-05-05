"""Animate a modal mode shape on a pump bracket dataset.

The slider scrubs through phase frames; the play toggle drives the same
update loop asynchronously. The ``cmap`` selector swaps the lookup table.
"""

from __future__ import annotations

import asyncio

import matplotlib.pyplot as plt
import numpy as np
import pyvista as pv
from pyvista import examples
from trame.app import asynchronous
from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3

from trame_pyvista.ui import plotter_ui

pv.OFF_SCREEN = True

server = get_server(client_type='vue3')
state, ctrl = server.state, server.controller

state.trame__title = 'Pump Bracket'

dataset = examples.download_pump_bracket()

cpos = [
    (0.744, -0.502, -0.830),
    (0.0520, -0.160, 0.0743),
    (-0.180, -0.958, 0.224),
]

n_frames = 32
phases = np.linspace(0, 2 * np.pi, n_frames, endpoint=False)
mode_shape = 'disp_6'

pl = pv.Plotter()
pl.enable_anti_aliasing('fxaa')
pl.add_mesh(dataset, color='white', opacity=0.5)

warped = dataset.copy()
actor = pl.add_mesh(warped, show_scalar_bar=False, ambient=0.2)
pl.camera_position = cpos


@state.change('cmap')
def update_cmap(cmap='viridis', **kwargs):
    actor.mapper.lookup_table.cmap = cmap
    ctrl.view_update()


@state.change('phase_index')
def update_phase(phase_index=0, **kwargs):
    phase = phases[phase_index]
    warped.points = dataset.points + dataset[mode_shape] * np.cos(phase) * 0.05
    ctrl.view_update()


@state.change('play')
@asynchronous.task
async def update_play(**kwargs):
    while state.play:
        with state:
            state.phase_index = (state.phase_index + 1) % len(phases)
            update_phase(state.phase_index)
        await asyncio.sleep(1 / 30)


with SinglePageLayout(server) as layout:
    layout.icon.click = ctrl.view_reset_camera
    layout.title.set_text(state.trame__title)

    with layout.toolbar:
        vuetify3.VSpacer()
        vuetify3.VSelect(
            label='Color map',
            v_model=('cmap', 'viridis'),
            items=('array_list', plt.colormaps()),
            hide_details=True,
            density='compact',
            variant='outlined',
            classes='pt-1 ml-2',
            style='max-width: 250px',
        )
        vuetify3.VSlider(
            v_model=('phase_index', 0),
            min=0,
            max=len(phases) - 1,
            hide_details=True,
            density='compact',
            style='max-width: 200px',
        )
        vuetify3.VCheckbox(
            v_model=('play', False),
            false_icon='mdi-play',
            true_icon='mdi-stop',
            hide_details=True,
            density='compact',
            classes='mx-2',
        )

    with layout.content:
        view = plotter_ui(pl)
        ctrl.view_update = view.update
        ctrl.view_reset_camera = view.reset_camera

    layout.footer.hide()

server.start()
