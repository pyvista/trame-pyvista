"""Vue 3 toolbar widgets and shared state to control a PyVista plotter."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
import weakref

import pyvista as pv
from trame.app import dataclass
from trame.widgets import dataclass as dc
from trame.widgets import html
from trame.widgets import vuetify3 as v3

from trame_pyvista.widgets import _BaseView

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trame_server.core import Server
    from vtkmodules.vtkInteractionWidgets import vtkAbstractWidget

IS_WASM_SUPPORTED = pv.vtk_version_info >= (9, 7, 0)
HAS_WASM_SCREENSHOT = pv.vtk_version_info >= (9, 8, 0) or pv.vtk_version_info >= (9, 7, 20260913)

PLOTTER_TO_STATE_ID_BY_SERVER: dict[str, dict[str, str]] = {}

__all__ = [
    'PlotterState',
    'PyVistaPlotterControls',
    'get_plotter_state',
]


def get_plotter_state(plotter: pv.Plotter, server: Server) -> PlotterState:
    """Return the state instance bound to a plotter, creating it if needed.

    Parameters
    ----------
    plotter : pyvista.Plotter
        The PyVista Plotter the state reflects.

    server : trame_server.core.Server
        Trame server holding the state.

    Returns
    -------
    PlotterState
        The shared state for that plotter on that server.

    """
    server_map = PLOTTER_TO_STATE_ID_BY_SERVER.setdefault(server.name, {})
    state_instance = dataclass.get_instance(server_map.get(plotter._id_name))
    if state_instance is None:
        state_instance = PlotterState(server, plotter=plotter)
        server_map[plotter._id_name] = state_instance._id
        state_instance.update_from_plotter()

    return state_instance


class PlotterState(dataclass.StateDataModel):
    """Synchronized state reflecting and driving the options of a PyVista plotter.

    Parameters
    ----------
    *args
        Arguments forwarded to ``trame.app.dataclass.StateDataModel``.

    plotter : pyvista.Plotter
        The PyVista Plotter to control.

    **kwargs
        Keyword arguments forwarded to ``trame.app.dataclass.StateDataModel``.

    """

    view = dataclass.ServerOnly(_BaseView, None, type_checking=dataclass.TypeValidation.SKIP)
    skip_render = dataclass.ServerOnly(bool, False)
    need_register_widgets = dataclass.ServerOnly(bool, False)
    # ---
    expanded = dataclass.Sync(bool, True)
    show_edges = dataclass.Sync(bool, False)
    show_bounding_box = dataclass.Sync(bool, False)
    show_axis_grid = dataclass.Sync(bool, False)
    show_orientation_axis = dataclass.Sync(bool, False)
    use_parallel_projection = dataclass.Sync(bool, False)
    # ---
    view_type = dataclass.Sync(str, '')
    is_remote = dataclass.Sync(bool, False)
    # ---
    can_screenshot = dataclass.Sync(bool, True)
    can_download_data = dataclass.Sync(bool, True)
    can_download_html = dataclass.Sync(bool, True)

    def __init__(self, *args: Any, plotter: pv.Plotter, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._plotter = weakref.ref(plotter)

    @property
    def plotter(self) -> pv.Plotter | None:
        """Return the plotter if still available or None."""
        return self._plotter()

    def update_from_plotter(self) -> None:
        """Initialize the state from the current plotter configuration."""
        if self.plotter is None:
            return

        iren = self.plotter.iren
        if iren is not None and hasattr(iren.interactor, 'SetTrackInteractorObserverInstances'):
            self.need_register_widgets = False
            iren.interactor.SetTrackInteractorObserverInstances(1)
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

        self.skip_render = False

    def render(self) -> None:
        """Update the attached view unless rendering is suspended."""
        if self.skip_render:
            return

        if self.view:
            self.view.render()

    def reset_camera(self) -> None:
        """Reset the camera of the attached view unless rendering is suspended."""
        if self.skip_render:
            return

        if self.view:
            self.view.reset_camera()

    def register_widgets(self, widgets: Sequence[vtkAbstractWidget]) -> None:
        """Register VTK widgets with the attached view when supported."""
        if self.view:
            self.view._set_widgets(widgets)

    @dataclass.watch('show_orientation_axis', sync=True)
    def _update_orientation_axis(self, show_orientation_axis: bool) -> None:
        """Show or hide the orientation axes on every renderer."""
        if self.plotter is None:
            return

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
    def _update_bounding_box(self, show_bounding_box: bool) -> None:
        """Show or hide the bounding box on every renderer."""
        if self.plotter is None:
            return

        for renderer in self.plotter.renderers:
            if show_bounding_box:
                renderer.add_bounding_box(reset_camera=False)
            else:
                renderer.remove_bounding_box()

        self.render()

    @dataclass.watch('show_edges', sync=True)
    def _update_edge_visibility(self, show_edges: bool) -> None:
        """Show or hide mesh edges on every actor."""
        if self.plotter is None:
            return

        for renderer in self.plotter.renderers:
            for actor in renderer.actors.values():
                if isinstance(actor, pv.Actor):
                    actor.prop.show_edges = show_edges

        self.render()

    @dataclass.watch('use_parallel_projection', sync=True)
    def _update_parallel_projection(self, use_parallel_projection: bool) -> None:
        """Toggle parallel projection on every renderer."""
        if self.plotter is None:
            return

        for renderer in self.plotter.renderers:
            if use_parallel_projection:
                renderer.enable_parallel_projection()
            else:
                renderer.disable_parallel_projection()

        self.render()

    @dataclass.watch('show_axis_grid', sync=True)
    def _update_axis_grid(self, show_axis_grid: bool) -> None:
        """Show or hide the axis grid (ruler) on every renderer."""
        if self.plotter is None:
            return

        for renderer in self.plotter.renderers:
            if show_axis_grid:
                renderer.show_grid()
            else:
                renderer.remove_bounds_axes()

        if self.need_register_widgets:
            self.register_widgets([])  # TODO

        self.render()


def btn(**kwargs: Any) -> None:
    """Create a compact toolbar button."""
    v3.VBtn(
        density='compact',
        variant='flat',
        classes='rounded',
        **kwargs,
    )


class PyVistaPlotterControls(dc.Provider):
    """Toolbar to control camera, display options and exports of a plotter view.

    Parameters
    ----------
    view : SimpleViewer or pyvista view widget
        View exposing the plotter and the camera/export methods to drive.

    style : str, optional
        CSS style of the toolbar card.

    classes : str, optional
        CSS classes of the toolbar card.

    variant : str, default: 'plain'
        Vuetify variant of the toolbar card.

    **kwargs : dict, optional
        Any additional keyword arguments to pass to ``VCard``.

    """

    def __init__(
        self,
        view: _BaseView,
        *,
        style: str = 'position:absolute;top:1rem;left:1rem;z-index:10;',
        classes: str = 'd-flex flex-row pa-1 border-thin bg-white',
        variant: str = 'plain',
        **kwargs: Any,
    ) -> None:
        super().__init__(name='plotter')
        self._view = view
        self._state = get_plotter_state(view._plotter(), self.server)
        self._state.view = view
        self.instance = self._state._id

        with self, v3.VCard(classes=classes, style=style, variant=variant, **kwargs):
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
                    # icon='mdi-camera-switch', # original icon
                    icon=("plotter.use_parallel_projection ? 'mdi-cylinder' : 'mdi-cone'",),
                    active=('plotter.use_parallel_projection',),
                    v_tooltip_bottom=(
                        '`Toggle parallel projection '
                        "(${ plotter.use_parallel_projection ? 'on' : 'off' })`"
                    ),
                )
                btn(
                    click='plotter.show_edges = !plotter.show_edges',
                    icon=("`mdi-grid${plotter.show_edges ? '' : '-off'}`",),
                    active=('plotter.show_edges',),
                    v_tooltip_bottom=(
                        "`Toggle edge visibility (${ plotter.show_edges ? 'on' : 'off' })`"
                    ),
                )
                btn(
                    click='plotter.show_bounding_box = !plotter.show_bounding_box',
                    icon=("`mdi-cube${plotter.show_bounding_box ? '' : '-off'}-outline`",),
                    active=('plotter.show_bounding_box',),
                    v_tooltip_bottom=(
                        "`Toggle bounding box (${ plotter.show_bounding_box ? 'on' : 'off' })`"
                    ),
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
                    v_tooltip_bottom=(
                        "`Toggle axis (${ plotter.show_orientation_axis ? 'on' : 'off' })`"
                    ),
                )
                v3.VDivider(vertical=True)

                # Local screenshot download
                if HAS_WASM_SCREENSHOT:
                    btn(
                        v_if='plotter.can_screenshot && !plotter.is_remote',
                        click=self.download_screenshot,
                        icon='mdi-file-image-outline',
                        v_tooltip_bottom="'Save screenshot'",
                    )
                # Remote screenshot + local download
                btn(
                    v_if='plotter.can_screenshot && plotter.is_remote',
                    click=(
                        "utils.download('pyvista-screenshot.png', "
                        f"trigger('{self.server.trigger_name(self.download_screenshot)}'), "
                        "'application/octet-stream')"
                    ),
                    icon='mdi-file-image-outline',
                    v_tooltip_bottom="'Save screenshot'",
                )
                if IS_WASM_SUPPORTED:
                    btn(
                        v_if='plotter.can_download_data',
                        click=(
                            "utils.download('pyvista-scene.wazex', "
                            f"trigger('{self.server.trigger_name(self.download_scene)}'), "
                            "'application/octet-stream')"
                        ),
                        icon='mdi-database-arrow-down-outline',
                        v_tooltip_bottom="'Save scene as data file'",
                    )
                    btn(
                        v_if='plotter.can_download_html',
                        click=(
                            "utils.download('pyvista-viewer.html', "
                            f"trigger('{self.server.trigger_name(self.download_view3d)}'), "
                            "'application/octet-stream')"
                        ),
                        icon='mdi-cloud-download-outline',
                        v_tooltip_bottom="'Save scene as HTML'",
                    )

    @property
    def view(self) -> _BaseView:
        """Return the controlled view."""
        return self._view

    @property
    def plotter(self) -> pv.Plotter | None:
        """Return the plotter if still available or None."""
        return self._state.plotter

    def download_screenshot(self) -> Any:
        """Capture a PNG screenshot of the view."""
        return self.view._export_screenshot('pyvista-screenshot.png')

    def download_view3d(self) -> Any:
        """Export the scene as a standalone HTML file."""
        return self.view._export_html()

    def download_scene(self) -> Any:
        """Export the scene as a data file."""
        return self.view._export_data()

    def reset_camera(self) -> None:
        """Reset the camera of the view."""
        self.view.reset_camera()

    def view_isometric(self) -> None:
        """View the scene from an isometric perspective."""
        if self.plotter is None:
            return

        self.plotter.renderer.view_isometric(render=False)
        self.view._update_camera()

    def view_yz(self) -> None:
        """View YZ plane."""
        if self.plotter is None:
            return

        self.plotter.renderer.view_yz(render=False)
        self.view._update_camera()

    def view_xz(self) -> None:
        """View XZ plane."""
        if self.plotter is None:
            return

        self.plotter.renderer.view_xz(render=False)
        self.view._update_camera()

    def view_xy(self) -> None:
        """View XY plane."""
        if self.plotter is None:
            return

        self.plotter.renderer.view_xy(render=False)
        self.view._update_camera()
