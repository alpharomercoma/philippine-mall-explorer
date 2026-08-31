/* Map view.
 *
 * This module knows about points, pixels and tiles. It knows nothing about
 * brands, operators or filters: the caller hands it a plain array of points and
 * a function that builds a popup for one, which keeps the data model in app.js
 * and the geometry here.
 *
 * Three decisions worth knowing about:
 *
 * Lazy    Leaflet is 147 KB and most visits never open the map, so the library
 *         and its stylesheet are injected on first use rather than shipped in
 *         the critical path. A phone that only ever reads the list pays nothing.
 * Stable  Clustering projects each point at an explicit zoom, so groups depend
 *         on zoom alone. Panning cannot reshuffle them, which is what makes the
 *         map feel steady rather than alive.
 * Honest  Some properties share a coordinate outright, so no zoom separates
 *         them. Those clusters open as a list instead of pretending a click
 *         will split them. See `separable`.
 * Safe    Every label and popup is built from DOM nodes with textContent. The
 *         page's no-innerHTML rule does not stop at the edge of the map.
 */

const PH_CENTER = [12.6, 122.6];   // roughly the centroid of the archipelago
const PH_ZOOM = 6;
const MAX_ZOOM = 18;
const CLUSTER_CELL = 62;           // px; a cluster owns a square of this size
const R_MIN = 5;
const R_MAX = 17;
const FIT_PADDING = [20, 20];
const FOCUS_ZOOM = 16;             // close enough that one property stands alone

let L = null;
let loading = null;
let map = null;
let markerLayer = null;
let tileLayer = null;
let popupFor = null;
let points = [];
let maxListings = 1;
let tilesFailed = false;
let onTileError = null;
const markerByIndex = new Map();   // only individual points; clusters have no one index
const stackByIndex = new Map();    // every point inside a cluster no zoom can split
let pendingFocus = null;           // a property to open as soon as it has been drawn

/* ---------- lazy library load ---------- */

function injectStylesheet(href) {
  return new Promise((resolve, reject) => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    link.onload = resolve;
    link.onerror = () => reject(new Error(`could not load ${href}`));
    document.head.appendChild(link);
  });
}

function injectScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`could not load ${src}`));
    document.head.appendChild(script);
  });
}

/** Load Leaflet once. Repeat calls share the first promise, including failure,
 *  so a broken deploy reports the same error every time instead of retrying
 *  a fetch that will not succeed. */
function loadLeaflet() {
  if (loading) return loading;
  // Same version marker as the rest of the assets, so a deploy cannot leave a
  // visitor running new code against an old library.
  const v = document.body.dataset.assets;
  const q = v ? `?v=${v}` : '';
  loading = Promise.all([
    injectStylesheet(`vendor/leaflet.css${q}`),
    injectScript(`vendor/leaflet.js${q}`),
  ]).then(() => {
    if (!window.L) throw new Error('the map library loaded but did not initialise');
    L = window.L;
    return L;
  });
  return loading;
}

/* ---------- geometry ---------- */

function cellKey(point, zoom) {
  const pixel = map.project([point.lat, point.lon], zoom);
  return `${Math.floor(pixel.x / CLUSTER_CELL)}:${Math.floor(pixel.y / CLUSTER_CELL)}`;
}

/** Group points into fixed pixel cells at one zoom level.
 *  Projecting at an explicit zoom rather than the current view means the result
 *  is a pure function of (points, zoom): pan does not change it. */
function clusterAt(zoom) {
  const cells = new Map();
  for (const point of points) {
    const key = cellKey(point, zoom);
    const cell = cells.get(key);
    if (cell) cell.push(point);
    else cells.set(key, [point]);
  }
  return [...cells.values()];
}

/** Whether zooming can ever break this group apart.
 *
 *  Closest zoom is the generous test: a group still in one cell there is in one
 *  cell everywhere. Several groups fail it, and none of them is a defect in the
 *  map. Three wings of Lucky Chinatown are one building and the operator
 *  publishes one coordinate for all three. The SMDC strips are only resolved to
 *  their town, so a whole set of them shares its centre. For those, "zoom in to
 *  separate them" is advice that cannot be taken, and a marker that offers it
 *  spends the reader's clicks and gives nothing back. */
