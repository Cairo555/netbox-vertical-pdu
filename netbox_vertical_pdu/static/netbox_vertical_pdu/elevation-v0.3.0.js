/* Delegate to live SVG nodes: NetBox loads its native rack through HTMX. */
(() => {
  if (window.netboxVerticalPduHoverInitialized) return;
  window.netboxVerticalPduHoverInitialized = true;
  let pointerSource = null;
  let focusSource = null;
  let activeScene = null;
  let activeSource = null;

  function sourceFor(node) {
    if (!(node instanceof Element)) return null;
    const source = node.closest('.vpdu-outlet, .vpdu-connection, .vpdu-native a');
    return source?.closest('.vpdu-scene') ? source : null;
  }

  function pathFor(link) {
    const href = link.getAttribute('href') || link.getAttributeNS('http://www.w3.org/1999/xlink', 'href');
    return href ? new URL(href, document.baseURI).pathname : '';
  }

  function clear(scene) {
    if (!scene) return;
    scene.classList.remove('vpdu-has-highlight');
    scene.querySelectorAll('.vpdu-highlight').forEach(el => el.classList.remove('vpdu-highlight'));
    scene.querySelectorAll('.vpdu-highlight-overlay').forEach(el => el.remove());
  }

  function sync(force = false) {
    if (!pointerSource?.isConnected) pointerSource = null;
    if (!focusSource?.isConnected) focusSource = null;
    const source = pointerSource || focusSource;
    if (!force && source === activeSource) return;
    clear(activeScene);
    activeSource = source;
    activeScene = source?.closest('.vpdu-scene') || null;
    if (!activeScene) return;

    const lines = [...activeScene.querySelectorAll('.vpdu-connection')];
    let selected;
    if (source.matches('.vpdu-outlet')) {
      selected = lines.filter(line => line.dataset.outletId === source.dataset.outletId);
    } else if (source.matches('.vpdu-connection')) {
      selected = [source];
    } else {
      const path = pathFor(source);
      selected = lines.filter(line => line.dataset.deviceUrl === path);
    }
    if (!selected.length) return;

    activeScene.classList.add('vpdu-has-highlight');
    const outletIds = new Set(selected.map(line => line.dataset.outletId));
    const devicePaths = new Set(selected.map(line => line.dataset.deviceUrl));
    activeScene.querySelectorAll('.vpdu-outlet').forEach(outlet => {
      outlet.classList.toggle('vpdu-highlight', outletIds.has(outlet.dataset.outletId));
    });
    activeScene.querySelectorAll('.vpdu-native a').forEach(device => {
      device.classList.toggle('vpdu-highlight', devicePaths.has(pathFor(device)));
    });

    // Paint a non-interactive copy last, above all crossing/shared segments.
    // Keep original anchors in place so hover, keyboard focus and clicks remain stable.
    const overlay = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    overlay.setAttribute('class', 'vpdu-highlight-overlay');
    overlay.setAttribute('aria-hidden', 'true');
    selected.forEach(line => {
      line.classList.add('vpdu-highlight');
      line.querySelectorAll('path, circle').forEach(shape => {
        const copy = shape.cloneNode(true);
        copy.removeAttribute('id');
        overlay.appendChild(copy);
      });
    });
    activeScene.querySelector('.vpdu-connections').appendChild(overlay);
  }

  document.addEventListener('pointerover', event => { pointerSource = sourceFor(event.target); sync(); });
  document.addEventListener('pointerout', event => { pointerSource = sourceFor(event.relatedTarget); sync(); });
  document.addEventListener('focusin', event => { focusSource = sourceFor(event.target); sync(); });
  document.addEventListener('focusout', event => { focusSource = sourceFor(event.relatedTarget); sync(); });
  document.addEventListener('htmx:afterSwap', () => sync(true));
})();
