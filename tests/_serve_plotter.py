"""Serve plotters through the Jupyter code path and print their iframe URLs."""

from __future__ import annotations

import argparse
import asyncio

import pyvista as pv

from trame_pyvista.jupyter import build_url
from trame_pyvista.jupyter import initialize
from trame_pyvista.jupyter import launch_server
from trame_pyvista.widgets import get_server

pv.OFF_SCREEN = True


def _build_plotter() -> pv.Plotter:
    """Return a two-subplot scene with a sphere and a cube."""
    pl = pv.Plotter(notebook=True, shape=(1, 2), window_size=(600, 300))
    pl.subplot(0, 0)
    pl.add_mesh(pv.Sphere(), color='tomato', show_edges=True)
    pl.subplot(0, 1)
    pl.add_mesh(pv.Cube(), color='steelblue')
    pl.link_views()
    return pl


def _build_tight_scene(*, show_edges: bool) -> pv.Plotter:
    """Return a sphere and a cube in an isometric view with a tight parallel camera."""
    pl = pv.Plotter(notebook=True, window_size=(400, 300))
    pl.add_mesh(pv.Sphere(center=(-0.6, 0, 0)), color='tomato', show_edges=show_edges)
    pl.add_mesh(pv.Cube(center=(0.6, 0, 0)), color='steelblue', show_edges=show_edges)
    pl.view_isometric()
    pl.camera.tight()
    return pl


SCENES = {
    'subplots': _build_plotter,
    'tight': lambda: _build_tight_scene(show_edges=False),
    'tight-edges': lambda: _build_tight_scene(show_edges=True),
}


async def _main(client_type: str, mode: str, port: int, scene: str, count: int) -> None:
    """Launch the server, build the UI, print the URLs and serve forever."""
    server = get_server(f'serve-{client_type}-{mode}', client_type=client_type)
    launch_server(server, port=port)
    await server.ready
    plotters = [SCENES[scene]() for _ in range(count)]
    for pl in plotters:
        initialize(server, pl, mode=mode)
    for pl in plotters:
        print(f'URL {build_url(server, ui=pl._id_name)}', flush=True)
    await asyncio.Event().wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--client-type', choices=['vue2', 'vue3'], required=True)
    parser.add_argument('--mode', choices=['trame', 'server', 'client'], required=True)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--scene', choices=list(SCENES), default='subplots')
    parser.add_argument('--count', type=int, default=1, help='number of plotters to serve')
    args, _ = parser.parse_known_args()
    asyncio.run(_main(args.client_type, args.mode, args.port, args.scene, args.count))
