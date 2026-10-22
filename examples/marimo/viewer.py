from __future__ import annotations

import marimo

__generated_with = '0.25.2'
app = marimo.App(width='full')


@app.cell
def _():
    import pyvista as pv

    from trame_pyvista.anywidget import from_plotter

    return from_plotter, pv


@app.cell
def _(from_plotter, pv):
    pl = pv.Plotter()
    pl.add_mesh(pv.Sphere())
    from_plotter(pl, height=320)


if __name__ == '__main__':
    app.run()
