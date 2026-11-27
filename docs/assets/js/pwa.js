// Registra o service worker e guarda o evento de instalação do navegador.
(function () {
  const hostname = window.location.hostname;
  const isCodespacesPreview =
    hostname === "github.dev" ||
    hostname.endsWith(".app.github.dev") ||
    hostname.endsWith(".githubpreview.dev");

  // currentScript só existe enquanto o script roda, por isso guardamos agora.
  const scriptSrc = document.currentScript && document.currentScript.src;

  // Remove instalações antigas do preview e não pede novo manifesto nem worker protegido.
  if (isCodespacesPreview) {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.getRegistrations().then((registrations) => {
        registrations.forEach((registration) => registration.unregister());
      });
    }
    document.querySelectorAll('link[rel="manifest"]').forEach((link) => link.remove());
    return;
  }

  if (scriptSrc) {
    const manifestUrl = new URL("../../manifest.json", scriptSrc);
    if (!document.querySelector('link[rel="manifest"]')) {
      const manifest = document.createElement("link");
      manifest.rel = "manifest";
      manifest.href = manifestUrl.href;
      document.head.appendChild(manifest);
    }
  }

  if (!("serviceWorker" in navigator)) return;

  window.addEventListener("load", () => {
    // Caminho calculado a partir deste arquivo: funciona em /tinkercad/ (GitHub Pages) e no localhost.
    const swUrl = new URL("../../sw.js", scriptSrc || window.location.href);
    navigator.serviceWorker.register(swUrl.href).catch((erro) => console.warn("PWA: falha ao registrar", erro));
  });

  // Permite criar um botão próprio: window.instalarCuida()
  let convite = null;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    convite = e;
    document.dispatchEvent(new CustomEvent("cuida:pode-instalar"));
  });
  window.instalarCuida = async () => {
    if (!convite) return false;
    convite.prompt();
    const { outcome } = await convite.userChoice;
    convite = null;
    return outcome === "accepted";
  };
})();