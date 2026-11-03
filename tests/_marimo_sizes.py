"""Notebook with one default-size and two explicit-size plots, for the browser tests."""

import marimo

__generated_with = '0.25.2'
app = marimo.App()


@app.cell
def _():
    import pyvista as pv

    return (pv,)


@app.cell
def _(pv):
    _pl = pv.Plotter()
    _pl.add_mesh(pv.Sphere())
    _pl.trame.show(mode='html')


@app.cell
def _(pv):
    _pl = pv.Plotter(window_size=[400, 300])
    _pl.add_mesh(pv.Sphere())
    _pl.trame.show(mode='html')


@app.cell
def _(pv):
    _pl = pv.Plotter(window_size=[300, 700])
    _pl.add_mesh(pv.Sphere())
    _pl.trame.show(mode='html')


if __name__ == '__main__':
    app.run()
