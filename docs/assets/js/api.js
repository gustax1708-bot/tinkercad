(function () {
  const staleAfterMs = 6 * 60 * 1000;
  const refreshIntervalMs = 10 * 1000;
  const isPublishedDashboard =
    window.location.hostname === "gustax1708-bot.github.io";
  const defaultApiBaseUrl = isPublishedDashboard
    ? "https://cura-plus-api.onrender.com"
    : window.location.origin;
  const configuredBaseUrl =
    document.documentElement.dataset.apiBase ||
    window.CUIDA_API_URL ||
    defaultApiBaseUrl;
  const apiBaseUrl = configuredBaseUrl.replace(/\/$/, "");
  if (isPublishedDashboard) {
    window.CUIDA_API_URL = apiBaseUrl;
    window.CUIDA_API_READ_ONLY = true;
  }
  const fetchWithTimeout = (url, options = {}) => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 5000);
    return fetch(url, {
      ...options,
      cache: "no-store",
      signal: controller.signal,
    }).finally(() => window.clearTimeout(timeoutId));
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
    if (toastText) toastText.textContent = "Novo alerta de simulação recebido.";
    toast.classList.add("show");
    window.clearTimeout(panicToastTimer);
    panicToastTimer = window.setTimeout(() => toast.classList.remove("show"), 5000);
  };

  const formatTime = (value) => {
    if (!value) return "sem leitura";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR");
  };

  const renderActiveAlerts = (alerts) => {
    const panel = document.querySelector("[data-active-alerts]");
    const list = document.querySelector("[data-active-alert-list]");
    if (!panel || !list) return;
    list.replaceChildren();
    panel.hidden = alerts.length === 0;
    alerts.forEach((alert) => {
      const item = document.createElement("article");
      item.className = "active-alert-item";
      const details = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent =
        alert.alert_type === "fall" ? "Possível queda detectada" : "Alerta manual de pânico";
      const meta = document.createElement("p");
      meta.textContent = `${alert.status === "acknowledged" ? "Reconhecido" : "Ativo"} · ${alert.device_id} · ${formatTime(alert.created_at)}`;
      details.append(title, meta);
      if (window.CUIDA_API_READ_ONLY) {
        item.append(details);
      } else {
        const actions = document.createElement("div");
        actions.className = "active-alert-actions";
        if (alert.status === "active") {
          const acknowledge = document.createElement("button");
          acknowledge.className = "care-button secondary";
          acknowledge.type = "button";
          acknowledge.textContent = "Reconhecer";
          acknowledge.dataset.alertAction = "acknowledge";
          acknowledge.dataset.alertId = alert.id;
          actions.append(acknowledge);
        }
        const resolve = document.createElement("button");
        resolve.className = "care-button";
        resolve.type = "button";
        resolve.textContent = "Resolver";
        resolve.dataset.alertAction = "resolve";
        resolve.dataset.alertId = alert.id;
        actions.append(resolve);
        item.append(details, actions);
      }
      list.append(item);
    });
  };

  const updateReading = (reading, latestPanic, activeAlerts = []) => {
    if (!reading) {
      setText('[data-reading="temperature"]', "--");
      setText('[data-reading="heart-rate"]', "--");
      setText('[data-reading="spo2"]', "--");
      setText('[data-reading="battery"]', "--");
      setText('[data-reading="acceleration"]', "--");
      setText('[data-reading="gyroscope"]', "--");
      setText('[data-reading="motion"]', "--");
      setText('[data-reading="fall"]', "--");
      setText("[data-reading-battery-voltage]", "MAX17048");
      setText('[data-reading="panic"]', "Desativado");
      setText("[data-reading-device]", "pulseira-01");
      setText("[data-reading-alert]", "Nenhum alerta manual registrado");
      setText("[data-reading-status]", "Aguardando dados da pulseira");
      setText("[data-reading-updated]", "Nenhuma leitura recebida");
      setText("[data-health-state]", "Aguardando");
      setText("[data-health-detail]", "Nenhuma telemetria recebida");
      setText("[data-component-esp32]", "sem telemetria");
      setText("[data-component-sensors]", "sem leitura");
      renderActiveAlerts(activeAlerts);
      document.body.dataset.readingState = "idle";
      return;
    }

    const receivedAt = Date.parse(reading.received_at);
    const readingIsFresh =
      Number.isFinite(receivedAt) &&
      Date.now() >= receivedAt &&
      Date.now() - receivedAt <= staleAfterMs;
    const sensorConnected = readingIsFresh && reading.sensor_contact;
    setText(
      '[data-reading="temperature"]',
      !readingIsFresh
        ? "Desatualizado"
        : formatValue(reading.temperature_c, " °C", 1),
    );
    setText(
      '[data-reading="heart-rate"]',
      !readingIsFresh
        ? "Desatualizado"
        : !reading.sensor_contact
          ? "Sem contato"
          : formatValue(reading.heart_rate_bpm, " bpm", 1),
    );
    setText(
      '[data-reading="spo2"]',
      !readingIsFresh
        ? "Desatualizado"
        : !reading.sensor_contact
          ? "Sem contato"
          : formatValue(reading.spo2_percent, "%", 1),
    );
    setText(
      '[data-reading="battery"]',
      readingIsFresh
        ? formatValue(reading.battery_percent, "%", 0)
        : "Desatualizado",
    );
    setText(
      "[data-reading-battery-voltage]",
      !readingIsFresh
        ? "Leitura desatualizada"
        : reading.battery_voltage == null
        ? "MAX17048"
        : `${formatValue(reading.battery_voltage, " V", 2)} · MAX17048`,
    );
    setText(
      '[data-reading="acceleration"]',
      readingIsFresh
        ? formatValue(reading.acceleration_g, " g", 2)
        : "Desatualizado",
    );
    const gyroscopeValues = [
      reading.gyroscope_x_dps,
      reading.gyroscope_y_dps,
      reading.gyroscope_z_dps,
    ];
    setText(
      '[data-reading="gyroscope"]',
      !readingIsFresh
        ? "Desatualizado"
        : gyroscopeValues.every((value) => value == null)
          ? "Sem leitura"
          : `X: ${formatValue(gyroscopeValues[0], "°/s")} · Y: ${formatValue(gyroscopeValues[1], "°/s")} · Z: ${formatValue(gyroscopeValues[2], "°/s")}`,
    );
    setText(
      '[data-reading="motion"]',
      !readingIsFresh
        ? "Desatualizado"
        : reading.acceleration_g == null
        ? "--"
        : reading.motion_active
          ? "Ativo"
          : "Repouso",
    );
    const fallAlert = activeAlerts.find((alert) => alert.alert_type === "fall");
    setText(
      '[data-reading="fall"]',
      !readingIsFresh
        ? "Desatualizado"
        : fallAlert
          ? fallAlert.status === "acknowledged" ? "Reconhecida" : "Alerta ativo"
          : reading.fall_detected
            ? "Evento resolvido"
            : "Não detectada",
    );
    const panicAlert = activeAlerts.find((alert) => alert.alert_type === "panic");
    const panicLabel = panicAlert
      ? panicAlert.status === "acknowledged" ? "Reconhecido" : "Ativo"
      : latestPanic && latestPanic.panic
        ? "Resolvido"
        : "Inativo";
    setText('[data-reading="panic"]', panicLabel);
    const status = activeAlerts.some((alert) => alert.status === "active")
      ? "Alerta ativo — requer atenção"
      : activeAlerts.length
        ? "Alerta reconhecido"
      : readingIsFresh
        ? reading.sensor_contact
          ? "Monitoramento ativo"
          : "Sem contato com o sensor"
        : "Leitura desatualizada";
    setText("[data-reading-status]", status);
    document.documentElement.dataset.readingStale = String(!readingIsFresh);
    document.body.dataset.readingState = activeAlerts.length
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
          : "Sem contato: pulso e SpO₂ não disponíveis"
        : "Última leitura há mais de 6 minutos",
    );
    setText(
      "[data-component-esp32]",
      readingIsFresh ? "telemetria recente" : "sem telemetria",
    );
    setText(
      "[data-component-sensors]",
      readingIsFresh
        ? `MAX30102 ${reading.sensor_contact ? "com contato" : "sem contato"} · MAX30205 ${reading.temperature_c == null ? "sem leitura" : "ativo"} · MPU6050 ${reading.acceleration_g == null ? "indisponível" : "ativo"}`
        : "sem leitura",
    );
    setText(
      "[data-reading-updated]",
      readingIsFresh
        ? `Recebido em ${formatTime(reading.received_at)}`
        : `Leitura antiga (${formatTime(reading.received_at)})`,
    );
    setText("[data-reading-trend]", reading.temperature_trend || "estavel");
    setText("[data-reading-device]", reading.device_id || "pulseira-01");

    const alertMessage = panicAlert
      ? `Alerta ${panicAlert.status === "acknowledged" ? "reconhecido" : "ativo"} desde ${formatTime(panicAlert.created_at)}`
      : latestPanic && latestPanic.panic
        ? "Último alerta resolvido"
        : "Nenhum alerta manual registrado";
    setText("[data-reading-alert]", alertMessage);
    renderActiveAlerts(activeAlerts);
  };

  const chartMetrics = {
    heart_rate_bpm: {
      label: "Frequência de pulso",
      unit: " bpm",
      decimals: 0,
    },
    spo2_percent: {
      label: "Saturação de oxigênio",
      unit: "%",
      decimals: 0,
    },
    temperature_c: {
      label: "Temperatura de contato",
      unit: " °C",
      decimals: 1,
    },
    battery_percent: {
      label: "Nível da bateria",
      unit: "%",
      decimals: 0,
    },
  };
  let chartReadings = [];

  const renderReadingChart = () => {
    const chart = document.querySelector("[data-reading-chart]");
    const metricSelect = document.querySelector("[data-chart-metric]");
    const emptyState = document.querySelector("[data-chart-empty]");
    const summary = document.querySelector("[data-chart-summary]");
    if (!chart || !metricSelect || !emptyState || !summary) return;

    const metric =
      chartMetrics[metricSelect.value] || chartMetrics.heart_rate_bpm;
    const points = chartReadings
      .map((reading) => ({
        time: Date.parse(reading.received_at),
        value: reading[metricSelect.value],
      }))
      .filter(
        (point) =>
          Number.isFinite(point.time) &&
          point.value != null &&
          point.value !== "" &&
          Number.isFinite(Number(point.value)),
      )
      .map((point) => ({ ...point, value: Number(point.value) }))
      .sort((a, b) => a.time - b.time)
      .slice(-30);

    chart.replaceChildren();
    if (!points.length) {
      chart.hidden = true;
      emptyState.hidden = false;
      emptyState.textContent = chartReadings.length
        ? `Sem leituras válidas para ${metric.label.toLocaleLowerCase("pt-BR")}.`
        : "Aguardando leituras para gerar o gráfico.";
      summary.textContent = "";
      return;
    }

    const values = points.map((point) => point.value);
    const dataMin = Math.min(...values);
    const dataMax = Math.max(...values);
    const minLabel = `${dataMin.toFixed(metric.decimals)}${metric.unit}`;
    const maxLabel = `${dataMax.toFixed(metric.decimals)}${metric.unit}`;
    const namespace = "http://www.w3.org/2000/svg";
    const makeSvgElement = (tagName, attributes = {}) => {
      const element = document.createElementNS(namespace, tagName);
      Object.entries(attributes).forEach(([name, value]) => {
        element.setAttribute(name, String(value));
      });
      return element;
    };
    const title = makeSvgElement("title", { id: "readingChartSvgTitle" });
    title.textContent = `Histórico de ${metric.label.toLocaleLowerCase("pt-BR")}`;
    const firstTime = new Date(points[0].time).toLocaleString("pt-BR");
    const lastTime = new Date(points[points.length - 1].time).toLocaleString(
      "pt-BR",
    );
    const description = makeSvgElement("desc", {
      id: "readingChartSvgDescription",
    });
    description.textContent =
      `${points.length} leituras entre ${firstTime} e ${lastTime}, ` +
      `com valores entre ${minLabel} e ${maxLabel}.`;
    chart.append(title, description);
    chart.hidden = false;
    emptyState.hidden = true;

    const width = 480;
    const height = 280;
    const plot = { left: 90, right: 12, top: 18, bottom: 46 };
    const plotWidth = width - plot.left - plot.right;
    const plotHeight = height - plot.top - plot.bottom;
    const minimumPadding = metric.decimals > 0 ? 0.1 : 1;
    const padding = Math.max(
      (dataMax - dataMin) * 0.15,
      Math.abs(dataMax) * 0.03,
      minimumPadding,
    );
    const min = dataMin - padding;
    const max = dataMax + padding;

    for (let index = 0; index <= 4; index += 1) {
      const y = plot.top + (plotHeight * index) / 4;
      const value = max - ((max - min) * index) / 4;
      chart.append(
        makeSvgElement("line", {
          class: "chart-grid-line",
          x1: plot.left,
          x2: width - plot.right,
          y1: y,
          y2: y,
        }),
      );
      const label = makeSvgElement("text", {
        class: "chart-axis-label",
        x: plot.left - 10,
        y: y + 4,
        "text-anchor": "end",
      });
      label.textContent = `${value.toFixed(metric.decimals)}${metric.unit}`;
      chart.append(label);
    }

    chart.append(
      makeSvgElement("line", {
        class: "chart-axis-line",
        x1: plot.left,
        x2: width - plot.right,
        y1: height - plot.bottom,
        y2: height - plot.bottom,
      }),
    );

    const xFor = (index) =>
      points.length === 1
        ? plot.left + plotWidth / 2
        : plot.left + (plotWidth * index) / (points.length - 1);
    const yFor = (value) =>
      plot.top + (plotHeight * (max - value)) / (max - min);
    const path = points
      .map(
        (point, index) =>
          `${index === 0 ? "M" : "L"} ${xFor(index).toFixed(1)} ${yFor(point.value).toFixed(1)}`,
      )
      .join(" ");
    chart.append(
      makeSvgElement("path", {
        class: "chart-data-line",
        d: path,
      }),
    );

    points.forEach((point, index) => {
      chart.append(
        makeSvgElement("circle", {
          class: "chart-data-point",
          cx: xFor(index),
          cy: yFor(point.value),
          r: 4.5,
        }),
      );
    });

    const timeLabelIndices = [
      ...new Set([0, Math.floor((points.length - 1) / 2), points.length - 1]),
    ];
    timeLabelIndices.forEach((index, labelIndex) => {
      const label = makeSvgElement("text", {
        class: "chart-axis-label",
        x: xFor(index),
        y: height - 12,
        "text-anchor":
          timeLabelIndices.length === 1
            ? "middle"
            : labelIndex === 0
              ? "start"
              : labelIndex === timeLabelIndices.length - 1
                ? "end"
                : "middle",
      });
      label.textContent = new Date(points[index].time).toLocaleTimeString(
        "pt-BR",
        {
          hour: "2-digit",
          minute: "2-digit",
        },
      );
      chart.append(label);
    });

    const lastPoint = points[points.length - 1];
    const lastReadingTime = new Date(lastPoint.time).toLocaleTimeString(
      "pt-BR",
      {
        hour: "2-digit",
        minute: "2-digit",
      },
    );
    summary.textContent = `${points.length} ${
      points.length === 1 ? "leitura válida" : "leituras válidas"
    } · de ${minLabel} a ${maxLabel} · última às ${lastReadingTime}`;
  };

  const updateHistory = (readings) => {
    chartReadings = Array.isArray(readings) ? readings : [];
    renderReadingChart();
    const log = document.querySelector("[data-reading-log]");
    const activityList = document.querySelector("[data-reading-history]");
    const activityCount = document.querySelector("[data-reading-count]");
    const recentReadings = chartReadings.slice(0, 4);
    if (activityCount)
      activityCount.textContent = `${chartReadings.length} registros`;

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
            ` ${reading.fall_detected ? "Possível queda" : reading.panic ? "Alerta manual" : "Leitura enviada"} · ${reading.status}`,
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
      details.textContent = `SpO₂ ${formatValue(reading.spo2_percent, "%")} · pulso ${formatValue(reading.heart_rate_bpm, " bpm")} · temp. ${formatValue(reading.temperature_c, " °C")} · bateria ${formatValue(reading.battery_percent, "%", 0)}${reading.fall_detected ? " · possível queda" : ""}`;
      const time = document.createElement("small");
      time.textContent = formatTime(reading.received_at);
      content.append(title, details, time);
      item.append(marker, content);
      activityList.append(item);
    });
  };

  let refreshInProgress = false;
  let alertBaselineEstablished = false;
  let lastAlertIds = new Set();

  const notifyForNewAlerts = (alerts) => {
    const currentAlertIds = new Set(alerts.map((alert) => String(alert.id)));
    if (!alertBaselineEstablished) {
      alertBaselineEstablished = true;
      const hasRecentAlert = alerts.some((alert) => {
        const createdAt = Date.parse(alert.created_at);
        return (
          Number.isFinite(createdAt) &&
          Date.now() >= createdAt &&
          Date.now() - createdAt <= refreshIntervalMs + 5000
        );
      });
      if (hasRecentAlert) showPanicNotification();
      lastAlertIds = currentAlertIds;
      return;
    }
    if ([...currentAlertIds].some((id) => !lastAlertIds.has(id))) {
      showPanicNotification();
    }
    lastAlertIds = currentAlertIds;
  };

  const submitAlertAction = async (alertId, action) => {
    const response = await fetchWithTimeout(
      `${apiBaseUrl}/api/v1/alerts/${encodeURIComponent(alertId)}/${action}`,
      { method: "POST" },
    );
    if (!response.ok) throw new Error("Não foi possível atualizar o alerta.");
  };

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-alert-action]");
    if (!button) return;
    button.disabled = true;
    try {
      await submitAlertAction(button.dataset.alertId, button.dataset.alertAction);
      while (refreshInProgress) {
        await new Promise((resolve) => window.setTimeout(resolve, 50));
      }
      await refreshDeviceData();
    } catch (error) {
      button.disabled = false;
      const toast = document.querySelector("#toast");
      if (toast) {
        const toastText = toast.querySelector("span");
        if (toastText) toastText.textContent = error.message;
        toast.classList.add("show");
        window.setTimeout(() => toast.classList.remove("show"), 5000);
      }
    }
  });

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
        const activeAlerts = Array.isArray(latest.active_alerts)
          ? latest.active_alerts
          : [];
        notifyForNewAlerts(activeAlerts);
        updateReading(latest.reading, latest.latest_panic, activeAlerts);
        document.documentElement.dataset.apiStatus = "online";
        setText("[data-api-connection]", "API e banco online");
      } catch {
        updateReading(null, null, []);
        setText("[data-reading-status]", "API indisponível — sem dados atuais");
        setText("[data-api-connection]", "API indisponível");
        setText("[data-health-state]", "OFF");
        setText("[data-health-detail]", "Não foi possível consultar a API");
        setText("[data-reading-updated]", "Sem conexão com a API");
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
    const chartMetric = document.querySelector("[data-chart-metric]");
    if (chartMetric) {
      chartMetric.addEventListener("change", renderReadingChart);
    }
    refreshDeviceData();
    window.setInterval(refreshDeviceData, refreshIntervalMs);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) refreshDeviceData();
    });
    window.addEventListener("focus", refreshDeviceData);
  });
})();
