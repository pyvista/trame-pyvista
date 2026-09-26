"""Ready-to-use trame applications for displaying a PyVista plotter."""

from __future__ import annotations

import weakref

from trame.app import TrameApp
from trame.ui.vuetify3 import VAppLayout
from trame.widgets import html
from trame.widgets import vuetify3 as v3

from trame_pyvista import module
from trame_pyvista import vue3_widgets
from trame_pyvista import widgets

IS_WASM_SUPPORTED = widgets.IS_WASM_SUPPORTED
INVALID_APPLICATION_MESSAGE = """

PyVista currently only provides a single viewer named "default".

When requesting an application, please make sure the requested application name ({app_name})
is valid against the actual set of applications.

"""


class InvalidApplicationNameError(ValueError):
    """Exception when asking for a non existing PyVista viewer application."""

    def __init__(self, app_name):
        """Call the base class constructor with the custom message."""
        super().__init__(INVALID_APPLICATION_MESSAGE.format(app_name=app_name))


def create_application(name, server, plotter):
    """Create a registered PyVista viewer application.

    Parameters
    ----------
    name : str or None
        Name of the application to create. ``None`` resolves to ``'default'``.

    server : trame_server.core.Server
        Trame server to bind the application to.

    plotter : pyvista.Plotter
        The PyVista Plotter to display.

    Returns
    -------
    trame.app.TrameApp
        The created application.

    Raises
    ------
    InvalidApplicationNameError
        If ``name`` does not match any registered application.

    """
    if name is None:
        name = 'default'

    app = APPS.get(name)
    if app:
        return app(plotter, server)

    raise InvalidApplicationNameError(name)


class SimpleViewer(TrameApp, widgets._BaseView):
    """Viewer that can toggle between local (VTK.wasm) and remote rendering.

    Parameters
    ----------
    plotter : pyvista.Plotter
        The PyVista Plotter to display.

    server : trame_server.core.Server, optional
        Trame server to use. A default one is used when not provided.

    mode : str, default: 'local'
        Initial rendering mode, either ``'local'`` or ``'remote'``.

    """

    def __init__(self, plotter, server=None, mode='local'):
        widgets._BaseView.__init__(self, plotter)
        TrameApp.__init__(self, server)
        self.server.enable_module(module)
        self._plotter = weakref.ref(plotter)
        self.view_wasm = None  # needs vtk>=9.7

        # Add warning since some capabilities are now hidden
        if not IS_WASM_SUPPORTED:
            import warnings

            warnings.warn(widgets.UPDATE_VTK_FOR_WASM, stacklevel=2)

        # Define UI
        with VAppLayout(self.server, full_height=True, height='100%') as self.ui:
            self.ui.iframe_attrs['class'] = 'trame-iframe'

            with html.Div(classes='pyvista-client-server'):
                with html.Transition(name='fade'):
                    # Local rendering component
                    if IS_WASM_SUPPORTED:
                        self.view_wasm = widgets.PyVistaWasmView(
                            self.plotter, v_if="pyvista_rendering_mode == 'local'"
                        )

                    # Remote rendering component
                    self.view_rca = widgets.PyVistaRCAView(
                        self.plotter, v_if="pyvista_rendering_mode == 'remote'"
                    )

                # Toggle for remote/local rendering
                if IS_WASM_SUPPORTED:
                    v3.VSwitch(
                        model_value=('pyvista_rendering_mode', mode),
                        hide_details=True,
                        inset=True,
                        true_value='remote',
                        false_value='local',
                        false_icon='mdi-laptop',
                        true_icon='mdi-cloud-outline',
                        classes='toggle',
                        update_modelValue=self._toggle_rendering_mode,
                        v_tooltip_left=(
                            "pyvista_rendering_mode === 'remote' "
                            "? 'Server side rendering' : 'Client side rendering'"
                        ),
                    )

            # Plotter toolbar
            self.controls = vue3_widgets.PyVistaPlotterControls(self)

        # Fallback to remote if WASM is not an option
        if not IS_WASM_SUPPORTED:
            self.use_remote_rendering()

    def _toggle_rendering_mode(self):
        """Switch between local and remote rendering."""
        if self.state.pyvista_rendering_mode == 'remote':
            self.use_local_rendering()
        else:
            self.use_remote_rendering()

    def use_remote_rendering(self):
        """Switch to server side rendering."""
        self.controls._state.is_remote = True
        self.state.pyvista_rendering_mode = 'remote'

    def use_local_rendering(self):
        """Switch to client side rendering after syncing the scene."""
        if not IS_WASM_SUPPORTED:
            return

        self.controls._state.is_remote = False
        self.view_wasm.update(push_camera=True)
        self.state.pyvista_rendering_mode = 'local'

    @property
    def active_view(self):
        """Return the view matching the current rendering mode."""
        if not IS_WASM_SUPPORTED:
            return self.view_rca

        if self.state.pyvista_rendering_mode == 'remote':
            return self.view_rca

        return self.view_wasm

    def render(self):
        """Refresh the web view."""
        self.active_view.render()

    def reset_camera(self):
        """Reset the camera of the active view.

        Part of the view API used by ``PyVistaPlotterControls``.
        """
        self.active_view.reset_camera()

    def _set_widgets(self, widgets=None):
        """Register VTK widgets with the local view.

        Part of the view API used by ``PyVistaPlotterControls``.
        """
        if IS_WASM_SUPPORTED:
            self.view_wasm._set_widgets(widgets)

    def _update_camera(self):
        """Push the plotter camera to the active view.

        Part of the view API used by ``PyVistaPlotterControls``.
        """
        self.active_view._update_camera()

    def _export_screenshot(self, filename):
        """Capture a screenshot of the active view.

        Part of the view API used by ``PyVistaPlotterControls``.
        """
        return self.active_view._export_screenshot(filename)


APPS = {
    'default': SimpleViewer,
}
