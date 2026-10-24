"""Tests for the anywidget container widget (client-side PyVista rendering)."""

from __future__ import annotations

import base64
from http.server import SimpleHTTPRequestHandler
from http.server import ThreadingHTTPServer
import io
import os
from pathlib import Path
import threading

from PIL import Image
import pytest
import pyvista as pv

import trame_pyvista.anywidget as aw
from trame_pyvista.anywidget import PyVistaWidget
from trame_pyvista.anywidget import from_plotter
from trame_pyvista.anywidget import show_anywidget


def _sphere_scene() -> pv.Plotter:
    pl = pv.Plotter(window_size=(400, 300))
    pl.add_mesh(pv.Sphere(), show_edges=True)
    return pl


def _png_unique_colors(png_bytes: bytes) -> int:
    """Count distinct colors in a PNG (decodes with Pillow)."""
    image = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
    return len(image.getcolors(maxcolors=1_000_000) or [1])


def test_pyvista_widget_creation():
    pl = _sphere_scene()
    widget = from_plotter(pl, height=320)
    assert isinstance(widget, PyVistaWidget)
    assert widget._model_name == 'AnyModel'
    assert widget._model_module == 'anywidget'
    assert widget._view_module == 'anywidget'
    assert widget.height == 320
    # The embedded scene is a base64 zip produced by export_vtksz.
    raw = base64.b64decode(widget.data)
    assert raw[:2] == b'PK'


def test_pyvista_widget_accepts_raw_data():
    pl = _sphere_scene()
    payload = base64.b64encode(base64.b64decode(from_plotter(pl).data)).decode('ascii')
    widget = PyVistaWidget(data=payload, height=200)
    assert widget.data == payload
    assert widget.height == 200
    assert base64.b64decode(widget.data)[:2] == b'PK'


def test_pyvista_widget_traits_sync():
    widget = PyVistaWidget(height=100)
    assert widget.data == ''
    widget.data = base64.b64encode(b'PK\x03\x04').decode('ascii')
    assert widget.data == base64.b64encode(b'PK\x03\x04').decode('ascii')
    widget.height = 777
    assert widget.height == 777


def test_pyvista_widget_state_is_synced():
    """``data`` and ``height`` must reach the frontend, i.e. appear in the
    synced state sent over the comm.

    Without ``sync=True`` on the traits the frontend receives an empty model
    and renders a blank container (regression: marimo / JupyterLab render).
    """
    pl = _sphere_scene()
    widget = from_plotter(pl, height=320)
    state = widget.get_state()
    assert 'data' in state
    assert 'height' in state
    assert state['height'] == 320
    assert base64.b64decode(state['data'])[:2] == b'PK'
    assert {'data', 'height'}.issubset(widget.keys)


def test_to_anywidget_component():
    pl = _sphere_scene()
    widget = pl.trame.to_anywidget(height=300)
    assert isinstance(widget, PyVistaWidget)
    assert widget.height == 300
    assert base64.b64decode(widget.data)[:2] == b'PK'


def test_show_anywidget_backend():
    pl = pv.Plotter(notebook=True, window_size=(400, 300))
    pl.add_mesh(pv.Sphere(), show_edges=True)
    widget = pl.show(jupyter_backend='anywidget', return_viewer=True, auto_close=False)
    assert isinstance(widget, PyVistaWidget)
    assert widget._model_module == 'anywidget'
    assert base64.b64decode(widget.data)[:2] == b'PK'


def test_show_anywidget_accepts_screenshot_kwarg():
    """PyVista forwards ``screenshot`` to backend handlers; it must be tolerated."""
    pl = _sphere_scene()
    widget = show_anywidget(pl, screenshot=None)
    assert isinstance(widget, PyVistaWidget)


def test_esm_is_self_contained():
    """The bundled ESM must embed the viewer and disable standalone auto-boot."""
    esm = aw._ESM
    assert 'trame_pyvista_widget' in esm
    assert 'window.OfflineLocalView' in esm
    assert 'export default trame_pyvista_widget' in esm
    # The standalone-page boot (file-drop zone / URL auto-load) must be off,
    # otherwise it would mutate the host notebook page.
    assert 'setTimeout(()=>{ra&&(window?.loadDataSet?.(),ra&&q0())},100)' not in esm


@pytest.mark.parametrize(
    'html',
    [
        '<html></html>',
        '<script type="module">var a=1;</script>',
        '<script type="module">window.OfflineLocalView={load(){}</script>',
    ],
)
def test_extract_viewer_rejects_unexpected_html(html: str):
    """A changed trame-vtk viewer page raises instead of shipping a broken bundle."""
    with pytest.raises(RuntimeError, match='OfflineLocalView'):
        aw._extract_viewer(html)


@pytest.mark.needs_playwright
def test_anywidget_widget_renders_in_browser(tmp_path: Path) -> None:
    """Render the anywidget widget in Chromium and confirm the canvas is interactive.

    This exercises the exact ESM bundle that ``anywidget`` evaluates, with a
    minimal model shim standing in for the ipywidgets model.
    """
    from playwright.sync_api import sync_playwright

    pl = _sphere_scene()
    payload = from_plotter(pl).data

    site = tmp_path / 'site'
    site.mkdir()
    (site / 'bundle.mjs').write_text(aw._ESM, encoding='utf-8')
    (site / 'index.html').write_text(
        f"""<!doctype html>
<html><head><meta charset="utf-8"></head>
<body>
<div id="host" style="width:400px;height:300px;background:#fff"></div>
<script type="module">
  window.__errors = [];
  window.addEventListener('error', (e) => window.__errors.push(String(e.message)));
  const host = document.getElementById('host');
  const state = {{ data: "{payload}", height: 300 }};
  const model = {{
    get: (key) => state[key],
    on: () => {{}},
    off: () => {{}},
    send: () => {{}},
  }};
  const bundle = await import('./bundle.mjs');
  const controller = new AbortController();
  window.__cleanup = bundle.default.render({{
    model, el: host, signal: controller.signal,
  }});
  window.__ready = true;
</script>
</body></html>
"""
    )

    old_cwd = Path.cwd()
    os.chdir(site)
    server = ThreadingHTTPServer(('127.0.0.1', 0), SimpleHTTPRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page_errors: list[str] = []
            page.on('pageerror', lambda e: page_errors.append(str(e)))
            page.goto(f'http://{host}:{port}/index.html')
            page.wait_for_function('window.__ready === true', timeout=20_000)

            canvas = page.locator('canvas')
            canvas.wait_for(timeout=20_000)
            page.wait_for_timeout(1500)

            # The standalone viewer must not have injected a file-drop UI.
            assert page.locator('input[type=file]').count() == 0
            assert page.evaluate('document.body.className') == ''
            before = canvas.screenshot()
            # The canvas must contain a rendered scene, not a blank buffer
            # (decode the composited screenshot; a WebGL buffer cannot be
            # sampled reliably after compositing).
            unique_colors = _png_unique_colors(before)
            assert unique_colors > 1, f'canvas appears blank ({unique_colors} colors)'
            box = canvas.bounding_box()
            assert box is not None
            x = box['x'] + box['width'] / 2
            y = box['y'] + box['height'] / 2
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + 150, y + 80, steps=8)
            page.mouse.up()
            page.wait_for_timeout(800)
            after = canvas.screenshot()
            assert before != after

            assert page_errors == []
            assert page.evaluate('window.__errors') == []
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        os.chdir(old_cwd)
