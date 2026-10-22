document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.querySelector("#sidebar");
  const toast = document.querySelector("#toast");
  const menuButton = document.querySelector("#menuButton");
  let toastTimer;

  if (window.lucide && typeof window.lucide.createIcons === "function") {
    window.lucide.createIcons();
  }

  const showToast = (message) => {
    if (!toast) return;
    const toastText = toast.querySelector("span");
    if (toastText) toastText.textContent = message;
    toast.classList.add("show");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toast.classList.remove("show"), 3000);
  };

  const shareProject = async () => {
    try {
      if (!navigator.clipboard || !window.location.href)
        throw new Error("Clipboard indisponível");
      await navigator.clipboard.writeText(window.location.href);
      showToast("Link do projeto copiado para a área de transferência.");
    } catch {
      showToast("Não foi possível copiar o link neste navegador.");
    }
  };

  const downloadProjectData = async () => {
    try {
      const apiBase =
        document.documentElement.dataset.apiBase ||
        window.CUIDA_API_URL ||
        window.location.origin;
      const response = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/latest`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error("API indisponível");
      const payload = await response.json();
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "cuida-plus-ultima-leitura.json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      showToast("Arquivo JSON da última leitura foi exportado.");
    } catch {
      showToast("Não foi possível exportar a leitura. Verifique a API.");
    }
  };

  if (menuButton && sidebar) {
    menuButton.addEventListener("click", () =>
      sidebar.classList.toggle("open"),
    );
  }

  document
    .querySelectorAll("#shareButton, #shareTopButton")
    .forEach((button) => {
      button.addEventListener("click", shareProject);
    });

  const downloadButton = document.querySelector("#downloadButton");
  if (downloadButton) {
    downloadButton.addEventListener("click", downloadProjectData);
  }

  const openWorkbench = document.querySelector("#openWorkbench");
  if (openWorkbench) {
    openWorkbench.addEventListener("click", () => {
      const workbenchPath = "workbench.html";
      const currentPage = window.location.pathname.split("/").pop() || "index.html";
      if (currentPage === workbenchPath) {
        showToast("A bancada já está aberta.");
        return;
      }
      window.location.assign(workbenchPath);
    });
  }

  const viewDocsButton = document.querySelector("#viewDocsButton");
  if (viewDocsButton) {
    viewDocsButton.addEventListener("click", () => {
      const docsPath = "docs.html";
      const currentPage = window.location.pathname.split("/").pop() || "index.html";
      if (currentPage === docsPath) {
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      }
      window.location.assign(docsPath);
    });
  }

  document.querySelectorAll(".nav-item[data-section]").forEach((item) => {
    item.addEventListener("click", (event) => {
      const pageBySection = {
        overview: "index.html",
        hardware: "hardware.html",
        software: "firmware.html",
      };
      const currentPage =
        window.location.pathname.split("/").pop() || "index.html";
      const section = item.dataset.section;
      const targetPage = pageBySection[section];
      const href = item.getAttribute("href");

      if (
        item.tagName === "A" &&
        href &&
        !href.startsWith("#") &&
        href !== currentPage
      ) {
        return;
      }

      if (item.tagName === "A" && href && href.startsWith("#")) {
        event.preventDefault();
      }

      const activeItem = document.querySelector(".nav-item.active");
      if (activeItem) activeItem.classList.remove("active");
      item.classList.add("active");

      const breadcrumb = document.querySelector(".breadcrumbs strong");
      const label = item.querySelector("span");
      if (breadcrumb && label) breadcrumb.textContent = label.textContent;

      if (targetPage && targetPage !== currentPage && item.tagName !== "A") {
        window.location.assign(targetPage);
        return;
      }

      const target =
        document.querySelector(`#${section}`) ||
        document.querySelector("#overview");
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      if (sidebar) sidebar.classList.remove("open");
    });
  });
});
