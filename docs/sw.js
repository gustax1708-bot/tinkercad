// Service worker do CUIDA+
// Estratégia: rede primeiro, cache como reserva (assim você sempre vê a versão nova quando está online).
const CACHE = "cuida-v1";

// Arquivos guardados na instalação, para o app abrir mesmo sem internet.
const ARQUIVOS = [
  "./",
  "./pages/index.html",
  "./pages/medications.html",
  "./pages/hardware.html",
  "./pages/firmware.html",
  "./pages/docs.html",
  "./pages/workbench.html",
  "./pages/login.html",
  "./pages/profile.html",
  "./pages/privacy.html",
  "./pages/terms.html",
  "./404.html",
  "./favicon.svg",
  "./manifest.json",
  "./assets/css/home.css",
  "./assets/css/hardware.css",
  "./assets/css/firmware.css",
  "./assets/js/api.js",
  "./assets/js/home.js",
  "./assets/js/care-features.js",
  "./assets/js/hardware.js",
  "./assets/js/firmware.js",
  "./assets/js/pwa.js",
  "./assets/images/icon-192.png",
  "./assets/images/icon-512.png",
];

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ARQUIVOS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (evento) => {
  // apaga caches de versões antigas
  evento.waitUntil(
    caches
      .keys()
      .then((nomes) => Promise.all(nomes.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (evento) => {
  const req = evento.request;
  const url = new URL(req.url);

  // Só mexe em GET do próprio site. API (Render), fontes e outros sites passam direto.
  if (req.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.includes("/api/")) return;

  evento.respondWith(
    fetch(req)
      .then((resposta) => {
        if (resposta.ok) {
          const copia = resposta.clone();
          caches.open(CACHE).then((cache) => cache.put(req, copia));
        }
        return resposta;
      })
      .catch(() =>
        caches.match(req, { ignoreSearch: true }).then(
          (guardado) => guardado || (req.mode === "navigate" ? caches.match("./pages/index.html") : undefined)
        )
      )
  );
});