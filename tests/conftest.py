"""Shared pytest fixtures and CLI options."""

from __future__ import annotations

import pytest
import pyvista as pv

from trame_pyvista.widgets import HAS_VTK_94

pv.OFF_SCREEN = True

# trame-vtklocal, imported by test_wasm.py, fails to import below VTK 9.4
collect_ignore = [] if HAS_VTK_94 else ['test_wasm.py']


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        '--playwright',
        action='store_true',
        default=False,
        help='Run Playwright-based tests (requires browser install).',
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption('--playwright'):
        return
    skip = pytest.mark.skip(reason='Playwright tests disabled (use --playwright).')
    for item in items:
        if 'needs_playwright' in item.keywords:
            item.add_marker(skip)
