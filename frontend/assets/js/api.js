(function () {
  const staleAfterMs = 6 * 60 * 1000;
  const panicDurationMs = 10 * 60 * 1000;
  const refreshIntervalMs = 10 * 1000;
  const configuredBaseUrl =
    document.documentElement.dataset.apiBase ||
    window.CUIDA_API_URL ||
    window.location.origin;
  const apiBaseUrl = configuredBaseUrl.replace(/\/$/, "");
  const fetchWithTimeout = (url) => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 5000);
    return fetch(url, { cache: "no-store", signal: controller.signal }).finally(
      () => window.clearTimeout(timeoutId),
    );
  };

  const formatValue = (value, suffix = "", decimals = 1) => {
    if (value == null || Number.isNaN(Number(value))) return "--";
    const numericValue = Number(value);
    const formatted = Number.isInteger(numericValue)
      ? numericValue.toFixed(decimals)
      : numericValue.toFixed(decimals);
    return `${formatted}${suffix}`;
  };

  const setText = (selector, value) => {
    document.querySelectorAll(selector).forEach((element) => {
      element.textContent = value;
    });
  };

  let panicToastTimer;
  const showPanicNotification = () => {
    const toast = document.querySelector("#toast");
    if (!toast) return;
    const toastText = toast.querySelector("span");
    if (toastText) toastText.textContent = "Botão de pânico acionado. Alerta recebido.";
    toast.classList.add("show");
    window.clearTimeout(panicToastTimer);
    panicToastTimer = window.setTimeout(() => toast.classList.remove("show"), 5000);
  };

  const formatTime = (value) => {
    if (!value) return "sem leitura";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR");
  };

  const updateReading = (reading, latestPanic) => {
    if (!reading) {
      setText('[data-reading="temperature"]', "--");
      setText('[data-reading="heart-rate"]', "--");
      setText('[data-reading="spo2"]', "--");
      setText('[data-reading="panic"]', "--");
      setText("[data-reading-device]", "pulseira-01");
      setText("[data-reading-alert]", "Nenhum alerta manual registrado");
      setText("[data-reading-status]", "Aguardando dados da pulseira");
      setText("[data-reading-updated]", "Nenhuma leitura recebida");
      setText("[data-health-state]", "Aguardando");
      setText("[data-health-detail]", "Nenhuma telemetria recebida");
      setText("[data-component-esp32]", "sem telemetria");
      setText("[data-component-sensors]", "sem leitura");
      document.body.dataset.readingState = "idle";
      return;
    }

    setText(
      '[data-reading="temperature"]',
      formatValue(reading.temperature_c, " °C", 1),
    );
    setText(
      '[data-reading="heart-rate"]',
      formatValue(reading.heart_rate_bpm, " bpm", 1),
    );
    setText('[data-reading="spo2"]', formatValue(reading.spo2_percent, "%", 1));
    const panicReceivedAt = latestPanic
      ? Date.parse(latestPanic.received_at)
      : NaN;
    const panicActive =
      Boolean(latestPanic && latestPanic.panic) &&
      Number.isFinite(panicReceivedAt) &&
      Date.now() >= panicReceivedAt &&
      Date.now() - panicReceivedAt < panicDurationMs;
    const panicLabel = panicActive
      ? "Enviado"
      : latestPanic && latestPanic.panic
        ? "Expirado"
        : "Inativo";
    setText('[data-reading="panic"]', panicLabel);
    const receivedAt = Date.parse(reading.received_at);
    const readingIsFresh =
      Number.isFinite(receivedAt) && Date.now() - receivedAt <= staleAfterMs;
    const sensorConnected = readingIsFresh && reading.sensor_contact;
    const status = panicActive
      ? "Alerta remoto vigente"
      : readingIsFresh
        ? reading.sensor_contact
          ? "Monitoramento ativo"
          : "Sem contato com o sensor"
        : "Leitura desatualizada";
    setText("[data-reading-status]", status);
    document.documentElement.dataset.readingStale = String(!readingIsFresh);
    document.body.dataset.readingState = panicActive
      ? "panic"
      : readingIsFresh
        ? "live"
        : "stale";
    setText("[data-health-state]", sensorConnected ? "OK" : "OFF");
    setText(
      "[data-health-detail]",
      readingIsFresh
        ? reading.sensor_contact
          ? "Última telemetria recente"
          : "MAX30102 sem contato"
        : "Última leitura há mais de 6 minutos",
    );
    setText(
      "[data-component-esp32]",
      readingIsFresh ? "telemetria recente" : "sem telemetria",
    );
    setText(
      "[data-component-sensors]",
      readingIsFresh
        ? `MAX30102 ${reading.sensor_contact ? "com contato" : "sem contato"} · DS18B20 ${reading.temperature_c == null ? "sem leitura" : "ativo"}`
        : "sem leitura",
    );
    setText(
      "[data-reading-updated]",
      `Recebido em ${formatTime(reading.received_at)}`,
    );
    setText("[data-reading-trend]", reading.temperature_trend || "estavel");
    setText("[data-reading-device]", reading.device_id || "pulseira-01");

    const panicEndsAt = Number.isFinite(panicReceivedAt)
      ? formatTime(new Date(panicReceivedAt + panicDurationMs).toISOString())
      : "";
    const alertMessage = panicActive
      ? `Alerta enviado; válido até ${panicEndsAt}`
      : latestPanic && latestPanic.panic
        ? `Último alerta expirou às ${panicEndsAt}`
        : "Nenhum alerta manual registrado";
    setText("[data-reading-alert]", alertMessage);
  };

  const updateHistory = (readings) => {
    const log = document.querySelector("[data-reading-log]");
    const activityList = document.querySelector("[data-reading-history]");
    const activityCount = document.querySelector("[data-reading-count]");
    const recentReadings = readings.slice(0, 4);
    if (activityCount)
      activityCount.textContent = `${readings.length} registros`;

    if (log) {
      log.replaceChildren();
      if (!recentReadings.length) {
        const empty = document.createElement("p");
        empty.textContent = "Aguardando leitura da pulseira";
        log.append(empty);
      } else {
        recentReadings.forEach((reading) => {
          const line = document.createElement("p");
          const time = document.createElement("span");
          time.textContent = formatTime(reading.received_at);
          line.append(
            time,
            ` ${reading.panic ? "Alerta manual" : "Leitura enviada"} · ${reading.status}`,
          );
          log.append(line);
        });
      }
    }

    if (!activityList) return;
    activityList.replaceChildren();
    if (!recentReadings.length) {
      const empty = document.createElement("p");
      empty.className = "activity-empty";
      empty.textContent = "Aguardando eventos do dispositivo";
      activityList.append(empty);
      return;
    }

    recentReadings.slice(0, 3).forEach((reading) => {
      const item = document.createElement("div");
      item.className = "activity-item";
      const marker = document.createElement("span");
      marker.className = `activity-marker ${reading.panic ? "orange-marker" : "green-marker"}`;
      const content = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = reading.panic ? "Alerta manual" : "Leitura recebida";
      const details = document.createElement("p");
      details.textContent = `SpO₂ ${formatValue(reading.spo2_percent, "%")} · pulso ${formatValue(reading.heart_rate_bpm, " bpm")} · temperatura ${formatValue(reading.temperature_c, " °C")}`;
      const time = document.createElement("small");
      time.textContent = formatTime(reading.received_at);
      content.append(title, details, time);
      item.append(marker, content);
      activityList.append(item);
    });
  };

  let refreshInProgress = false;
  let panicBaselineEstablished = false;
  let lastPanicEventId = null;

  const notifyForNewPanic = (latestPanic) => {
    const eventId = latestPanic
      ? latestPanic.id ?? latestPanic.received_at
      : null;

    if (!panicBaselineEstablished) {
      panicBaselineEstablished = true;
      lastPanicEventId = eventId;
      const receivedAt = latestPanic
        ? Date.parse(latestPanic.received_at)
        : NaN;
      if (
        latestPanic?.panic &&
        Number.isFinite(receivedAt) &&
        Date.now() - receivedAt <= refreshIntervalMs + 5000 &&
        Date.now() >= receivedAt
      ) {
        showPanicNotification();
      }
      return;
    }

    if (latestPanic?.panic && eventId !== null && eventId !== lastPanicEventId) {
      showPanicNotification();
    }
    lastPanicEventId = eventId;
  };

  const refreshDeviceData = async () => {
    if (refreshInProgress) return;
    refreshInProgress = true;
    try {
      try {
        const latestResponse = await fetchWithTimeout(
          `${apiBaseUrl}/api/v1/latest`,
        );
        if (!latestResponse.ok) throw new Error("API indisponivel");
        const latest = await latestResponse.json();
        notifyForNewPanic(latest.latest_panic);
        updateReading(latest.reading, latest.latest_panic);
        document.documentElement.dataset.apiStatus = "online";
      } catch {
        setText("[data-reading-status]", "API indisponivel");
        document.documentElement.dataset.apiStatus = "offline";
        return;
      }

      try {
        const historyResponse = await fetchWithTimeout(
          `${apiBaseUrl}/api/v1/history`,
        );
        if (!historyResponse.ok) throw new Error("Historico indisponivel");
        const history = await historyResponse.json();
        updateHistory(history.readings || []);
      } catch {
        setText("[data-reading-count]", "Histórico indisponível");
      }
    } finally {
      refreshInProgress = false;
    }
  };

  document.addEventListener("DOMContentLoaded", () => {
    refreshDeviceData();
    window.setInterval(refreshDeviceData, refreshIntervalMs);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) refreshDeviceData();
    });
    window.addEventListener("focus", refreshDeviceData);
  });
})();
