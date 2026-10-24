"""PyVista view rendered server side with trame-rca."""

from __future__ import annotations

from pathlib import Path
import tempfile

from trame.widgets import rca

from trame_pyvista import widgets as pv_widgets


class PyVistaRCAView(rca.RemoteControlledArea, pv_widgets._BaseView):  # type: ignore[misc]
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
        pv_widgets._BaseView.__init__(self, plotter)

        rca.RemoteControlledArea.__init__(
            self,
            display=display,
            **kwargs,
        )
        self.handler = self.create_view_handler(
            self.plotter.render_window,  # type: ignore[union-attr]
            encoder='jpeg' if display == 'image' else None,
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
