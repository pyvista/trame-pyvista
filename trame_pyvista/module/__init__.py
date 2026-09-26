"""Trame module serving the static assets (styles) of trame-pyvista."""

from __future__ import annotations

from pathlib import Path

from trame_pyvista import __version__

__all__ = [
    'serve',
    'styles',
]

serve_path = str(Path(__file__).with_name('serve').resolve())
BASE_URL = f'__trame_pyvista_{__version__}'

serve = {
    BASE_URL: serve_path,
}
styles = [
    f'{BASE_URL}/style.css',
]
