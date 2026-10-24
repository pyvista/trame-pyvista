"""Trame namespace shim exposing ``trame_pyvista`` view widgets.

Mirrors the convention used by ``trame-vtk`` and ``trame-vuetify``, where
sibling packages contribute modules to the ``trame.widgets`` namespace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trame_pyvista.vue3_widgets import PyVistaPlotterControls
from trame_pyvista.widgets import PyVistaLocalView
from trame_pyvista.widgets import PyVistaRemoteLocalView
from trame_pyvista.widgets import PyVistaRemoteView

if TYPE_CHECKING:
    from trame_pyvista.rca_view import PyVistaRCAView
    from trame_pyvista.wasm_view import PyVistaWasmView

__all__ = [
    'PyVistaLocalView',
    'PyVistaPlotterControls',
    'PyVistaRCAView',
    'PyVistaRemoteLocalView',
    'PyVistaRemoteView',
    'PyVistaWasmView',
]


def __getattr__(name):  # numpydoc ignore=RT01
    """Import the trame-rca and trame-vtklocal views lazily, they need VTK >= 9.4."""
    from trame_pyvista import widgets

    return getattr(widgets, name)
