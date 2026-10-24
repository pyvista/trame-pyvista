// Anywidget frontend for trame-pyvista.
//
// Renders a base64-encoded trame/vtk.js scene snapshot (produced by
// ``plotter.trame.export_vtksz``) inside the widget element using the
// OfflineLocalView bundle from trame-vtk. The Python side concatenates
// that bundle onto this file, so this module is self contained and
// needs no network access or running server.

const trame_pyvista_widget = (() => {
  const defaultHeight = 450;

  function heightCss(model) {
    const height = model.get('height');
    return `${Number(height) || defaultHeight}px`;
  }

  // The bundle exposes a render window collection at
  // ``window.global.renderWindow``; each contained view has ``setSize``.
  function resizeArea(width, height) {
    const g = typeof window !== 'undefined' && window.global;
    const rw = g && g.renderWindow;
    if (!rw || !rw.getViews) {
      return;
    }
    for (const view of rw.getViews()) {
      if (view && typeof view.setSize === 'function') {
        view.setSize(width, height);
      }
    }
  }

  function render({ model, el, signal }) {
    el.style.width = '100%';
    el.style.height = heightCss(model);
    el.style.position = 'relative';
    el.style.overflow = 'hidden';

    const load = (base64Str) => {
      // A previous scene's canvas would linger otherwise.
      el.innerHTML = '';
      window.OfflineLocalView.load(el, { base64Str });
    };

    if (model.get('data')) {
      load(model.get('data'));
    }

    const context = {};
    const onData = () => {
      const data = model.get('data');
      if (data) {
        load(data);
      }
    };
    const onHeight = () => {
      el.style.height = heightCss(model);
      resizeArea(el.clientWidth || 640, el.clientHeight || defaultHeight);
    };
    model.on('change:data', onData, context);
    model.on('change:height', onHeight, context);

    // Keep the vtk.js views sized to the element.
    const resize = () => {
      resizeArea(el.clientWidth || 640, el.clientHeight || defaultHeight);
    };
    let observer = null;
    if (typeof ResizeObserver === 'function') {
      observer = new ResizeObserver(resize);
      observer.observe(el);
    }

    const cleanup = () => {
      model.off(null, null, context);
      if (observer) {
        observer.disconnect();
      }
      el.innerHTML = '';
    };
    signal.addEventListener('abort', cleanup);
    return cleanup;
  }

  return { render };
})();

export default trame_pyvista_widget;
