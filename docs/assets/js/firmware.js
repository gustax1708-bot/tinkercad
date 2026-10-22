document.addEventListener("DOMContentLoaded", () => {
  const toast = document.querySelector("#toast");

  const showToast = (message) => {
    if (!toast) return;
    const toastText = toast.querySelector("span");
    if (toastText) toastText.textContent = message;
    toast.classList.add("show");
    window.setTimeout(() => toast.classList.remove("show"), 3000);
  };

  const copyCodeButton = document.querySelector("#copyCodeButton");
  if (copyCodeButton) {
    copyCodeButton.addEventListener("click", async () => {
      const source = document.querySelector(".code-block code");
      if (!source || !navigator.clipboard) {
        showToast("A cópia não está disponível neste navegador.");
        return;
      }
      try {
        await navigator.clipboard.writeText(source.innerText);
        showToast("Trecho copiado para a área de transferência.");
      } catch {
        showToast("Não foi possível acessar a área de transferência.");
      }
    });
  }

  const viewDependenciesButton = document.querySelector(
    "#viewDependenciesButton",
  );
  if (viewDependenciesButton) {
    viewDependenciesButton.addEventListener("click", () => {
      document
        .querySelector(".dependency-list")
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }
});