function separable(group) {
  const cells = new Set();
  for (const point of group) {
    cells.add(cellKey(point, MAX_ZOOM));
    if (cells.size > 1) return true;
  }
  return false;
}

/** Radius encoding listing count. Area, not radius, carries the value, so the
 *  radius grows with the square root. A circle twice as wide then really does
 *  mean four times as much. */
function radiusFor(listings) {
  const share = maxListings > 0 ? Math.sqrt(Math.max(listings, 0) / maxListings) : 0;
  return R_MIN + (R_MAX - R_MIN) * share;
}

function boundsOf(group) {
  return L.latLngBounds(group.map((p) => [p.lat, p.lon]));
}

/* ---------- drawing ---------- */

function clusterIcon(count, stacked) {
  const node = document.createElement('span');
  node.className = 'cluster-label';
  node.textContent = String(count);
  const size = count >= 100 ? 46 : count >= 25 ? 40 : 34;
  return L.divIcon({
    html: node,                    // an Element, so Leaflet appends rather than parses
    // A stacked cluster answers a click with a list rather than a zoom, so it
    // says so before it is clicked instead of looking identical and behaving
    // differently.
    className: stacked ? 'cluster cluster--stacked' : 'cluster',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

/** Swap what the popup shows, without the click escaping to the map.
 *
 *  Redrawing the popup detaches the button that was clicked, and Leaflet decides
 *  whether a click belongs to the map by walking up from its target. A detached
 *  target has no path back to the popup, so the click reads as a click on the
 *  map and closes the very popup it was meant to navigate. Stopping it here is
 *  what keeps the two views reachable from each other. */
function swapTo(marker, point, event) {
  event.stopPropagation();
  marker.showInStack(point);
}

/** The list behind a stacked cluster, or one member's own popup with a way back.
 *
 *  This module still knows nothing about brands or operators: the rows carry the
 *  name and count every point already has, and the detail is whatever the
 *  caller's builder returns. */
function stackList(group, marker, selected) {
  if (selected) {
    const box = document.createElement('div');
    const back = document.createElement('button');
    back.type = 'button';
    back.className = 'popup-back';
    back.textContent = `Back to all ${group.length} here`;
    back.addEventListener('click', (event) => swapTo(marker, null, event));
    box.append(back, popupFor(selected));
    return box;
  }

  const box = document.createElement('div');
  box.className = 'popup';
  const title = document.createElement('strong');
  // Say which kind of coincidence this is. Sharing a building is a fact about
  // the properties; sharing a town centre is a limit of what we could resolve,
  // and reading one as the other would be misleading.
  title.textContent = group.every((p) => p.approximate)
    ? `${group.length} properties resolved to this locality`
    : `${group.length} properties at this location`;

  const meta = document.createElement('p');
  meta.className = 'popup-meta';
  meta.textContent = 'Zooming cannot separate them. Select one to see it.';

  const list = document.createElement('ul');
  list.className = 'stack';
  for (const point of [...group].sort((a, b) => b.listings - a.listings)) {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'stack-item';
    const name = document.createElement('span');
    name.textContent = point.name;
    const count = document.createElement('span');
    count.className = 'stack-count';
    count.textContent = `${point.listings}`;
    button.append(name, count);
    button.addEventListener('click', (event) => swapTo(marker, point, event));
    item.appendChild(button);
    list.appendChild(item);
  }
  box.append(title, meta, list);
  return box;
}

function drawCluster(group) {
  const stacked = !separable(group);
  const marker = L.marker(boundsOf(group).getCenter(), {
    icon: clusterIcon(group.length, stacked),
    keyboard: true,
    title: stacked
      ? `${group.length} properties in one spot. Select to list them.`
      : `${group.length} properties. Select to zoom in.`,
    alt: `${group.length} properties`,
  });

  if (stacked) {
    // Bound as a function so every open rebuilds from `shown`, which reopening
    // resets. Leaflet re-invokes it on update(), so selecting a row is a
    // content swap in place rather than a second popup.
    let shown = null;
    marker.showInStack = (point) => {
      shown = point;
      if (marker.isPopupOpen()) marker.getPopup().update();
      else marker.openPopup();
    };
    marker.bindPopup(() => stackList(group, marker, shown), {
      maxWidth: 280,
      closeButton: true,
    });
    marker.on('popupclose', () => { shown = null; });
    return marker;
  }

  marker.on('click', () => {
    // Zooming to the group's own bounds is what a reader expects. Points on top
    // of each other never reach here: `separable` sent them to the list above.
    map.fitBounds(boundsOf(group), { padding: FIT_PADDING, maxZoom: MAX_ZOOM });
  });
  return marker;
}

function drawPoint(point) {
  const marker = L.circleMarker([point.lat, point.lon], {
    radius: radiusFor(point.listings),
    className: 'pin' + (point.approximate ? ' pin--approx' : ''),
    // Colour comes from the stylesheet so the two themes stay in one place;
    // Leaflet only needs to be told not to paint its own defaults over it.
    weight: 1.5,
    fillOpacity: 0.75,
  });
  marker.bindPopup(() => popupFor(point), { maxWidth: 280, closeButton: true });
  marker.on('add', () => {
    const element = marker.getElement();
    if (!element) return;
    element.setAttribute('tabindex', '0');
    element.setAttribute('role', 'button');
    element.setAttribute('aria-label', `${point.name}, ${point.listings} listings`);
    element.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        marker.openPopup();
      }
    });
  });
  return marker;
}

