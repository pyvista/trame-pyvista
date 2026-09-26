from __future__ import annotations

import pyvista as pv
from pyvista import examples
from trame.app import TrameApp
from trame.decorators import change
from trame.ui.vuetify3 import VAppLayout
from trame.widgets import pyvista as pvw
from trame.widgets import vuetify3 as v3
from vtkmodules.vtkFiltersCore import vtkContourFilter

pv.OFF_SCREEN = True


class ContourViewer(TrameApp):
    def __init__(self, server=None):
        super().__init__(server)
        self.server.cli.add_argument(
            '--mode', choices=['trame', 'client', 'server', 'wasm'], default='server'
        )
        args, _ = self.server.cli.parse_known_args()
        self.mode = args.mode

        # PyVista viz setup
        volume = examples.download_head_2()
        data_range = tuple(volume.get_data_range())

        contour = vtkContourFilter(number_of_contours=1)
        contour.SetInputDataObject(volume)

        # Update trame state
        self.state.data_range = (float(data_range[0]), float(data_range[1]))
        self.state.contour_value = 0.5 * (data_range[0] + data_range[1])

        pl = pv.Plotter()
        pl.add_mesh(contour, cmap='viridis', clim=data_range)

        pl.camera.position = (-404.79988296140607, 472.3909763602064, 91.97414214495656)
        pl.camera.focal_point = (126.68265914916992, 123.96118450164795, 92.5)
        pl.camera.up = (0.20815009687634312, -0.178056364727541, -0.9617533301997878)
        pl.reset_camera(bounds=volume.bounds)

        # Keep some ref around
        self.contour = contour
        self.pl = pl

        # Build trame UI
        self._build_ui()

    @change('contour_value')
    def _on_contour(self, contour_value, **_):
        self.contour.SetValue(0, contour_value)

        if self.mode == 'server':
            # Animation won't detect change unless render_window mtime is new
            self.pl.render_window.Modified()
        elif self.mode == 'trame':
            self.ctx.view.update_image()
        elif self.mode == 'wasm':
            self.ctx.view.render()

    def start_animation(self):
        if self.mode == 'server':
            self.ctx.view.start_animation(fps=20, quality=80, ratio=1)

    def stop_animation(self):
        if self.mode == 'server':
            self.ctx.view.stop_animation()
        else:
            self.ctx.view.update()

    def _build_ui(self):
        self.state.trame__title = 'Contour'
        with VAppLayout(self.server) as self.ui:
            with v3.VMain():
                if self.mode == 'server':
                    pvw.PyVistaRemoteView(self.pl, ctx_name='view')
                elif self.mode == 'client':
                    pvw.PyVistaLocalView(self.pl, ctx_name='view')
                elif self.mode == 'trame':
                    pvw.PyVistaRemoteLocalView(self.pl, ctx_name='view')
                elif self.mode == 'wasm':
                    pvw.PyVistaWasmView(self.pl, ctx_name='view', config=["{mode: 'wasm64'}"])
                else:
                    pvw.PyVistaRemoteView(self.pl, ctx_name='view')
            with v3.VFooter(app=True):
                v3.VProgressLinear(
                    indeterminate=True,
                    absolute=True,
                    bottom=True,
                    active=('trame__busy',),
                )
                v3.VSlider(
                    v_model='contour_value',
                    min=('data_range[0]',),
                    max=('data_range[1]',),
                    step=('(data_range[1] - data_range[0]) / 255',),
                    hide_details=True,
                    density='compact',
                    start=self.start_animation,
                    end=self.stop_animation,
                )
                v3.VBtn(
                    icon='mdi-crop-free',
                    click=self.ctx.view.reset_camera,
                    classes='rounded',
                    flat=True,
                )


def main():
    app = ContourViewer()
    app.server.start()


if __name__ == '__main__':
    main()
