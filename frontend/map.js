/* Base-map loading and container sizing are independent of account/sign data. */
(function (root) {
  'use strict';

  function mount({ L, document, environment = root, idPrefix = '' }) {
    const $ = id => document.getElementById(idPrefix + id);
    const notice = $('map-notice'), message = $('map-message');
    const retry = $('map-retry'), home = $('map-home');
    const sourceControl = $('map-source');
    const map = L.map(idPrefix + 'map').setView([10.7769, 106.7009], 15);
    const attribution = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>';
    const sources = [
      {id:'osm',url:'https://tile.openstreetmap.org/{z}/{x}/{y}.png',attribution},
      {id:'osm-de',url:'https://tile.openstreetmap.de/{z}/{x}/{y}.png',
        attribution:attribution+' · Tiles © <a href="https://tile.openstreetmap.de/">FOSSGIS</a>'}
    ];
    const sourceKey = 'signsight.map-source';
    function savedSource() {
      try {
        const saved = JSON.parse(environment.localStorage?.getItem(sourceKey) || 'null');
        const age = Date.now() - saved?.savedAt;
        if (Number.isFinite(age) && age >= 0 && age < 24*60*60*1000) {
          const index = sources.findIndex(source => source.id === saved.id);
          if (index >= 0) return index;
        }
      } catch (_) { /* Storage may be disabled on the device. */ }
      return 0;
    }
    function rememberSource(index) {
      try { environment.localStorage?.setItem(sourceKey, JSON.stringify({id:sources[index].id,savedAt:Date.now()})); }
      catch (_) { /* The map still works without preferences. */ }
    }
    let tiles = null, sourceIndex = 0, automaticSwitchUsed = false, loadedCount = 0;
    const failedTiles = new Set();
    let timer = null, frame = null, disposed = false, loading = false;
    function show(text) { message.textContent = text; notice.hidden = false; }
    function clearTimer() {
      if (timer !== null) environment.clearTimeout(timer);
      timer = null;
    }
    function showFailures() {
      if (failedTiles.size) show('Không tải được nền bản đồ. Kiểm tra kết nối mạng rồi thử lại.');
      else notice.hidden = true;
    }
    function fallback() {
      if (automaticSwitchUsed) return false;
      automaticSwitchUsed = true;
      changeSource(sourceIndex === 0 ? 1 : 0);
      return true;
    }
    function changeSource(index) {
      clearTimer();
      if (tiles) { tiles.off(); map.removeLayer(tiles); }
      failedTiles.clear(); loadedCount = 0; loading = false;
      sourceIndex = index; sourceControl.value = sources[index].id;
      show('Đang tải nền bản đồ…');
      const layer = L.tileLayer(sources[index].url, {
        maxZoom:19, referrerPolicy:'strict-origin-when-cross-origin', attribution:sources[index].attribution
      });
      tiles = layer;
      const current = fn => event => { if (!disposed && tiles === layer) fn(event); };
      layer.on('loading', current(() => {
        loading = true;
        loadedCount = 0;
        clearTimer();
        timer = environment.setTimeout(() => {
          timer = null;
          if (!disposed && tiles === layer && !fallback()) show('Nền bản đồ tải chậm. Thử đổi nguồn bản đồ hoặc kiểm tra kết nối mạng.');
        }, 10000);
      }));
      layer.on('tileerror', current(event => { failedTiles.add(event.tile); showFailures(); }));
      function forgetTile(event) {
        failedTiles.delete(event.tile);
        if (!loading) showFailures();
      }
      layer.on('tileload', current(event => { loadedCount++; forgetTile(event); }));
      layer.on('tileunload', current(forgetTile));
      layer.on('tileabort', current(forgetTile));
      layer.on('load', current(() => {
        loading = false; clearTimer();
        if (failedTiles.size && !loadedCount && fallback()) return;
        if (loadedCount) rememberSource(sourceIndex);
        showFailures();
      }));
      layer.addTo(map);
    }
    sourceControl.onchange = () => {
      const index = sources.findIndex(source => source.id === sourceControl.value);
      if (index < 0 || index === sourceIndex) return;
      automaticSwitchUsed = true;
      rememberSource(index);
      changeSource(index);
    };
    retry.onclick = () => {
      failedTiles.clear();
      show('Đang tải lại nền bản đồ…');
      tiles.redraw();
    };
    home.onclick = () => map.setView([10.7769, 106.7009], 15);

    // Leaflet tracks window resize, but VS Code panels/flex layout can resize alone.
    const container = map.getContainer();
    function resize() {
      if (disposed || frame !== null) return;
      frame = environment.requestAnimationFrame(() => {
        frame = null;
        if (!disposed && container.clientWidth > 0 && container.clientHeight > 0) {
          map.invalidateSize({ pan: false, debounceMoveend: true });
        }
      });
    }
    const observer = environment.ResizeObserver ? new environment.ResizeObserver(resize) : null;
    if (observer) observer.observe(container);
    map.on('unload', () => {
      disposed = true;
      if (observer) observer.disconnect();
      if (frame !== null) environment.cancelAnimationFrame(frame);
      clearTimer();
      tiles.off();
      failedTiles.clear();
      retry.onclick = null;
      home.onclick = null;
      sourceControl.onchange = null;
    });
    changeSource(savedSource());
    resize();
    return { map };
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = { mount };
  else root.signSightMap = { mount };
})(typeof window === 'undefined' ? globalThis : window);
