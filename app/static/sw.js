/* 大雪深埋 Service Worker:静态资源缓存,API 始终走网络(数据在服务端) */
const CACHE = "daxue-v3";
const ASSETS = [
  "/", "/static/style.css", "/static/app.js",
  "/static/vendor/katex/katex.min.css", "/static/vendor/katex/katex.min.js",
  "/static/vendor/katex/auto-render.min.js",
  "/static/icons/icon-192.png", "/static/icons/icon-512.png",
  "/static/manifest.json",
];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ).then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;             // API 写操作直连
  if (url.pathname.startsWith("/api/")) return;        // API 走网络
  if (url.origin !== location.origin) return;
  e.respondWith(
    caches.match(e.request).then(hit =>
      hit || fetch(e.request).then(resp => {
        if (resp.ok) {
          const copy = resp.clone();
          caches.open(CACHE).then(c => c.put(e.request, copy));
        }
        return resp;
      }).catch(() => caches.match("/"))
    )
  );
});
