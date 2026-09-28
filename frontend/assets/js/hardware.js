document.addEventListener("DOMContentLoaded", () => {
  const toast = document.querySelector("#toast");
  const diagnosticsButton = document.querySelector("#runDiagnosticsButton");

  const showToast = (message) => {
    if (!toast) return;
    const toastText = toast.querySelector("span");
    if (toastText) toastText.textContent = message;
    toast.classList.add("show");
    window.setTimeout(() => toast.classList.remove("show"), 3000);
  };

  if (diagnosticsButton) {
    diagnosticsButton.addEventListener("click", async () => {
      diagnosticsButton.disabled = true;
      try {
        const apiBase =
          document.documentElement.dataset.apiBase ||
          window.CUIDA_API_URL ||
          "http://localhost:8000";
        const response = await fetch(
          `${apiBase.replace(/\/$/, "")}/api/v1/latest`,
          { cache: "no-store" },
        );
        if (!response.ok) throw new Error("API indisponível");
        const { reading } = await response.json();
        if (!reading) {
          showToast(
            "API online; aguardando a primeira leitura do dispositivo.",
          );
        } else if (!reading.sensor_contact) {
          showToast("API online; MAX30102 sem contato com o sensor.");
        } else {
          const receivedAt = Date.parse(reading.received_at);
          if (!Number.isFinite(receivedAt) || Date.now() - receivedAt > 45000) {
            showToast(
              "API online; última leitura do dispositivo está desatualizada.",
            );
          } else {
            showToast(
              "API online; telemetria recente recebida do dispositivo.",
            );
          }
        }
      } catch {
        showToast(
          "Não foi possível consultar a API. Verifique o serviço local.",
        );
      } finally {
        diagnosticsButton.disabled = false;
      }
    });
  }
});
