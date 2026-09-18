"""How to use PyVista UI template.

This example demonstrates how to use ``plotter_ui`` to add a PyVista
``Plotter`` to a UI with scene controls and standard UI features.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pyvista as pv
from pyvista import examples

from trame.app import TrameApp
from trame.ui.vuetify3 import VAppLayout
from trame.widgets import vuetify3 as v3
from trame.decorators import change

from trame_pyvista.ui import plotter_ui

pv.OFF_SCREEN = True


class Viewer(TrameApp):
    def __init__(self, server=None):
        super().__init__(server)

        # VTK/PyVista
        mesh = examples.load_random_hills()
        self.pl = pv.Plotter()
        self.actor = self.pl.add_mesh(mesh, cmap='viridis')

        # UI
        self.state.trame__title = 'PyVista UI Template'
        with VAppLayout(self.server) as self.ui:
            self.ctrl.view_update = plotter_ui(self.pl).update

            v3.VSelect(
                label='Color map',
                v_model=('cmap', 'viridis'),
                items=('array_list', plt.colormaps()),
                density='compact',
                variant='outlined',
                style='position:absolute;top:1rem;right:1rem;width: 250px;',
            )

    @change('cmap')
    def update_cmap(self, cmap='viridis', **_):
        self.actor.mapper.lookup_table.cmap = cmap
        self.ctrl.view_update()


def main():
    app = Viewer()
    app.server.start()


if __name__ == '__main__':
    main()
