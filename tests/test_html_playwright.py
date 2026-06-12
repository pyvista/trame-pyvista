from __future__ import annotations

from http.server import SimpleHTTPRequestHandler
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
from threading import Thread

import pytest
import pyvista as pv


@pytest.mark.needs_playwright
def test_offlineviewer_interactive(tmp_path: Path) -> None:
    """Browser-driven test for the ``offlineviewer`` Sphinx directive.

    Builds the ``tinypages`` fixture (which embeds an interactive trame
    scene exported via :mod:`trame_pyvista.sphinx_ext`), serves it over
    HTTP, and uses Playwright to confirm a user can interact with the
    embedded canvas.
    """
    from playwright.sync_api import sync_playwright

    source_dir = Path(__file__).parent / 'tinypages'
    html_dir = tmp_path / '_build'

    result = subprocess.run(
        ['sphinx-build', '-b', 'html', str(source_dir), str(html_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    old_cwd = Path.cwd()
    os.chdir(html_dir)

    server = ThreadingHTTPServer(('127.0.0.1', 0), SimpleHTTPRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            host, port = server.server_address
            page.goto(f'http://{host}:{port}/some_plots.html')
            page.wait_for_timeout(1000)

            page.get_by_text('Interactive Scene', exact=True).first.click()
            page.wait_for_timeout(1000)

            frame = page.frame_locator('iframe').first
            canvas = frame.locator('canvas')
            canvas.wait_for(timeout=10000)

            before = canvas.screenshot()

            box = canvas.bounding_box()
            assert box is not None
            x = box['x'] + box['width'] / 2
            y = box['y'] + box['height'] / 2

            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + 200, y + 100)
            page.mouse.up()
            page.wait_for_timeout(500)

            after = canvas.screenshot()
            assert before != after
    finally:
        server.shutdown()
        server.server_close()
        os.chdir(old_cwd)


BASELINE_IMAGE_NAME = 'html_screenshot_baseline.png'


@pytest.fixture
def sphere_html_screenshot(tmp_path):
    window_size = (400, 300)

    def generate_html(out_path: Path) -> None:
        # Minimal reproducer from https://github.com/pyvista/trame-pyvista/issues/73
        # It's very important to use 'html' backend here
        pv.set_jupyter_backend('html')
        pl = pv.Plotter(window_size=window_size)
        pl.add_mesh(pv.Sphere(), show_edges=True)
        pl.export_html(out_path)

    def html_screenshot(html_file: Path, screenshot_file: Path, window_size=window_size) -> Path:
        # Convert html file to a png
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context().new_page()

            page.set_viewport_size({'width': window_size[0], 'height': window_size[1]})
            page.goto(f'file://{html_file}')
            page.screenshot(path=str(screenshot_file))

            browser.close()

    html_file = tmp_path / 'scene.html'
    png_file = tmp_path / BASELINE_IMAGE_NAME

    generate_html(html_file)
    html_screenshot(html_file, png_file)
    assert png_file.is_file()
    return png_file


@pytest.mark.needs_playwright
def test_export_html_sphere_screenshot(sphere_html_screenshot) -> None:
    # Regression test for https://github.com/pyvista/trame-pyvista/issues/73
    expected = Path(__file__).parent / BASELINE_IMAGE_NAME
    assert expected.is_file()

    error = pv.compare_images(sphere_html_screenshot, expected)
    assert error < 200
