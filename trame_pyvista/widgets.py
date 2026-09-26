"""Trame view interface for PyVista."""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
import io
from pathlib import Path
import sys
import tempfile
import weakref

import pyvista as pv
from trame.app import get_server as trame_get_server
from trame.widgets import rca
from trame.widgets import vtklocal
from trame.widgets.vtk import VtkLocalView
from trame.widgets.vtk import VtkRemoteLocalView
from trame.widgets.vtk import VtkRemoteView
from trame_vtk.tools.vtksz2html import write_html

if sys.version_info >= (3, 12):
    from typing import override
else:

    def override(func):  # noqa: D103
        return func


IS_WASM_SUPPORTED = pv.vtk_version_info >= (9, 7, 0)

UPDATE_VTK_FOR_WASM = (
    '\n\n  The current version of vtk '
    f'{".".join(str(v) for v in pv.vtk_version_info)} is too old\n'
    '  to properly support PyVistaWasmView and new apps.\n'
    '  Please update to a VTK >= 9.7 by either running `pip install "vtk>=9.7"` or\n'
    '  `pip install "vtk==9.7.20260913.dev0" --index-url https://wheels.vtk.org`\n'
    '  for grabbing a nightly version.\n'
)

CLOSED_PLOTTER_ERROR = (
    'The render window for this plotter has been destroyed. '
    'Do not call `show()` for the plotter before passing to trame.'
)

MISSING_WASM = (
    'The widget PyVistaWasmLocalView can only be used if trame-vtklocal is installed. '
    'To install trame-vtklocal you should run "pip install trame-pyvista[wasm]". '
    'WASM needs VTK >= 9.7.'
)

MISSING_RCA = (
    'The widget PyVistaRCAView can only be used if trame-rca is installed. '
    'To install trame-rca you should run "pip install trame-pyvista[rca]".'
)


def get_server(*args, **kwargs):  # numpydoc ignore=RT01
    """Override trame's get_server.

    Parameters
    ----------
    *args :
        Any extra args are passed as option to the server instance.

    **kwargs :
        Any extra keyword args are passed as option to the server instance.

    Returns
    -------
    trame_server.core.Server
        Trame server.

    """
    server = trame_get_server(*args, **kwargs)
    if 'client_type' in kwargs:
        server.client_type = kwargs['client_type']
    return server


class _BasePyVistaView:
    """Shared behavior of the PyVista trame views."""

    def __init__(self, plotter):
        """Initialize the base PyVista view."""
        self._plotter = weakref.ref(plotter)
        self.pyvista_initialize()
        self._plotter_render_callback = lambda *_: self.update()  # type: ignore[attr-defined]

    @property
    def plotter(self):
        """Return the plotter if still available or None."""
        return self._plotter()

    def pyvista_initialize(self):
        """Validate the plotter and set default camera positions when unset."""
        if self.plotter.render_window is None:  # type: ignore[union-attr]
            raise RuntimeError(CLOSED_PLOTTER_ERROR)
        for renderer in self.plotter.renderers:  # type: ignore[union-attr]
            if not renderer.camera.is_set:
                renderer.camera_position = renderer.get_default_cam_pos()
                renderer.ResetCamera()

    def _post_initialize(self):
        """Schedule the first update and keep the view in sync with plotter renders."""
        if self._server.running:  # type: ignore[attr-defined]
            self.update()  # type: ignore[attr-defined]
        else:
            self._server.controller.on_server_ready.add(self.update)  # type: ignore[attr-defined]

        # Callback to sync view on PyVista's render call when renders are suppressed
        self.plotter.add_on_render_callback(self._plotter_render_callback, render_event=False)  # type: ignore[union-attr]

    def update_camera(self):
        """Update camera or push the image."""
        self.push_camera()  # type: ignore[attr-defined]
        self.update_image()  # type: ignore[attr-defined]

    def export_html(self):
        """Export scene to HTML as StringIO buffer."""
        content = io.StringIO()
        if isinstance(self, PyVistaLocalView):
            data = self.export(format='zip')
            if data is None:
                msg = 'No data to write.'
                raise ValueError(msg)
            write_html(data, content)
            content.seek(0)
        elif isinstance(self, PyVistaRemoteLocalView):
            data = self.export_geometry(format='zip')
            if data is None:
                msg = 'No data to write.'
                raise ValueError(msg)
            write_html(data, content)
            content.seek(0)
        else:
            content = self.plotter.trame.export_html(filename=None)  # type: ignore[union-attr]
        return io.BytesIO(content.read().encode('utf8')).read()


