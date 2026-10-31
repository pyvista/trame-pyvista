"""Notebook with two html plots and one client plot, served by marimo in the browser tests."""

import marimo

__generated_with = '0.25.2'
app = marimo.App()


@app.cell
def _():
    import pyvista as pv

    return (pv,)


@app.cell
def _(pv):
    sphere = pv.Plotter()
    sphere.add_mesh(pv.Sphere())
    sphere.trame.show(mode='html', height='200px')


@app.cell
def _(pv):
    cube = pv.Plotter()
    cube.add_mesh(pv.Cube())
    cube.trame.show(mode='html', height='200px')


@app.cell
def _(pv):
    cone = pv.Plotter()
    cone.add_mesh(pv.Cone())
    cone.trame.show(mode='client', height='200px')


if __name__ == '__main__':
    app.run()
