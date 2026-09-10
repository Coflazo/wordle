/* Service worker.
 *
 * The app promises to run on your own machine, so it should not stop working
 * when the network does. The shell is cached on install and served cache-first;
 * API calls go to the network first and fall back to the last good response.
 *
 * Scoped deliberately: game state is authoritative on the server, so a guess is
 * never answered from cache. Only reads are.
 */

const VERSION = 'v1';
const SHELL_CACHE = `oflaz-shell-${VERSION}`;
const DATA_CACHE = `oflaz-data-${VERSION}`;

const SHELL = [
  '/',
  '/game',
  '/profile',
  '/css/tokens.css',
  '/css/base.css',
  '/css/game.css',
  '/css/welcome.css',
  '/css/profile.css',
  '/js/api.js',
  '/js/analytics.js',
  '/js/avatar.js',
  '/js/board.js',
  '/js/game.js',
  '/js/i18n.js',
  '/js/keyboard.js',
  '/js/pixel-background.js',
  '/js/profile.js',
  '/js/state.js',
  '/js/theme.js',
  '/js/toast.js',
  '/js/welcome.js',
  '/assets/icons/favicon.svg',
  '/assets/manifest.json',
];

// Reads worth keeping a copy of. A stale dashboard beats a blank page.
const CACHEABLE_API = [/^\/api\/stats\//, /^\/api\/meaning\//, /^\/api\/flags/];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      // addAll rejects the whole install if any single entry 404s, which would
      // leave the worker permanently uninstalled. Add them individually.
      .then((cache) => Promise.allSettled(SHELL.map((url) => cache.add(url))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names
          .filter((name) => name !== SHELL_CACHE && name !== DATA_CACHE)
          .map((name) => caches.delete(name))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith('/api/')) {
    if (CACHEABLE_API.some((pattern) => pattern.test(url.pathname))) {
      event.respondWith(networkFirst(request));
    }
    // Everything else — starting a game, submitting a guess — must reach the
    // server or fail honestly. Answering those from a cache would show the
    // player a result that never happened.
    return;
  }

  event.respondWith(cacheFirst(request));
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    // Refresh in the background so the next load is current.
    fetchAndStore(request, SHELL_CACHE).catch(() => {});
    return cached;
  }
  try {
    return await fetchAndStore(request, SHELL_CACHE);
  } catch (err) {
    const fallback = await caches.match('/');
    if (fallback) return fallback;
    throw err;
  }
}

async function networkFirst(request) {
  try {
    return await fetchAndStore(request, DATA_CACHE);
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response(
      JSON.stringify({ detail: { code: 'offline', message: 'no connection', params: {} } }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

async function fetchAndStore(request, cacheName) {
  const response = await fetch(request);
  if (response && response.ok) {
    const cache = await caches.open(cacheName);
    cache.put(request, response.clone());
  }
  return response;
}
