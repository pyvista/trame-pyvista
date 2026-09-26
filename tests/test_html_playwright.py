from __future__ import annotations

from http.server import SimpleHTTPRequestHandler
from http.server import ThreadingHTTPServer
import io
import os
from pathlib import Path
import subprocess
import sys
from threading import Thread
import time

import numpy as np
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
        [sys.executable, '-m', 'sphinx', '-b', 'html', str(source_dir), str(html_dir)],
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
SUBPLOTS_BASELINE_IMAGE_NAME = 'html_subplots_baseline.png'
WINDOW_SIZE = (400, 300)


def _sphere_scene() -> pv.Plotter:
    # Minimal reproducer from https://github.com/pyvista/trame-pyvista/issues/73
    pl = pv.Plotter(window_size=WINDOW_SIZE)
    pl.add_mesh(pv.Sphere(), show_edges=True)
    return pl


def _subplots_scene() -> pv.Plotter:
    # Subplots regression, https://github.com/pyvista/trame-pyvista/issues/9
    pl = pv.Plotter(shape=(1, 2), window_size=WINDOW_SIZE)
    pl.subplot(0, 0)
    pl.add_mesh(pv.Sphere(), color='tomato', show_edges=True)
    pl.subplot(0, 1)
    pl.add_mesh(pv.Cube(), color='steelblue')
    return pl


def _html_screenshot(html_file: Path, screenshot_file: Path) -> None:
    """Render an exported HTML scene in Chromium and save a PNG of it."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()
        page.set_viewport_size({'width': WINDOW_SIZE[0], 'height': WINDOW_SIZE[1]})
        page.goto(f'file://{html_file}')
        page.screenshot(path=str(screenshot_file))
        browser.close()


def _export_and_screenshot(build_scene, tmp_path: Path, name: str) -> Path:
    """Export ``build_scene()`` through the ``html`` backend and screenshot it."""
    # It's very important to use 'html' backend here
    pv.set_jupyter_backend('html')
    pl = build_scene()
    html_file = tmp_path / 'scene.html'
    pl.trame.export_html(html_file)
    png_file = tmp_path / name
    _html_screenshot(html_file, png_file)
    assert png_file.is_file()
    return png_file


@pytest.mark.needs_playwright
def test_export_html_sphere_screenshot(tmp_path) -> None:
    # Regression test for https://github.com/pyvista/trame-pyvista/issues/73
    screenshot = _export_and_screenshot(_sphere_scene, tmp_path, BASELINE_IMAGE_NAME)
    expected = Path(__file__).parent / BASELINE_IMAGE_NAME
    assert expected.is_file()
    assert pv.compare_images(screenshot, expected) < 200


@pytest.mark.needs_playwright
def test_export_html_subplots_screenshot(tmp_path) -> None:
    # Regression test for https://github.com/pyvista/trame-pyvista/issues/9
    screenshot = _export_and_screenshot(_subplots_scene, tmp_path, SUBPLOTS_BASELINE_IMAGE_NAME)
    expected = Path(__file__).parent / SUBPLOTS_BASELINE_IMAGE_NAME
    assert expected.is_file()
    assert pv.compare_images(screenshot, expected) < 200


def _png_pixels(data: bytes) -> np.ndarray:
    """Decode PNG bytes into an RGB array."""
    from PIL import Image

    return np.asarray(Image.open(io.BytesIO(data)).convert('RGB'))


@pytest.fixture
def served_plotter(request):
    """Serve the two-subplot scene in a subprocess and yield its iframe URL."""
    client_type, mode = request.param
    script = Path(__file__).parent / '_serve_plotter.py'
    proc = subprocess.Popen(
        [sys.executable, str(script), '--client-type', client_type, '--mode', mode],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, 'PYVISTA_OFF_SCREEN': 'true'},
    )
    lines: list[str] = []
    url = None
    deadline = time.monotonic() + 90
    try:
        while time.monotonic() < deadline and proc.poll() is None:
            line = proc.stdout.readline()
            lines.append(line)
            if line.startswith('URL '):
                url = line.split()[1]
                break
        assert url is not None, ''.join(lines)
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.mark.needs_playwright
@pytest.mark.parametrize(
    'served_plotter',
    [(ct, mode) for ct in ('vue2', 'vue3') for mode in ('trame', 'server', 'client')],
    ids=lambda p: f'{p[0]}-{p[1]}',
    indirect=True,
)
def test_jupyter_app_renders_in_browser(served_plotter) -> None:
    """Load the Jupyter iframe target in Chromium and interact with it.

    Covers what the unit tests cannot: the client actually receives the
    scene, draws both subplots, and reacts to camera controls and mouse.
    """
    from playwright.sync_api import sync_playwright

    page_errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 800, 'height': 500})
        page.on('pageerror', lambda err: page_errors.append(str(err)))
        page.goto(served_plotter)

        # Server rendering streams into an <img>; client rendering draws a <canvas>.
        view = page.locator('img, canvas').filter(visible=True).first
        view.wait_for(timeout=30000)
        page.wait_for_timeout(2000)

        def rendered() -> np.ndarray:
            return _png_pixels(view.screenshot())

        first = rendered()
        height, width = first.shape[:2]
        sphere = first[int(0.55 * height), int(0.25 * width)]
        cube = first[int(0.55 * height), int(0.75 * width)]
        assert sphere[0] > sphere[2] + 40, f'left subplot not tomato: {sphere}'
        assert cube[2] > cube[0] + 40, f'right subplot not steelblue: {cube}'

        page.locator('.mdi-axis-z-arrow').first.click()
        page.wait_for_timeout(1500)
        after_view_xy = rendered()
        assert not np.array_equal(first, after_view_xy)

        box = view.bounding_box()
        assert box is not None
        x, y = box['x'] + box['width'] / 4, box['y'] + box['height'] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 100, y + 60, steps=10)
        page.mouse.up()
        page.wait_for_timeout(1500)
        after_drag = rendered()
        assert not np.array_equal(after_view_xy, after_drag)

        browser.close()

    assert page_errors == []
