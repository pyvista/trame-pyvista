import pyvista as pv
from trame.widgets import vuetify3 as v3, dataclass as dc, html
from trame.app import dataclass

PLOTTER_TO_STATE_ID_BY_SERVER = {}


def get_plotter_state(plotter, server):
    server_map = PLOTTER_TO_STATE_ID_BY_SERVER.setdefault(server.name, {})
    state_instance = dataclass.get_instance(server_map.get(plotter._id_name))
    if state_instance is None:
        state_instance = PlotterState(server, plotter=plotter)
        server_map[plotter._id_name] = state_instance._id
        state_instance.update_from_plotter()

    return state_instance


class PlotterState(dataclass.StateDataModel):
    plotter = dataclass.ServerOnly(None, None, type_checking=dataclass.TypeValidation.SKIP)
    view = dataclass.ServerOnly(None, None, type_checking=dataclass.TypeValidation.SKIP)
    skip_render = dataclass.ServerOnly(bool, False)
    need_register_widgets = dataclass.ServerOnly(bool, False)
    # ---
    expanded = dataclass.Sync(bool, True)
    show_edges = dataclass.Sync(bool, False)
    show_bounding_box = dataclass.Sync(bool, False)
    show_axis_grid = dataclass.Sync(bool, False)
    show_orientation_axis = dataclass.Sync(bool, False)
    use_parallel_projection = dataclass.Sync(bool, False)

    def update_from_plotter(self):
        if hasattr(self.plotter.iren, 'SetTrackInteractorObserverInstances'):
            self.need_register_widgets = False
            self.plotter.iren.SetTrackInteractorObserverInstances(1)
        else:
            self.need_register_widgets = True

        self.skip_render = True

        self.use_parallel_projection = self.plotter.renderer.parallel_projection
        self.show_axis_grid = self.plotter.renderer.cube_axes_actor is not None
        self.show_bounding_box = any(key.startswith('BoundingBox') for key in self.plotter.actors)
        self.show_edges = any(
            isinstance(actor, pv.Actor) and actor.prop.show_edges
            for actor in self.plotter.actors.values()
        )
        self.show_orientation_axis = any(
            ren.axes_widget is not None for ren in self.plotter.renderers
        )

        # remove/add widgets to make sure they are tracked
        if self.show_orientation_axis:
            self._update_orientation_axis(False)
            self._update_orientation_axis(True)

        if self.show_axis_grid:
            self._update_axis_grid(False)
            self._update_axis_grid(True)

        self.skip_render = False

    def render(self):
        if self.skip_render:
            return

        if self.view:
            self.view.update()

    def reset_camera(self):
        if self.skip_render:
            return

        if self.view:
            self.view.reset_camera()

    def register_widgets(self, widgets):
        if self.view and hasattr(self.view, 'set_widgets'):
            self.view.set_widgets(widgets)

    @dataclass.watch('show_orientation_axis', sync=True)
    def _update_orientation_axis(self, show_orientation_axis):
        for renderer in self.plotter.renderers:
            if show_orientation_axis:
                renderer.show_axes()
            else:
                renderer.hide_axes()

        if self.need_register_widgets:
            self.register_widgets(
                [ren.axes_widget for ren in self.plotter.renderers if ren.axes_widget is not None]
            )

        self.render()

    @dataclass.watch('show_bounding_box', sync=True)
    def _update_bounding_box(self, show_bounding_box):
        for renderer in self.plotter.renderers:
            if show_bounding_box:
                renderer.add_bounding_box(reset_camera=False)
            else:
                renderer.remove_bounding_box()

        self.render()

    @dataclass.watch('show_edges', sync=True)
    def _update_edge_visibility(self, show_edges):
        for renderer in self.plotter.renderers:
            for actor in renderer.actors.values():
                if isinstance(actor, pv.Actor):
                    actor.prop.show_edges = show_edges

        self.render()

    @dataclass.watch('use_parallel_projection', sync=True)
    def _update_parallel_projection(self, use_parallel_projection):
        for renderer in self.plotter.renderers:
            if use_parallel_projection:
                renderer.enable_parallel_projection()
            else:
                renderer.disable_parallel_projection()

        self.render()

    @dataclass.watch('show_axis_grid', sync=True)
    def _update_axis_grid(self, show_axis_grid):
        for renderer in self.plotter.renderers:
            if show_axis_grid:
                renderer.show_grid()
            else:
                renderer.remove_bounds_axes()

        if self.need_register_widgets:
            self.register_widgets([])  # TODO

        self.render()


def btn(**kwargs):
    v3.VBtn(
        density='compact',
        variant='flat',
        classes='rounded',
        **kwargs,
    )


