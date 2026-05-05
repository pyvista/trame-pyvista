"""Shared pytest fixtures and CLI options."""

from __future__ import annotations

import pyvista as pv
import pytest

pv.OFF_SCREEN = True


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        '--playwright',
        action='store_true',
        default=False,
        help='Run Playwright-based tests (requires browser install).',
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption('--playwright'):
        return
    skip = pytest.mark.skip(reason='Playwright tests disabled (use --playwright).')
    for item in items:
        if 'needs_playwright' in item.keywords:
            item.add_marker(skip)
