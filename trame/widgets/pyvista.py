"""Trame namespace shim exposing ``trame_pyvista`` view widgets.

Mirrors the convention used by ``trame-vtk`` and ``trame-vuetify``, where
sibling packages contribute modules to the ``trame.widgets`` namespace.
"""

from __future__ import annotations

from trame_pyvista.vue3_widgets import PyVistaPlotterControls
from trame_pyvista.widgets import PyVistaLocalView
from trame_pyvista.widgets import PyVistaRCAView
from trame_pyvista.widgets import PyVistaRemoteLocalView
from trame_pyvista.widgets import PyVistaRemoteView
from trame_pyvista.widgets import PyVistaWasmView

__all__ = [
    'PyVistaLocalView',
    'PyVistaPlotterControls',
    'PyVistaRCAView',
    'PyVistaRemoteLocalView',
    'PyVistaRemoteView',
    'PyVistaWasmView',
]