class PyVistaRemoteView(VtkRemoteView, _BasePyVistaView):  # type: ignore[misc]
    """PyVista wrapping of trame ``VtkRemoteView`` for server rendering.

    This will connect to a PyVista plotter and stream the server-side
    renderings.

    Parameters
    ----------
    plotter : pyvista.Plotter
        The PyVista Plotter to display in the output view.

    interactive_ratio : int, optional
        Image size scale factor while interacting. Increasing this
        value will give higher resulotuion images during interaction
        events at the cost of performance. Use lower values (e.g.,
        ``0.5``) to increase performance while interacting.
        Defaults to 1.

    still_ratio : int, optional
        Image size scale factor while not interacting (still).
        Increasing this value will give higher resulotuion images
        when not interacting with the scene. Defaults to 1.

    namespace : str, optional
        The namespace for this view component. A default value is
        chosen based on the ``_id_name`` of the plotter.

    **kwargs : dict, optional
        Any additional keyword arguments to pass to
        ``trame.widgets.vtk.VtkRemoteView``.

    Notes
    -----
    For optimal rendering results, you may want to have the same
    value for ``interactive_ratio`` and ``still_ratio`` so that
    the entire rendering is not re-scaled between interaction events.

    """

    def __init__(
        self,
        plotter,
        *,
        interactive_ratio=None,
        still_ratio=None,
        namespace=None,
        **kwargs,
    ):  # numpydoc ignore=PR01,RT01
        """Create a trame remote view from a PyVista Plotter."""
        _BasePyVistaView.__init__(self, plotter)
        if namespace is None:
            namespace = f'{plotter._id_name}'
        if interactive_ratio is None:
            interactive_ratio = plotter._theme.trame.interactive_ratio
        if still_ratio is None:
            still_ratio = plotter._theme.trame.still_ratio
        VtkRemoteView.__init__(
            self,
            self.plotter.render_window,  # type: ignore[union-attr]
            interactive_ratio=interactive_ratio,
            still_ratio=still_ratio,
            __properties=[('still_ratio', 'stillRatio')],
            ref=f'view_{plotter._id_name}',
            namespace=namespace,
            **kwargs,
        )
        self._post_initialize()

    def push_camera(self, *args, **kwargs):  # pragma: no cover
        """No-op implementation to match local viewers."""

    def update_image(self, *args, **kwargs):  # numpydoc ignore=RT01
        """Wrap update call."""
        return self.update(*args, **kwargs)


class PyVistaLocalView(VtkLocalView, _BasePyVistaView):  # type: ignore[misc]
    """PyVista wrapping of trame VtkLocalView for in-browser rendering.

    This will connect to and synchronize with a PyVista plotter to
    perform client-side rendering with VTK.js in the browser.

    Parameters
    ----------
    plotter : pyvista.Plotter
        The PyVista Plotter to represent in the output view.

    namespace : str, optional
        The namespace for this view component. A default value is
        chosen based on the ``_id_name`` of the plotter.

    **kwargs : dict, optional
        Any additional keyword arguments to pass to
        ``trame.widgets.vtk.VtkLocalView``.

    """

    def __init__(self, plotter, *, namespace=None, **kwargs):
        """Create a trame local view from a PyVista Plotter."""
        _BasePyVistaView.__init__(self, plotter)
        if namespace is None:
            namespace = f'{plotter._id_name}'
        VtkLocalView.__init__(
            self,
            self.plotter.render_window,  # type: ignore[union-attr]
            ref=f'view_{plotter._id_name}',
            namespace=namespace,
            **kwargs,
        )
        self._post_initialize()

    def _post_initialize(self):
        """Register the orientation widgets after the base initialization."""
        super()._post_initialize()
        self.set_widgets(
            [ren.axes_widget for ren in self.plotter.renderers if ren.axes_widget is not None],  # type: ignore[union-attr]
        )

    def update_image(self, *args, **kwargs):  # pragma: no cover
        """No-op implementation to match remote viewers."""