class PyVistaPlotterControls(dc.Provider):
    def __init__(
        self,
        plotter,
        view,
        *,
        style='position:absolute;top:1rem;left:1rem;z-index:10;',
        classes='d-flex flex-row pa-1',
        **kwargs,
    ):
        super().__init__(name='plotter')
        self._view = view
        self._state = get_plotter_state(plotter, self.server)
        self._state.view = view
        self.instance = self._state._id

        with self, v3.VCard(classes=classes, style=style, **kwargs):
            btn(
                icon='mdi-dots-vertical',
                click='plotter.expanded = !plotter.expanded',
                v_tooltip_bottom="'Toggle menu visibility'",
            )
            with html.Div(v_if='plotter.expanded', classes='d-flex flex-row ga-1 px-1'):
                v3.VDivider(vertical=True)
                btn(
                    icon='mdi-arrow-expand-all',
                    click=self.reset_camera,
                    v_tooltip_bottom="'Reset Camera'",
                )

                btn(
                    icon='mdi-axis-arrow',
                    click=self.view_isometric,
                    v_tooltip_bottom="'Perspective view'",
                )
                btn(
                    click=self.view_yz,
                    icon='mdi-axis-x-arrow',
                    v_tooltip_bottom="'Reset Camera X'",
                )
                btn(
                    click=self.view_xz,
                    icon='mdi-axis-y-arrow',
                    v_tooltip_bottom="'Reset Camera Y'",
                )
                btn(
                    click=self.view_xy,
                    icon='mdi-axis-z-arrow',
                    v_tooltip_bottom="'Reset Camera Z'",
                )
                v3.VDivider(vertical=True)
                btn(
                    click='plotter.use_parallel_projection = !plotter.use_parallel_projection',
                    icon='mdi-camera-switch',
                    active=('plotter.use_parallel_projection',),
                    v_tooltip_bottom="`Toggle parallel projection (${ plotter.use_parallel_projection ? 'on' : 'off' })`",
                )
                btn(
                    click='plotter.show_edges = !plotter.show_edges',
                    icon=("`mdi-grid${plotter.show_edges ? '' : '-off'}`",),
                    active=('plotter.show_edges',),
                    v_tooltip_bottom="`Toggle edge visibility (${ plotter.show_edges ? 'on' : 'off' })`",
                )
                btn(
                    click='plotter.show_bounding_box = !plotter.show_bounding_box',
                    icon=("`mdi-cube${plotter.show_bounding_box ? '' : '-off'}-outline`",),
                    active=('plotter.show_bounding_box',),
                    v_tooltip_bottom="`Toggle bounding box (${ plotter.show_bounding_box ? 'on' : 'off' })`",
                )
                btn(
                    click='plotter.show_axis_grid = !plotter.show_axis_grid',
                    icon='mdi-ruler-square',
                    active=('plotter.show_axis_grid',),
                    v_tooltip_bottom="`Toggle ruler (${ plotter.show_axis_grid ? 'on' : 'off' })`",
                )
                btn(
                    click='plotter.show_orientation_axis = !plotter.show_orientation_axis',
                    icon='mdi-axis-arrow-info',
                    active=('plotter.show_orientation_axis',),
                    v_tooltip_bottom="`Toggle axis (${ plotter.show_orientation_axis ? 'on' : 'off' })`",
                )
                v3.VDivider(vertical=True)
                btn(
                    click=self.download_screenshot,
                    icon='mdi-file-image-outline',
                    v_tooltip_bottom="'Save screenshot'",
                )
                if hasattr(self.view, 'export_data'):
                    btn(
                        click=(
                            "utils.download('pyvista-scene.wazex', "
                            f"trigger('{self.server.trigger_name(self.download_scene)}'), "
                            "'application/octet-stream')"
                        ),
                        icon='mdi-database-arrow-down-outline',
                        v_tooltip_bottom="'Save scene as data file'",
                    )
                btn(
                    click=(
                        "utils.download('pyvista-viewer.html', "
                        f"trigger('{self.server.trigger_name(self.download_view3d)}'), "
                        "'application/octet-stream')"
                    ),
                    icon='mdi-cloud-download-outline',
                    v_tooltip_bottom="'Save scene as HTML'",
                )

    @property
    def view(self):
        return self._view

    @property
    def plotter(self):
        return self._state.plotter

    def download_screenshot(self):
        self.view.download_screenshot('pyvista-screenshot.png', 'image/png')

    def download_view3d(self):
        return self.view.export_html()

    def download_scene(self):
        return self.view.export_data()

    def reset_camera(self):
        self.view.reset_camera()

    def view_isometric(self):
        self.plotter.view_isometric(render=False)
        self.view.update_camera()

    def view_yz(self):
        """View YZ plane."""
        self.plotter.view_yz(render=False)
        self.view.update_camera()

    def view_xz(self):
        """View XZ plane."""
        self.plotter.view_xz(render=False)
        self.view.update_camera()

    def view_xy(self):
        """View XY plane."""
        self.plotter.view_xy(render=False)
        self.view.update_camera()
