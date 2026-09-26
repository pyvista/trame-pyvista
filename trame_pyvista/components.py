"""Plotter component exposing trame functionality on ``Plotter``.

Registers under the ``trame`` namespace via the
``pyvista.plotter_components`` entry-point group, so methods are reached
as ``plotter.trame.export_vtksz(...)``.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Literal

import pyvista as pv

if TYPE_CHECKING:
    from pyvista.plotting.plotter import BasePlotter


class TrameComponent:
    """Trame-backed exporters and viewer launchers for a Plotter."""

    def __init__(self, plotter: BasePlotter) -> None:
        self._plotter = plotter

    def export_html(self, filename: str | Path | None) -> io.StringIO | None:
        """Export the scene as a self-contained HTML file.

        Parameters
        ----------
        filename : str | Path | None
            Destination path. If ``None``, return the HTML as a
            ``StringIO`` buffer.

        Returns
        -------
        io.StringIO | None
            The HTML buffer when ``filename`` is ``None``, otherwise
            ``None`` after writing the file.

        """
        from trame_vtk.tools.vtksz2html import write_html

        data = self.export_vtksz(filename=None)
        buffer = io.StringIO()
        write_html(data, buffer)
        buffer.seek(0)

        if filename is None:
            return buffer

        path = Path(filename)
        if path.suffix != '.html':
            path = path.with_suffix('.html')
        with path.open('w', encoding='utf-8') as fh:
            fh.write(buffer.read())
        return None

    def export_vtksz(
        self,
        filename: str | Path | None = 'scene-export.vtksz',
        *,
        format: Literal['zip', 'json'] = 'zip',  # noqa: A002
    ) -> str | Path | bytes:
        """Export the scene as a VTK.js OfflineLocalView file.

        Parameters
        ----------
        filename : str | Path | None, optional
            Destination path. If ``None``, return the encoded bytes.

        format : {'zip', 'json'}, optional
            Container format.

        Returns
        -------
        str | Path | bytes
            The destination path, or the raw bytes when ``filename`` is
            ``None``.

        """
        from trame_pyvista.jupyter import elegantly_launch
        from trame_pyvista.widgets import PyVistaLocalView
        from trame_pyvista.widgets import get_server

        server = get_server(pv.global_theme.trame.jupyter_server_name)
        if not server.running:
            elegantly_launch(pv.global_theme.trame.jupyter_server_name)

        view = PyVistaLocalView(self._plotter, trame_server=server)
        try:
            content = view.export(format=format)
        finally:
            view.release_resources()
            self._plotter._on_render_callbacks.discard(view._plotter_render_callback)

        if filename is None:
            return content

        path = Path(filename)
        path.write_bytes(content)
        return filename

    def export_wazex(
        self,
        filename: str | Path | None = 'scene-export.wazex',
    ) -> str | Path | bytes:
        """Export the scene as a VTK-wasm data file for its offline Viewer.

        Parameters
        ----------
        filename : str | Path | None, optional
        Destination path. If ``None``, return the encoded bytes.

        Returns
        -------
        str | Path | bytes
        The destination path, or the raw bytes when ``filename`` is
        ``None``.

        """
        from trame_vtklocal.utils import exporter

        vtk_objects = [
            self._plotter.render_window,
            *[ren.axes_widget for ren in self._plotter.renderers if ren.axes_widget is not None],
        ]

        return exporter.to_wazex(
            vtk_objects=vtk_objects,
            output=filename,
        )

    def export_wasm_html(
        self, filename: str | Path | None, mode: str = 'wasm32', rendering: str = 'webgl'
    ) -> io.StringIO | None:
        """Export the scene as a self-contained HTML file using vtk-wasm viewer.

        Parameters
        ----------
        filename : str | Path | None
            Destination path. If ``None``, return the HTML as a
            ``StringIO`` buffer.

        mode: str = wasm32
            Choose between `wasm32` or `wasm64` for the viewer.

        rendering: str = webgl
            Choose between `webgl` or `webgpu` for the viewer.

        Returns
        -------
        io.StringIO | None
            The HTML buffer when ``filename`` is ``None``, otherwise
            ``None`` after writing the file.

        """
        from trame_vtklocal.utils import exporter

        vtk_objects = [
            self._plotter.render_window,
            *[ren.axes_widget for ren in self._plotter.renderers if ren.axes_widget is not None],
        ]

        return exporter.to_html(
            vtk_objects=vtk_objects,
            output=filename,
            config={
                'mode': mode,
                'rendering': rendering,
                'exec': 'async',
            },
        )

    def show(self, **kwargs):
        """Display the plotter via trame in Jupyter.

        Thin wrapper around :func:`trame_pyvista.jupyter.show_trame`.

        Returns
        -------
        ipywidgets.widgets.HTML | IPython.display.IFrame
            The widget produced by the trame backend.

        """
        from trame_pyvista.jupyter import show_trame

        return show_trame(self._plotter, **kwargs)

    def app(self, name=None):
        """Return a trame app for the plotter which can be display in Jupyter.

        Returns
        -------
        A trame application for your plotter that can be displayed in Jupyter by
        simply returning it. But keeping a reference to it, allow you to also control it
        programatically.

        """
        from trame_pyvista.apps import create_application

        return create_application(name, pv.global_theme.trame.jupyter_server_name, self._plotter)