function draw() {
  if (!map) return;
  markerLayer.clearLayers();
  markerByIndex.clear();
  stackByIndex.clear();
  const zoom = map.getZoom();
  for (const group of clusterAt(zoom)) {
    if (group.length === 1) {
      const marker = drawPoint(group[0]);
      markerByIndex.set(group[0].index, marker);
      markerLayer.addLayer(marker);
    } else {
      const marker = drawCluster(group);
      // Only stacked clusters are worth remembering: they are the ones a
      // reader can be sent to and find nothing of their own to open.
      if (marker.showInStack) {
        for (const point of group) stackByIndex.set(point.index, marker);
      }
      markerLayer.addLayer(marker);
    }
  }
  applyFocus();
}

/* ---------- public API ---------- */

/** Create the map on first use. Safe to call repeatedly. */
export async function ensure({ container, tiles, attribution, referrerPolicy, onTileFailure }) {
  onTileError = onTileFailure;
  if (map) return map;
  await loadLeaflet();
  if (map) return map;                          // a second caller won the race

  map = L.map(container, {
    center: PH_CENTER,
    zoom: PH_ZOOM,
    minZoom: 5,
    maxZoom: MAX_ZOOM,
    attributionControl: false,   // we render attribution ourselves, as DOM
    worldCopyJump: false,
    zoomControl: true,
    // Integer zoom is too coarse for this country. The archipelago spans 17
    // degrees of latitude, which overflows one whole-number zoom and leaves
    // the next one down showing mostly Vietnam. Quarter steps let the fit
    // land on the level that actually frames it.
    zoomSnap: 0.25,
    zoomDelta: 0.5,
  });
  // Keep the view over the archipelago. Without this a stray drag lands the
  // reader in the empty Pacific with no way back except the reset button.
  map.setMaxBounds(L.latLngBounds([1.0, 112.0], [24.0, 132.0]));

  // referrerPolicy is set on the tile images only. The document sends no
  // referrer at all, which leaves the tile host unable to attribute the
  // request; its usage policy requires either a Referer or an identifying
  // User-Agent, and a browser cannot supply the second. Leaflet applies this
  // before setting src, so it governs the request rather than arriving late.
  tileLayer = L.tileLayer(tiles, {
    maxZoom: MAX_ZOOM,
    attribution: '',
    crossOrigin: false,
    referrerPolicy: referrerPolicy || 'strict-origin-when-cross-origin',
  });
  tileLayer.on('tileerror', () => {
    if (tilesFailed) return;
    tilesFailed = true;
    if (onTileError) onTileError();
  });
  tileLayer.addTo(map);
  markerLayer = L.layerGroup().addTo(map);

  // Recluster on zoom only: pan cannot change the grouping, so redrawing on
  // move would be work with no visible effect.
  map.on('zoomend', draw);
  // A focus that needed no redraw still has to be honoured, and one whose zoom
  // was already correct produces a move and nothing else.
  map.on('moveend', applyFocus);
  void attribution;   // rendered by the caller alongside the other map notes
  return map;
}

