from __future__ import annotations

import contextlib
from http.server import SimpleHTTPRequestHandler
from http.server import ThreadingHTTPServer
import io
import os
from pathlib import Path
import queue
import socket
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


_RENDER_SCENE_JS = """async ([esm, state, page]) => {
  const mod = await import(URL.createObjectURL(new Blob([esm], {type: 'text/javascript'})));
  const viewer = state._viewer_page?.replace('IPY_MODEL_', '');
  window.sceneState = state;
  const model = {
    get: (key) => window.sceneState[key],
    on: (_, handler) => { window.sceneChanged = handler; },
    off: () => {},
    widget_manager: {
      get_model: async (id) => ({get: (key) => (id === viewer && key === 'html_gz' ? page : '')}),
    },
  };
  const el = document.createElement('div');
  document.body.appendChild(el);
  await mod.default.render({model, el});
}"""


_RENDER_HTML_JS = """async ([esm, value]) => {
  const mod = await import(URL.createObjectURL(new Blob([esm], {type: 'text/javascript'})));
  const state = {value};
  const handlers = new Set();
  const model = {
    get: (key) => state[key],
    on: (_, handler) => handlers.add(handler),
    off: (_, handler) => handlers.delete(handler),
  };
  const el = document.createElement('div');
  const html = [];
  const cleanup = await mod.default.render({model, el});
  html.push(el.innerHTML);
  state.value = '<p>changed</p>';
  handlers.forEach((handler) => handler());
  html.push(el.innerHTML);
  cleanup();
  return [html, handlers.size];
}"""


@pytest.mark.needs_playwright
def test_widget_renders_in_browser() -> None:
    """Render a trame backend widget through its anywidget module with a stand-in model."""
    from playwright.sync_api import sync_playwright

    from trame_pyvista.jupyter import _HTML_ESM
    from trame_pyvista.jupyter import Widget

    widget = Widget(None, 'about:blank', width='10px', height='20px')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content('<html><body></body></html>')
        html, handlers = page.evaluate(_RENDER_HTML_JS, [_HTML_ESM, widget.value])
        browser.close()
    assert html == [widget.value, '<p>changed</p>']
    assert handlers == 0


@pytest.mark.needs_playwright
@pytest.mark.parametrize('viewer_page', ['shared', 'embedded'])
def test_embeddable_widget_renders_in_browser(viewer_page: str) -> None:
    """Render an html backend widget through its anywidget module with a stand-in model."""
    from playwright.sync_api import sync_playwright

    from trame_pyvista.jupyter import _SCENE_ESM
    from trame_pyvista.jupyter import _scene_esm_with_page

    pl = pv.Plotter(notebook=True)
    pl.add_mesh(pv.Sphere())
    widget = pl.show(jupyter_backend='html', return_viewer=True)
    state = {key: widget.get_state()[key] for key in ('scene', 'iframe_style', '_viewer_page')}
    esm = _SCENE_ESM
    if viewer_page == 'embedded':
        esm, state['_viewer_page'] = _scene_esm_with_page(), None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content('<html><body></body></html>')
        page.evaluate(_RENDER_SCENE_JS, [esm, state, widget._viewer_page.html_gz])
        canvas = page.frame_locator('iframe.pyvista').locator('canvas')
        canvas.wait_for(timeout=10000)
        iframe = page.locator('iframe.pyvista')
        assert iframe.evaluate('e => e.style.borderStyle') == 'solid'
        for _ in range(50):
            pixels = _png_pixels(canvas.screenshot())
            height, width = pixels.shape[:2]
            if not np.array_equal(pixels[height // 2, width // 2], pixels[2, 2]):
                break
            page.wait_for_timeout(200)
        else:
            pytest.fail('The scene drew nothing at the canvas centre.')

        before = iframe.evaluate('e => e.srcdoc')
        page.evaluate(
            'async (scene) => { window.sceneState.scene = scene; await window.sceneChanged(); }',
            'QUJD',
        )
        after = iframe.evaluate('e => e.srcdoc')
        assert 'base64Str: "QUJD"' in after
        assert before.replace(state['scene'], 'QUJD') == after
        browser.close()


@contextlib.contextmanager
def _serve_marimo(notebook, *args):
    """Serve ``notebook`` with ``marimo <args>`` on a free port and yield its URL."""
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, '-m', 'marimo', *args, '--headless', '--port', str(port), notebook],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, 'PYVISTA_OFF_SCREEN': 'true'},
    )
    output: queue.Queue[str] = queue.Queue()

    def drain():
        """Forward every output line so the pipe never fills."""
        for line in proc.stdout:
            output.put(line)

    Thread(target=drain, daemon=True).start()
    lines: list[str] = []
    url = None
    deadline = time.monotonic() + 90
    try:
        while url is None and time.monotonic() < deadline:
            try:
                line = output.get(timeout=1)
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue
            lines.append(line)
            if 'URL:' in line:
                url = line.split('URL:')[1].strip()
        assert url is not None, ''.join(lines)
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.fixture
def marimo_notebook(tmp_path):
    """Write the marimo plots notebook with cells running on open, and return its path."""
    pytest.importorskip('marimo')
    notebook = tmp_path / 'plots.py'
    notebook.write_text((Path(__file__).parent / '_marimo_plots.py').read_text())
    (tmp_path / 'pyproject.toml').write_text('[tool.marimo.runtime]\nauto_instantiate = true\n')
    return notebook


