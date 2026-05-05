"""Smoke-test every script in ``examples/`` by running it briefly with ``--serve``."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / 'examples'


def _collect() -> list[str]:
    return sorted(
        str(path.relative_to(EXAMPLES_DIR))
        for path in EXAMPLES_DIR.rglob('*.py')
        if '__pycache__' not in path.parts
    )


@pytest.mark.parametrize('script', _collect())
def test_serve(script: str) -> None:
    result = subprocess.run(
        [sys.executable, str(EXAMPLES_DIR / script), '--serve', '--timeout', '1', '--port', '0'],
        check=False,
    )
    assert result.returncode == 0