class PyVistaRemoteLocalView(VtkRemoteLocalView, _BasePyVistaView):  # type: ignore[misc]
    """PyVista wrapping of trame ``VtkRemoteLocalView``.

    Dynamically switch between client and server rendering.

    Parameters
    ----------
    plotter : pyvista.Plotter
        The PyVista Plotter to display in the output view.

    interactive_ratio : int, optional
        Image size scale factor while interacting. Increasing this
        value will give higher resulotuion images during interaction
        events at the cost of performance. Use lower values (e.g.,
        ``0.5``) to increase performance while interacting.
        Defaults to 1. This is only valid in the ``'remote'`` mode.

    still_ratio : int, optional
        Image size scale factor while not interacting (still).
        Increasing this value will give higher resulotuion images
        when not interacting with the scene. Defaults to 1.
        This is only valid in the ``'remote'`` mode.

    namespace : str, optional
        The namespace for this view component. A default value is
        chosen based on the ``_id_name`` of the plotter.

    **kwargs : dict, optional
        Any additional keyword arguments to pass to
        ``trame.widgets.vtk.VtkRemoteLocalView``.

    """

    def __init__(
        self,
        plotter,
        *,
        interactive_ratio=None,
        still_ratio=None,
        namespace=None,
        **kwargs,
    ):  # numpydoc ignore=PR01,RT01
        """Create a trame remote/local view from a PyVista Plotter."""
        _BasePyVistaView.__init__(self, plotter)
        if namespace is None:
            namespace = f'{plotter._id_name}'
        if interactive_ratio is None:
            interactive_ratio = plotter._theme.trame.interactive_ratio
        if still_ratio is None:
            still_ratio = plotter._theme.trame.still_ratio
        VtkRemoteLocalView.__init__(
            self,
            self.plotter.render_window,  # type: ignore[union-attr]
            interactive_ratio=interactive_ratio,
            still_ratio=still_ratio,
            __properties=[('still_ratio', 'stillRatio')],
            ref=f'view_{plotter._id_name}',
            namespace=namespace,
            **kwargs,
        )
        # Track namespace for our use since trame attributes are name mangled
        self._namespace = namespace

        self._post_initialize()

    def _post_initialize(self):
        """Register the orientation widgets after the base initialization."""
        super()._post_initialize()
        self.set_widgets(
            [ren.axes_widget for ren in self.plotter.renderers if ren.axes_widget is not None],  # type: ignore[union-attr]
        )


