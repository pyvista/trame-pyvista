import marimo

__generated_with = '0.25.2'
app = marimo.App(width='full')


@app.cell
def _():
    import pyvista as pv

    return (pv,)


@app.cell
def _(pv):
    pl = pv.Plotter()
    pl.add_mesh(pv.Sphere())
    pl.trame.show(mode='html', height='320px')


if __name__ == '__main__':
    app.run()