@pytest.fixture
def marimo_url(marimo_notebook):
    """Serve the plots notebook with ``marimo edit`` and yield its URL."""
    with _serve_marimo(marimo_notebook, 'edit', '--no-token') as url:
        yield url


@pytest.fixture
def marimo_run_url(marimo_notebook):
    """Serve the plots notebook with ``marimo run``, closing sessions 2 s after they disconnect."""
    with _serve_marimo(marimo_notebook, 'run', '--session-ttl', '2') as url:
        yield url


def _drawn_plots(page) -> list[bool]:
    """Return whether each pyvista iframe's canvas differs between its centre and corner."""
    drawn = []
    for iframe in page.locator('iframe.pyvista').all():
        canvas = iframe.content_frame.locator('canvas').first
        for _ in range(60):
            pixels = _png_pixels(canvas.screenshot())
            height, width = pixels.shape[:2]
            if not np.array_equal(pixels[height // 2, width // 2], pixels[2, 2]):
                drawn.append(True)
                break
            page.wait_for_timeout(250)
        else:
            drawn.append(False)
    return drawn


@pytest.mark.needs_playwright
def test_marimo_plots_survive_cell_rerun_and_reload(marimo_url) -> None:
    """Run the plots in marimo, re-run the first plot cell, then reload the page."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1200, 'height': 1400})
        page.goto(marimo_url)
        page.locator('iframe.pyvista').nth(2).wait_for(timeout=90000)
        assert _drawn_plots(page) == [True, True, True]

        first = page.locator('iframe.pyvista').first
        before = first.evaluate('e => e.srcdoc')
        page.locator('[data-testid=cell-editor]').nth(1).click()
        page.keyboard.press('Shift+Enter')
        for _ in range(240):
            page.wait_for_timeout(250)
            if first.evaluate('e => e.srcdoc') != before:
                break
        else:
            pytest.fail('Re-running the cell did not replace its plot.')
        assert _drawn_plots(page) == [True, True, True]

        page.reload()
        page.locator('iframe.pyvista').nth(2).wait_for(timeout=60000)
        assert _drawn_plots(page) == [True, True, True]
        browser.close()


_SCENE_FALLBACK_JS = """async ([esm, state, gz, html, dropInflate, noKernel, cached]) => {
  const load = () => import(URL.createObjectURL(new Blob([esm], {type: 'text/javascript'})));
  if (dropInflate) delete window.DecompressionStream;
  let inflations = 0;
  if (window.DecompressionStream) {
    const Inflate = window.DecompressionStream;
    window.DecompressionStream = class extends Inflate {
      constructor(format) { super(format); inflations += 1; }
    };
  }
  const viewerState = {html_gz: gz, html: cached ? html : '', plain: cached};
  const requests = [];
  const viewer = {
    comm_live: !noKernel,
    get: (key) => viewerState[key],
    set: (key, value) => { viewerState[key] = value; },
    save_changes: () => {
      if (noKernel) return;
      requests.push({...viewerState});
      viewerState.html = html;
      setTimeout(() => viewer.filled?.(), 0);
    },
    once: (_, handler) => { viewer.filled = handler; },
  };
  const model = {
    get: (key) => state[key],
    on: () => {},
    off: () => {},
    widget_manager: {get_model: async () => viewer},
  };
  const els = [document.createElement('div'), document.createElement('div')];
  for (const el of els) {
    document.body.appendChild(el);
    await (await load()).default.render({model, el});
  }
  return [els.map((el) => el.querySelector('iframe').srcdoc), requests, inflations];
}"""


@pytest.mark.needs_playwright
@pytest.mark.parametrize(
    'case', ['inflate', 'no_inflate', 'no_gz', 'bad_gzip', 'no_kernel', 'plain_cached']
)
def test_embeddable_widget_falls_back(case: str) -> None:
    """Fall back to the plain viewer page, or show the error."""
    from playwright.sync_api import sync_playwright

    from trame_pyvista.jupyter import _SCENE_ESM

    pl = pv.Plotter(notebook=True)
    pl.add_mesh(pv.Sphere())
    widget = pl.show(jupyter_backend='html', return_viewer=True)
    state = {key: widget.get_state()[key] for key in ('scene', 'iframe_style', '_viewer_page')}
    html = '<html><body><p>plain</p></body></html>'
    real_gz = widget._viewer_page.html_gz
    gz = {'bad_gzip': 'QUJD', 'no_gz': ''}.get(case, real_gz)
    drop_inflate = case in ('no_inflate', 'no_kernel', 'plain_cached')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content('<html><body></body></html>')
        docs, requests, inflations = page.evaluate(
            _SCENE_FALLBACK_JS,
            [
                _SCENE_ESM,
                state,
                gz,
                html,
                drop_inflate,
                case == 'no_kernel',
                case == 'plain_cached',
            ],
        )
        browser.close()
    assert docs[0] == docs[1]
    assert inflations == {'inflate': 1, 'bad_gzip': 2}.get(case, 0)
    if case == 'inflate':
        assert f'base64Str: "{state["scene"]}"' in docs[0]
        assert requests == []
    elif case == 'bad_gzip':
        assert 'could not load the viewer page' in docs[0]
        assert requests == []
    elif case == 'no_kernel':
        assert (
            'viewer page: this browser cannot unpack the viewer page without a running kernel'
            in docs[0]
        )
        assert requests == []
    elif case == 'plain_cached':
        assert docs[0].startswith('<html><body><p>plain</p>')
        assert f'base64Str: "{state["scene"]}"' in docs[0]
        assert requests == []
    else:
        assert docs[0].startswith('<html><body><p>plain</p>')
        assert f'base64Str: "{state["scene"]}"' in docs[0]
        assert [r['plain'] for r in requests] == [True]


_SCENE_EVENTS_JS = """async ([esm, state, page]) => {
  const mod = await import(URL.createObjectURL(new Blob([esm], {type: 'text/javascript'})));
  const viewer = state._viewer_page.replace('IPY_MODEL_', '');
  const handlers = {};
  const model = {
    get: (key) => state[key],
    on: (event, handler) => { (handlers[event] ||= new Set()).add(handler); },
    off: (event, handler) => { handlers[event]?.delete(handler); },
    widget_manager: {
      get_model: async (id) => ({get: (key) => (id === viewer && key === 'html_gz' ? page : '')}),
    },
  };
  const el = document.createElement('div');
  document.body.appendChild(el);
  const cleanup = await mod.default.render({model, el});
  state.iframe_style = 'width: 123px; height: 45px;';
  for (const event of ['change', 'change:iframe_style']) {
    for (const handler of handlers[event] || []) await handler();
  }
  const width = el.querySelector('iframe').style.width;
  cleanup();
  return [width, Object.values(handlers).reduce((n, set) => n + set.size, 0)];
}"""


@pytest.mark.needs_playwright
def test_embeddable_widget_follows_style_and_cleans_up() -> None:
    """Restyle an html backend widget, then check its cleanup removes every listener."""
    from playwright.sync_api import sync_playwright

    from trame_pyvista.jupyter import _SCENE_ESM

    pl = pv.Plotter(notebook=True)
    pl.add_mesh(pv.Sphere())
    widget = pl.show(jupyter_backend='html', return_viewer=True)
    state = {key: widget.get_state()[key] for key in ('scene', 'iframe_style', '_viewer_page')}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content('<html><body></body></html>')
        width, handlers = page.evaluate(
            _SCENE_EVENTS_JS, [_SCENE_ESM, state, widget._viewer_page.html_gz]
        )
        browser.close()
    assert width == '123px'
    assert handlers == 0


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
    output: queue.Queue[str] = queue.Queue()

    def drain():
        """Forward every output line so the pipe never fills."""
        for line in proc.stdout:
            output.put(line)

    Thread(target=drain, daemon=True).start()
    lines: list[str] = []
    url = None
    deadline = time.monotonic() + 90
    try:
        while url is None and time.monotonic() < deadline:
            try:
                line = output.get(timeout=1)
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue
            lines.append(line)
            if line.startswith('URL '):
                url = line.split()[1]
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


def _open_drawn_session(browser, url):
    """Open ``url`` in a new browser context and assert all three plots draw."""
    page = browser.new_context(viewport={'width': 1200, 'height': 1400}).new_page()
    page.goto(url)
    page.locator('iframe.pyvista').nth(2).wait_for(timeout=90000)
    assert _drawn_plots(page) == [True, True, True]
    return page


@pytest.mark.needs_playwright
def test_marimo_run_sessions_keep_their_plots(marimo_run_url) -> None:
    """Open two ``marimo run`` sessions, close one, then reload the other and open a third."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        first = _open_drawn_session(browser, marimo_run_url)
        second = _open_drawn_session(browser, marimo_run_url)
        first.context.close()
        second.wait_for_timeout(4000)

        second.reload()
        second.locator('iframe.pyvista').nth(2).wait_for(timeout=60000)
        assert _drawn_plots(second) == [True, True, True]
        _open_drawn_session(browser, marimo_run_url)
        browser.close()
