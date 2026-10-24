"""Smoke-test every script in ``examples/`` by booting trame headless briefly."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from trame_pyvista.widgets import HAS_VTK_94

EXAMPLES_DIR = Path(__file__).parent.parent / 'examples'

NEEDS_VTK_94 = {
    'advanced/contour.py',
    'advanced/contour_modern.py',
    'advanced/contour_widgets.py',
    'basic/simple.py',
}


def _collect() -> list:
    scripts = sorted(
        str(path.relative_to(EXAMPLES_DIR))
        for path in EXAMPLES_DIR.rglob('*.py')
        if '__pycache__' not in path.parts
    )
    skip = pytest.mark.skipif(not HAS_VTK_94, reason='needs VTK >= 9.4')
    return [pytest.param(s, marks=skip) if s in NEEDS_VTK_94 else s for s in scripts]


@pytest.mark.parametrize('script', _collect())
def test_serve(script: str) -> None:
    env = {**os.environ, 'PYVISTA_OFF_SCREEN': 'true'}
    result = subprocess.run(
        [
            sys.executable,
            str(EXAMPLES_DIR / script),
            '--server',  # trame: do not open browser
            '--timeout',
            '1',
            '--port',
            '0',
        ],
        check=False,
        env=env,
        timeout=90,
    )
    assert result.returncode == 0
