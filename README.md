# trame-pyvista

[Trame][trame] interface for [PyVista][pyvista]: web-based 3D viewers,
Jupyter backends, scene exporters, and a Sphinx directive for embedded
interactive plots.

This package was extracted from the `pyvista.trame` subpackage so the
trame stack can evolve on its own release cadence and dependency
window. PyVista re-exposes installed functionality through entry
points; user code mostly does not need to change.

[trame]: https://kitware.github.io/trame/
[pyvista]: https://pyvista.org

## Install

```bash
pip install trame-pyvista
```

For Jupyter:

```bash
pip install "trame-pyvista[jupyter]"
```

## What you get

- **Jupyter backends** — `trame`, `server`, `client`, `html`. Registered
  with PyVista via the `pyvista.jupyter_backends` entry-point group, so
  `pv.set_jupyter_backend('trame')` works once `trame-pyvista` is
  installed.
- **Plotter views** — `PyVistaLocalView`, `PyVistaRemoteView`,
  `PyVistaRemoteLocalView` for embedding in trame apps.
- **`plotter.trame` namespace** — registered as a PyVista plotter
  component so exporters live under the trame namespace:

  ```python
  import pyvista as pv

  pl = pv.Plotter()
  pl.add_mesh(pv.Sphere())
  pl.trame.export_vtksz('scene.vtksz')
  pl.trame.export_html('scene.html')
  ```

- **Sphinx directive** — `trame_pyvista.sphinx_ext` provides the
  `offlineviewer` directive used by PyVista docs to embed exported
  `.vtksz` scenes. Add to `conf.py`:

  ```python
  extensions = ['trame_pyvista.sphinx_ext']
  ```

## Usage

```python
import pyvista as pv

pv.set_jupyter_backend('trame')
pl = pv.Plotter()
pl.add_mesh(pv.Wavelet())
pl.show()
```

Custom UI:

```python
from trame_pyvista import plotter_ui

ui = plotter_ui(plotter, mode='trame')
```

See `examples/` for runnable scripts covering local/remote views, custom
UIs, and toolbar customization.

## Development

Uses [`uv`][uv] and [`just`][just]:

```bash
just sync         # create venv and install dev deps
just test         # unit tests
just test-playwright  # Sphinx + browser integration tests
just lint         # pre-commit (ruff, etc.)
just typecheck
just build
```

[uv]: https://docs.astral.sh/uv/
[just]: https://just.systems/

## License

MIT — see [LICENSE](LICENSE).