class _BaseView(ABC):
    """Shared behavior of the PyVista trame views."""

    def __init__(self, plotter):
        """Initialize the base PyVista view."""
        self._plotter = weakref.ref(plotter)
        self._pyvista_initialize()
        self._plotter_render_callback = lambda *_: self.update()  # type: ignore[attr-defined]

    @property
    def plotter(self):
        """Return the plotter if still available or None."""
        return self._plotter()

    def _pyvista_initialize(self):
        """Validate the plotter and set default camera positions when unset."""
        if self.plotter.render_window is None:  # type: ignore[union-attr]
            raise RuntimeError(CLOSED_PLOTTER_ERROR)
        for renderer in self.plotter.renderers:  # type: ignore[union-attr]
            if not renderer.camera.is_set:
                renderer.camera_position = renderer.get_default_cam_pos()
                renderer.ResetCamera()

    def _post_initialize(self):
        """Link plotter render to view update."""
        # Callback to sync view on PyVista's render call when renders are suppressed
        self.plotter.add_on_render_callback(self._plotter_render_callback, render_event=False)  # type: ignore[union-attr]

    @abstractmethod
    def render(self):
        """Refresh view."""

    @abstractmethod
    def reset_camera(self):
        """Reset the camera to make the scene fit in the view."""

    @abstractmethod
    def _export_screenshot(self, filename):
        """Make the web client download a file capturing the current rendering."""

    def _update_camera(self):  # noqa: B027
        """Force camera synchronization if needed per concrete implementation."""

    def _set_widgets(self, widgets):  # noqa: B027
        """Register widgets if needed per concrete implementation."""

    def _export_html(self, mode='wasm32', rendering='webgl'):
        """Export scene to HTML as StringIO buffer."""
        from trame_vtklocal.utils import exporter

        vtk_objects = [
            self.plotter.render_window,
            *[ren.axes_widget for ren in self.plotter.renderers if ren.axes_widget is not None],
        ]

        return exporter.to_html(
            vtk_objects,
            config={'mode': mode, 'rendering': rendering, 'exec': 'async'},
        )

    def _export_data(self):
        """Export scene to ``wazex`` format (vtk-wasm) as StringIO buffer."""
        from trame_vtklocal.utils import exporter

        vtk_objects = [
            self.plotter.render_window,
            *[ren.axes_widget for ren in self.plotter.renderers if ren.axes_widget is not None],
        ]

        return exporter.to_wazex(vtk_objects)


class PyVistaWasmView(vtklocal.LocalView, _BaseView):  # type: ignore[misc]
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
        if not IS_WASM_SUPPORTED:
            raise pv.VTKVersionError(UPDATE_VTK_FOR_WASM)

        _BaseView.__init__(self, plotter)

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
        ext = Path(filename).suffix
        return self.download_screenshot(filename, f'image/{ext}')

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


class PyVistaRCAView(rca.RemoteControlledArea, _BaseView):  # type: ignore[misc]
    """PyVista wrapping of trame RemoteControlledArea for remote rendering.

    This will connect to and synchronize with a PyVista plotter to
    perform server-side rendering with trame-rca.

    Parameters
    ----------
    plotter : pyvista.Plotter
        The PyVista Plotter to represent in the output view.

    display : str, default: 'image'
        Display mode of the remote area. ``'image'`` streams JPEG images.

    target_fps : int, default: 60
        Maximum number of frames per second pushed to the client.

    **kwargs : dict, optional
        Any additional keyword arguments to pass to
        ``trame.widgets.rca.RemoteControlledArea``.

    """

    def __init__(self, plotter, *, display='image', target_fps=60, **kwargs):
        """Create a trame local view from a PyVista Plotter."""
        _BaseView.__init__(self, plotter)

        rca.RemoteControlledArea.__init__(
            self,
            display=display,
            **kwargs,
        )
        self.handler = self.create_view_handler(
            self.plotter.render_window,  # type: ignore[union-attr]
            encoder='turbo-jpeg' if display == 'image' else None,
            target_fps=target_fps,
        )

    def render(self):
        """Render and push a new image."""
        self.handler.update()

    def reset_camera(self):
        """Reset the plotter camera and push a new image."""
        self.plotter.reset_camera()
        self.render()

    def _update_camera(self):
        """Sync scene with camera update."""
        self.render()

    @property
    def target_fps(self):
        """Maximum number of frames per second pushed to the client."""
        return self.handler.target_fps

    @target_fps.setter
    def target_fps(self, v):
        self.handler.target_fps = v

    def _export_screenshot(self, filename):
        """Capture a screenshot of the plotter and return its bytes."""
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            screenshot_img_file = Path(tmp_dir_str) / filename
            self.plotter.screenshot(screenshot_img_file)
            return screenshot_img_file.read_bytes()
