// Registra o service worker e guarda o evento de instalação do navegador.
(function () {
  if (!("serviceWorker" in navigator)) return;

  // currentScript só existe enquanto o script roda, por isso guardamos agora.
  const scriptSrc = document.currentScript && document.currentScript.src;

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