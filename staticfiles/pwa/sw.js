var CACHE_VERSION = 'nitrotech-blog-v1';
var CACHE_NAME = 'pages-' + CACHE_VERSION;
var STATIC_CACHE = 'static-' + CACHE_VERSION;
var PRECACHE_URLS = [
  '/blog/',
  '/static/pwa/manifest.json',
  '/static/img/pwa/icon-192.png',
  '/static/img/pwa/icon-512.png',
  '/static/css/dist/styles.css'
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(function (cache) {
      return cache.addAll(PRECACHE_URLS).then(function () {
        return self.skipWaiting();
      });
    })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.map(function (key) {
          if (key !== CACHE_NAME && key !== STATIC_CACHE) {
            return caches.delete(key);
          }
        })
      );
    }).then(function () {
      return self.clients.claim();
    })
  );
});

function isNavigation(request) {
  return request.mode === 'navigate';
}

self.addEventListener('fetch', function (event) {
  var request = event.request;

  if (request.method !== 'GET') {
    return;
  }

  var url = new URL(request.url);

  if (url.origin !== location.origin) {
    return;
  }

  if (isNavigation(request)) {
    event.respondWith(
      fetch(request).then(function (response) {
        var copy = response.clone();
        caches.open(CACHE_NAME).then(function (cache) {
          cache.put(request, copy);
        });
        return response;
      }).catch(function () {
        return caches.match(request).then(function (cached) {
          if (cached) {
            return cached;
          }
          return caches.match('/blog/');
        });
      })
    );
    return;
  }

  if (url.pathname.indexOf('/static/') === 0 || url.pathname.indexOf('/media/') === 0) {
    event.respondWith(
      caches.match(request).then(function (cached) {
        if (cached) {
          return cached;
        }
        return fetch(request).then(function (response) {
          if (response.ok) {
            var copy = response.clone();
            caches.open(STATIC_CACHE).then(function (cache) {
              cache.put(request, copy);
            });
          }
          return response;
        });
      })
    );
    return;
  }
});
