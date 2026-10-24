"""Smoke-test every script in ``examples/`` by booting trame headless briefly."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest
import pyvista as pv

EXAMPLES_DIR = Path(__file__).parent.parent / 'examples'

pytestmark = pytest.mark.skipif(
    pv.vtk_version_info < (9, 4), reason='the examples use VTK >= 9.4 APIs and trame-rca'
)


def _collect() -> list[str]:
    return sorted(
        str(path.relative_to(EXAMPLES_DIR))
        for path in EXAMPLES_DIR.rglob('*.py')
        if '__pycache__' not in path.parts
    )


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