/** Replace the plotted set. `fit` re-frames the view, which is right when the
 *  filters changed and wrong when the reader is mid-exploration. */
export function update(nextPoints, { fit = false } = {}) {
  points = nextPoints;
  // A focus is a request against the set that was on screen when it was made.
  // Filters replace that set, so drop it rather than let it open later against
  // a map the reader has since changed.
  pendingFocus = null;
  maxListings = points.reduce((max, p) => Math.max(max, p.listings), 1);
  if (!map) return;
  draw();
  if (fit) fitToPoints();
}

export function setPopupBuilder(builder) {
  popupFor = builder;
}

/** The closest-in zoom needed to leave this point alone in its cell, or null
 *  when no zoom does. Cheap enough to run on a click: a few hundred
 *  projections, and only while the reader waits for a map to move. */
function isolationZoom(point) {
  for (let zoom = FOCUS_ZOOM; zoom <= MAX_ZOOM; zoom += 1) {
    const key = cellKey(point, zoom);
    if (!points.some((other) => other.index !== point.index && cellKey(other, zoom) === key)) {
      return zoom;
    }
  }
  return null;
}

/** Open whatever the pending focus can be opened through, once it is drawn.
 *
 *  Deliberately not a one-shot `moveend` handler. Registering one before
 *  calling setView means an animation already in flight -- the fit that runs
 *  when the panel opens, most reliably -- satisfies it early, and the focus
 *  lands against the marker set of the zoom being left rather than the one
 *  being entered. Holding the request as state instead makes the outcome
 *  independent of which move finishes first. */
function applyFocus() {
  if (!pendingFocus) return;
  const point = pendingFocus;
  const marker = markerByIndex.get(point.index);
  if (marker) {
    pendingFocus = null;
    marker.openPopup();
    return;
  }
  const stack = stackByIndex.get(point.index);
  if (stack) {
    pendingFocus = null;
    stack.showInStack(point);
  }
}

/** Zoom to one property and open its popup.
 *
 *  Zooming used to be assumed to free the property from its cluster. It does
 *  not: a property sharing a coordinate with its neighbours has no marker of
 *  its own at any zoom, and the reader who followed a brand here was left
 *  looking at a number that opened nothing. So go to the zoom that actually
 *  isolates it, and when none does, open the cluster on the property asked for. */
export function focusOn(point) {
  if (!map) return;
  const isolation = isolationZoom(point);
  const zoom = isolation === null ? FOCUS_ZOOM : isolation;
  // Whether the marker set on screen is already the one this point will be
  // found in. Asking before the move, because the move is what changes it.
  const drawn = map.getZoom() === zoom;
  pendingFocus = point;
  map.setView([point.lat, point.lon], zoom);
  // Selecting a second property at the same spot moves the map nowhere, and a
  // view that does not move reports nothing to wait for. Resolve it here
  // instead of leaving the popup on whichever property was chosen first.
  if (drawn) applyFocus();
}

export function fitToPoints() {
  if (!map || points.length === 0) {
    if (map) map.setView(PH_CENTER, PH_ZOOM);
    return;
  }
  map.fitBounds(boundsOf(points), { padding: FIT_PADDING, maxZoom: 15 });
}

/** Leaflet measures its container on creation, so a map built while hidden has
 *  no size. Call this after the panel becomes visible. */
export function refresh() {
  if (map) map.invalidateSize();
}
