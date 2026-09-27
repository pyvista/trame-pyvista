"""Tests for the VTK.wasm views, the plotter toolbar and the ready-made apps."""

from __future__ import annotations

import asyncio
import io
import json
import zipfile

import pytest
import pyvista as pv
from trame_vtklocal.module import wasm
from trame_vtklocal.utils import exporter

from trame_pyvista import apps
from trame_pyvista import widgets
from trame_pyvista.apps import InvalidApplicationNameError
from trame_pyvista.apps import SimpleViewer
from trame_pyvista.apps import create_application
from trame_pyvista.jupyter import elegantly_launch
from trame_pyvista.ui import get_viewer
from trame_pyvista.ui import plotter_ui
from trame_pyvista.vue3_widgets import get_plotter_state
from trame_pyvista.widgets import PyVistaRCAView
from trame_pyvista.widgets import PyVistaWasmView
from trame_pyvista.widgets import get_server

pytestmark = pytest.mark.skipif(
    not widgets.IS_WASM_SUPPORTED, reason='VTK.wasm views need VTK >= 9.7'
)


def _wazex_ids(data):
    """Return the root object ids listed in a ``wazex`` archive."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return json.loads(archive.read('vtk-wasm.json'))['ids']


def _run(func):
    """Call ``func`` from a coroutine so throttled view renders find a running loop."""

    async def main():
        """Call ``func`` and let scheduled renders run."""
        result = func()
        await asyncio.sleep(0)
        return result

    return asyncio.get_event_loop().run_until_complete(main())


@pytest.fixture(params=['vue2', 'vue3'])
def server(request):
    """Return a launched trame server for the given client type."""
    name = f'wasm-tests-{request.param}'
    elegantly_launch(name, client_type=request.param)
    return get_server(name=name)


@pytest.fixture
def vue3_server():
    """Return a launched vue3 trame server."""
    elegantly_launch('wasm-tests-vue3', client_type='vue3')
    return get_server(name='wasm-tests-vue3')


@pytest.fixture(scope='session')
def wasm_bundle():
    """Download and unpack the VTK.wasm bundle once and return its archive path."""
    return exporter.find_wasm('wasm32')


@pytest.fixture
def plotter():
    """Return a notebook plotter showing a sphere."""
    pl = pv.Plotter(notebook=True)
    pl.add_mesh(pv.Sphere())
    return pl


@pytest.fixture
def viewer(plotter, vue3_server):
    """Return a SimpleViewer in local rendering mode."""
    return _run(lambda: SimpleViewer(plotter, vue3_server))


def test_create_application(plotter, vue3_server):
    app = _run(lambda: create_application(None, vue3_server, plotter))
    assert isinstance(app, SimpleViewer)
    assert app.plotter is plotter
    with pytest.raises(InvalidApplicationNameError, match=r'application name \(unknown\)'):
        create_application('unknown', vue3_server, plotter)


def test_component_app(plotter):
    elegantly_launch(pv.global_theme.trame.jupyter_server_name, client_type='vue3')
    app = _run(plotter.trame.app)
    assert isinstance(app, SimpleViewer)
    assert app.plotter is plotter


def test_simple_viewer_switches_rendering_mode(viewer, monkeypatch):
    state = viewer.controls._state
    updates = []
    monkeypatch.setattr(viewer.view_wasm, 'update', lambda **kwargs: updates.append(kwargs))
    assert viewer.state[viewer.RENDERING_MODE] == 'local'
    assert viewer.active_view is viewer.view_wasm
    assert not state.is_remote

    _run(viewer.use_remote_rendering)
    assert viewer.state[viewer.RENDERING_MODE] == 'remote'
    assert viewer.active_view is viewer.view_rca
    assert state.is_remote

    _run(viewer._toggle_rendering_mode)
    assert viewer.state[viewer.RENDERING_MODE] == 'local'
    assert viewer.active_view is viewer.view_wasm
    assert not state.is_remote
    assert updates == [{'push_camera': True}]

    _run(viewer._toggle_rendering_mode)
    assert viewer.active_view is viewer.view_rca


@pytest.mark.parametrize('mode', ['local', 'remote'])
def test_simple_viewer_delegates_to_active_view(viewer, mode, monkeypatch):
    _run(viewer.use_local_rendering if mode == 'local' else viewer.use_remote_rendering)
    calls = []
    for name in ('render', 'reset_camera', '_update_camera', '_export_screenshot'):
        monkeypatch.setattr(
            viewer.active_view, name, lambda *args, _name=name: calls.append((_name, args))
        )
    viewer.render()
    viewer.reset_camera()
    viewer._update_camera()
    viewer._export_screenshot('shot.png')
    assert calls == [
        ('render', ()),
        ('reset_camera', ()),
        ('_update_camera', ()),
        ('_export_screenshot', ('shot.png',)),
    ]


def test_simple_viewer_registers_widgets_on_wasm_view(viewer, plotter, monkeypatch):
    registered = []
    monkeypatch.setattr(viewer.view_wasm, 'register_vtk_object', registered.append)
    plotter.show_axes()
    viewer._set_widgets([plotter.renderer.axes_widget])
    assert registered == [plotter.renderer.axes_widget]


def test_simple_viewer_without_wasm(plotter, vue3_server, monkeypatch):
    monkeypatch.setattr(apps, 'IS_WASM_SUPPORTED', False)
    with pytest.warns(UserWarning, match='is too old'):
        app = _run(lambda: SimpleViewer(plotter, vue3_server))
    assert app.view_wasm is None
    assert app.state[app.RENDERING_MODE] == 'remote'
    assert app.controls._state.is_remote
    assert app.active_view is app.view_rca
    app.use_local_rendering()
    assert app.state[app.RENDERING_MODE] == 'remote'
    app._set_widgets([])


def test_simple_viewers_keep_their_own_rendering_mode(vue3_server):
    first = _run(lambda: SimpleViewer(pv.Plotter(notebook=True), vue3_server))
    _run(first.use_remote_rendering)
    second = _run(lambda: SimpleViewer(pv.Plotter(notebook=True), vue3_server))
    assert second.state[second.RENDERING_MODE] == 'local'
    assert second.active_view is second.view_wasm
    assert first.active_view is first.view_rca


def test_plotter_state_is_shared_per_plotter(plotter, vue3_server):
    state = get_plotter_state(plotter, vue3_server)
    assert get_plotter_state(plotter, vue3_server) is state
    assert get_plotter_state(pv.Plotter(notebook=True), vue3_server) is not state


def test_plotter_state_reads_plotter(vue3_server):
    pl = pv.Plotter(notebook=True)
    pl.add_mesh(pv.Sphere(), show_edges=True)
    pl.enable_parallel_projection()
    pl.show_bounds()
    pl.add_bounding_box()
    pl.show_axes()
    state = get_plotter_state(pl, vue3_server)
    assert state.show_edges
    assert state.use_parallel_projection
    assert state.show_axis_grid
    assert state.show_bounding_box
    assert state.show_orientation_axis
    assert pl.renderer.cube_axes_actor is not None
    assert pl.renderer.axes_widget is not None


def test_plotter_state_defaults(plotter, vue3_server):
    state = get_plotter_state(plotter, vue3_server)
    assert not state.show_edges
    assert not state.use_parallel_projection
    assert not state.show_axis_grid
    assert not state.show_bounding_box
    assert not state.show_orientation_axis


def test_plotter_state_tracks_widgets(plotter, vue3_server):
    state = get_plotter_state(plotter, vue3_server)
    assert plotter.iren.interactor.GetTrackInteractorObserverInstances()
    assert not state.need_register_widgets


def test_toolbar_axes_reach_the_wasm_scene(viewer, plotter):
    state = viewer.controls._state
    assert not state.need_register_widgets
    _run(lambda: setattr(state, 'show_orientation_axis', True))
    manager = viewer.view_wasm.api.vtk_object_manager
    root = viewer.view_wasm.get_wasm_id(plotter.render_window)
    assert manager.GetId(plotter.renderer.axes_widget) in manager.GetAllDependencies(root)


def test_plotter_state_registers_widgets_without_tracking(viewer, plotter, monkeypatch):
    state = viewer.controls._state
    with monkeypatch.context() as m:
        m.setattr(plotter, 'iren', None)
        state.update_from_plotter()
    assert state.need_register_widgets

    registered = []
    monkeypatch.setattr(viewer.view_wasm, 'register_vtk_object', registered.append)
    _run(lambda: setattr(state, 'show_orientation_axis', True))
    assert registered == [plotter.renderer.axes_widget]


def test_plotter_state_drives_plotter(viewer, plotter, monkeypatch):
    state = viewer.controls._state
    renders = []
    monkeypatch.setattr(viewer, 'render', lambda: renders.append(1))
    actor = next(iter(plotter.actors.values()))

    state.show_edges = True
    assert actor.prop.show_edges
    state.show_edges = False
    assert not actor.prop.show_edges

    state.use_parallel_projection = True
    assert plotter.renderer.parallel_projection
    state.use_parallel_projection = False
    assert not plotter.renderer.parallel_projection

    state.show_bounding_box = True
    assert any(key.startswith('BoundingBox') for key in plotter.actors)
    state.show_bounding_box = False
    assert not any(key.startswith('BoundingBox') for key in plotter.actors)

    state.show_axis_grid = True
    assert plotter.renderer.cube_axes_actor is not None
    state.show_axis_grid = False
    assert plotter.renderer.cube_axes_actor is None

    state.show_orientation_axis = True
    assert plotter.renderer.axes_widget.GetEnabled()
    state.show_orientation_axis = False
    assert not plotter.renderer.axes_widget.GetEnabled()

    assert len(renders) == 10


def test_plotter_state_suspends_rendering(viewer, monkeypatch):
    state = viewer.controls._state
    calls = []
    monkeypatch.setattr(viewer, 'render', lambda: calls.append('render'))
    monkeypatch.setattr(viewer, 'reset_camera', lambda: calls.append('reset_camera'))
    state.skip_render = True
    state.render()
    state.reset_camera()
    assert calls == []
    state.skip_render = False
    state.render()
    state.reset_camera()
    assert calls == ['render', 'reset_camera']


def test_plotter_state_without_view(plotter, vue3_server):
    state = get_plotter_state(plotter, vue3_server)
    assert state.view is None
    state.render()
    state.reset_camera()
    state.register_widgets([])


@pytest.mark.parametrize(
    'field',
    [
        'show_edges',
        'show_bounding_box',
        'show_axis_grid',
        'show_orientation_axis',
        'use_parallel_projection',
    ],
)
def test_plotter_state_without_plotter(plotter, vue3_server, field, monkeypatch):
    state = get_plotter_state(plotter, vue3_server)
    monkeypatch.setattr(state, '_plotter', lambda: None)
    assert state.plotter is None
    state.update_from_plotter()
    setattr(state, field, True)
    assert not next(iter(plotter.actors.values())).prop.show_edges
    assert not any(key.startswith('BoundingBox') for key in plotter.actors)
    assert plotter.renderer.cube_axes_actor is None
    assert plotter.renderer.axes_widget is None
    assert not plotter.renderer.parallel_projection


def test_controls_move_the_camera(viewer, plotter, monkeypatch):
    controls = viewer.controls
    assert controls.view is viewer
    assert controls.plotter is plotter
    updates = []
    monkeypatch.setattr(viewer, '_update_camera', lambda: updates.append(1))
    monkeypatch.setattr(viewer, 'reset_camera', lambda: updates.append('reset'))

    controls.view_xy()
    assert plotter.camera_position.viewup == (0.0, 1.0, 0.0)
    assert plotter.camera.direction == pytest.approx((0.0, 0.0, -1.0))
    controls.view_xz()
    assert plotter.camera.direction == pytest.approx((0.0, 1.0, 0.0))
    controls.view_yz()
    assert plotter.camera.direction == pytest.approx((-1.0, 0.0, 0.0))
    controls.view_isometric()
    assert plotter.camera.direction == pytest.approx(
        (-(3**-0.5), -(3**-0.5), -(3**-0.5)), abs=1e-6
    )
    controls.reset_camera()
    assert updates == [1, 1, 1, 1, 'reset']


def test_controls_without_plotter(viewer, plotter, monkeypatch):
    controls = viewer.controls
    monkeypatch.setattr(controls._state, '_plotter', lambda: None)
    before = plotter.camera_position
    for method in (
        controls.view_xy,
        controls.view_xz,
        controls.view_yz,
        controls.view_isometric,
    ):
        method()
    assert plotter.camera_position == before


@pytest.mark.usefixtures('wasm_bundle')
def test_controls_download_scene(viewer):
    controls = viewer.controls
    assert controls.download_scene()[:2] == b'PK'
    assert b'<html' in controls.download_view3d()[:1000].lower()


def test_controls_download_screenshot(viewer):
    _run(viewer.use_remote_rendering)
    assert viewer.controls.download_screenshot()[:8] == b'\x89PNG\r\n\x1a\n'


def test_wasm_view_requires_vtk_97(plotter, vue3_server, monkeypatch):
    monkeypatch.setattr(widgets, 'IS_WASM_SUPPORTED', False)
    with pytest.raises(pv.VTKVersionError, match='is too old'):
        PyVistaWasmView(plotter, trame_server=vue3_server)


def test_wasm_view_rejects_closed_plotter(plotter, vue3_server):
    plotter.close()
    with pytest.raises(RuntimeError, match='render window for this plotter has been destroyed'):
        PyVistaWasmView(plotter, trame_server=vue3_server)


def test_wasm_view(plotter, vue3_server, monkeypatch):
    plotter.show_axes()
    view = _run(lambda: PyVistaWasmView(plotter, trame_server=vue3_server))
    assert view.get_wasm_id(plotter.renderer.axes_widget)

    registered = []
    monkeypatch.setattr(view, 'register_vtk_object', registered.append)
    view._set_widgets(None)
    assert registered == []

    pushes = []
    monkeypatch.setattr(view, 'update', lambda **kwargs: pushes.append(kwargs))
    view.update_camera()
    view.push_camera()
    assert pushes == [{'push_camera': True}, {'push_camera': True}]

    renders = []
    monkeypatch.setattr(
        PyVistaWasmView, 'update_throttle', property(lambda _: lambda: renders.append(1))
    )
    view.update_image()
    view.render()
    assert renders == [1, 1]


@pytest.mark.parametrize(
    ('filename', 'mime'),
    [
        ('shot.png', 'image/png'),
        ('shot.jpg', 'image/jpeg'),
        ('shot.jpeg', 'image/jpeg'),
        ('shot', 'image/png'),
    ],
)
def test_wasm_view_screenshot_format(plotter, vue3_server, filename, mime, monkeypatch):
    view = _run(lambda: PyVistaWasmView(plotter, trame_server=vue3_server))
    screenshots = []
    monkeypatch.setattr(view, 'download_screenshot', lambda *args: screenshots.append(args))
    view._export_screenshot(filename)
    assert screenshots == [(filename, mime)]


def test_wasm_view_syncs_camera_from_client(plotter, vue3_server, monkeypatch):
    view = _run(lambda: PyVistaWasmView(plotter, trame_server=vue3_server))
    states = []
    monkeypatch.setattr(view, 'vtk_update_from_state', states.append)
    view._sync_camera([{'Id': 1}, {'Id': 2}])
    assert states == [{'Id': 1}, {'Id': 2}]


@pytest.mark.usefixtures('wasm_bundle')
def test_wasm_view_exports(plotter, vue3_server):
    view = _run(lambda: PyVistaWasmView(plotter, trame_server=vue3_server))
    without_axes = _wazex_ids(view._export_data())
    plotter.show_axes()
    assert len(_wazex_ids(view._export_data())) == len(without_axes) + 1
    html = view._export_html(mode='wasm32', rendering='webgpu').decode()
    assert '"mode": "wasm32", "rendering": "webgpu"' in html


def test_rca_view(plotter, vue3_server, monkeypatch):
    view = PyVistaRCAView(plotter, trame_server=vue3_server, target_fps=30)
    assert view.target_fps == 30
    view.target_fps = 10
    assert view.target_fps == 10

    updates = []
    monkeypatch.setattr(view.handler, 'update', lambda: updates.append(1))
    plotter.camera.zoom(3)
    before = plotter.camera_position
    view.reset_camera()
    assert plotter.camera_position != before
    view._update_camera()
    assert updates == [1, 1]
    assert view._export_screenshot('shot.png')[:8] == b'\x89PNG\r\n\x1a\n'


def test_plotter_ui_wasm_mode(plotter, server):
    view = _run(lambda: plotter_ui(plotter, mode='wasm', server=server))
    assert isinstance(view, PyVistaWasmView)


def test_axis_visibility_syncs_wasm_view_widgets(plotter, vue3_server, monkeypatch):
    view = _run(lambda: plotter_ui(plotter, mode='wasm', server=vue3_server))
    registered = []
    monkeypatch.setattr(view, 'register_vtk_object', registered.append)
    viewer = get_viewer(plotter)
    _run(lambda: viewer.on_axis_visibility_change(**{viewer.AXIS: True}))
    assert registered == [plotter.renderer.axes_widget]


def test_component_export_wazex(plotter, tmp_path):
    without_axes = _wazex_ids(plotter.trame.export_wazex(None))
    plotter.show_axes()
    assert len(_wazex_ids(plotter.trame.export_wazex(None))) == len(without_axes) + 1
    path = plotter.trame.export_wazex(tmp_path / 'scene.wazex')
    assert _wazex_ids(path.read_bytes()) == _wazex_ids(plotter.trame.export_wazex(None))


def test_component_export_wasm_html(plotter, wasm_bundle, tmp_path, monkeypatch):
    html = plotter.trame.export_wasm_html(None).decode()
    assert '"mode": "wasm32", "rendering": "webgl"' in html
    monkeypatch.setattr(exporter, 'find_wasm', lambda wasm_bits: wasm_bundle)
    path = plotter.trame.export_wasm_html(tmp_path / 'scene.html', 'wasm64', 'webgpu')
    assert '"mode": "wasm64", "rendering": "webgpu"' in path.read_text()


def test_wasm_bundle_extraction(plotter, wasm_bundle, tmp_path, monkeypatch):
    wasm_version, _ = wasm.get_wasm_info()
    monkeypatch.setattr(exporter, 'SERVE_PATH', tmp_path)
    monkeypatch.setattr(wasm, 'get_wasm_info', lambda wasm_bits: (wasm_version, wasm_bundle))
    html = plotter.trame.export_wasm_html(None)
    assert b'<html' in html[:1000].lower()
    assert (tmp_path / 'wasm32' / wasm_version / 'vtkWebAssembly.wasm').is_file()
