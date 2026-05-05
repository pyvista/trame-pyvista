"""Trame interface for PyVista."""

from __future__ import annotations

import logging

logging.getLogger('trame.app').disabled = True

try:
    from trame_pyvista._version import __version__
except ImportError:  # pragma: no cover
    __version__ = '0.0.0'

from trame_pyvista.components import TrameComponent
from trame_pyvista.jupyter import elegantly_launch
from trame_pyvista.jupyter import launch_server
from trame_pyvista.jupyter import show_trame
from trame_pyvista.ui import get_viewer
from trame_pyvista.ui import plotter_ui
from trame_pyvista.views import PyVistaLocalView
from trame_pyvista.views import PyVistaRemoteLocalView
from trame_pyvista.views import PyVistaRemoteView


def _register_plotter_component() -> None:
    """Attach the ``trame`` namespace to ``pyvista.BasePlotter``.

    Tolerates older PyVista that lacks ``register_plotter_component``.
    """
    try:
        from pyvista import register_plotter_component
    except ImportError:
        return
    register_plotter_component('trame', override=True)(TrameComponent)


_register_plotter_component()


__all__ = [
    'PyVistaLocalView',
    'PyVistaRemoteLocalView',
    'PyVistaRemoteView',
    'TrameComponent',
    '__version__',
    'elegantly_launch',
    'get_viewer',
    'launch_server',
    'plotter_ui',
    'show_trame',
]
