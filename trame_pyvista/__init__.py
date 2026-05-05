"""Trame interface for PyVista."""

from __future__ import annotations

import logging

logging.getLogger('trame.app').disabled = True

try:
    from trame_pyvista._version import __version__
except ImportError:  # pragma: no cover
    __version__ = '0.0.0'

from pyvista import register_jupyter_backend
from pyvista import register_plotter_component

from trame_pyvista.components import TrameComponent
from trame_pyvista.jupyter import elegantly_launch
from trame_pyvista.jupyter import launch_server
from trame_pyvista.jupyter import show_trame
from trame_pyvista.ui import get_viewer
from trame_pyvista.ui import plotter_ui
from trame_pyvista.widgets import PyVistaLocalView
from trame_pyvista.widgets import PyVistaRemoteLocalView
from trame_pyvista.widgets import PyVistaRemoteView

register_plotter_component('trame', override=True)(TrameComponent)


# Override pyvista's bundled trame jupyter handlers so the backends
# resolve to this package. Without override=True, pyvista falls through
# to its internal `pyvista.trame.jupyter` shim because the names collide
# with built-in backend identifiers. PyVista's custom-handler dispatch
# does not forward the backend name, so each registration captures its
# own ``mode``.
def _make_handler(_mode: str):
    def _handler(plotter, **kwargs):
        kwargs.setdefault('mode', _mode)
        return show_trame(plotter, **kwargs)

    _handler.__name__ = f'show_trame_{_mode}'
    return _handler


for _backend in ('trame', 'server', 'client', 'html'):
    register_jupyter_backend(_backend, _make_handler(_backend), override=True)
del _backend


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
