"""PyVista view rendered in the browser with VTK.wasm through trame-vtklocal."""

from __future__ import annotations

import mimetypes

import pyvista as pv
from trame.widgets import vtklocal

from trame_pyvista import widgets as pv_widgets


class PyVistaWasmView(vtklocal.LocalView, pv_widgets._BaseView):  # type: ignore[misc]
    """PyVista wrapping of trame LocalView for in-browser rendering.

    This will connect to and synchronize with a PyVista plotter to
    perform client-side rendering with VTK.wasm in the browser.

    Parameters
    ----------
    plotter : pyvista.Plotter
        The PyVista Plotter to represent in the output view.

    **kwargs : dict, optional
        Any additional keyword arguments to pass to
        ``trame.widgets.vtklocal.LocalView``.

    """

    def __init__(self, plotter, **kwargs):
        """Create a trame local view from a PyVista Plotter."""
        if not pv_widgets.IS_WASM_SUPPORTED:
            raise pv.VTKVersionError(pv_widgets.UPDATE_VTK_FOR_WASM)

        pv_widgets._BaseView.__init__(self, plotter)

        vtklocal.LocalView.__init__(
            self,
            self.plotter.render_window,  # type: ignore[union-attr]
            end_interaction=(self._sync_camera, '[$event]'),
            **kwargs,
        )

        self._post_initialize()

    def _sync_camera(self, camera_states):
        """Apply client camera states to the server-side VTK objects."""
        for vtk_state in camera_states:
            self.vtk_update_from_state(vtk_state)

    def _post_initialize(self):
        """Register the orientation widgets after the base initialization."""
        super()._post_initialize()
        self._set_widgets(
            [ren.axes_widget for ren in self.plotter.renderers if ren.axes_widget is not None],  # type: ignore[union-attr]
        )

    def _set_widgets(self, widgets=None):
        """Register VTK widgets to mimic the vtk.js local view API."""
        if not widgets:
            widgets = []

        for w in widgets:
            self.register_vtk_object(w)

    def _update_camera(self):
        """Sync scene with camera update."""
        self.update(push_camera=True)

    def render(self):
        """Trigger a view refresh."""
        self.update_throttle()

    def _export_screenshot(self, filename):
        """Make the web client download a screenshot in the format ``filename`` implies."""
        mime, _ = mimetypes.guess_type(filename)
        return self.download_screenshot(filename, mime or 'image/png')

    # -----------------------------------------------------------
    # Legacy API for compatibility - do not use in your code
    # -----------------------------------------------------------

    def update_camera(self, **_):
        """Do not use by hand - kept for legacy viewer."""
        self._update_camera()

    def push_camera(self, **_):
        """Do not use by hand - kept for legacy viewer."""
        self._update_camera()

    def update_image(self, **_):
        """Do not use - kept for legacy viewer."""
        self.render()

    # -----------------------------------------------------------
