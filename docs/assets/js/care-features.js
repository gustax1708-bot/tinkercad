document.addEventListener("DOMContentLoaded", () => {
  const storageKeys = {
    accessibility: "cuida-accessibility",
    medicines: "cuida-medicines",
    profile: "cuida-profile",
    reminders: "cuida-reminders",
  };

  const readStored = (key, fallback) => {
    const value = window.localStorage.getItem(key);
    if (!value) return fallback;
    try {
      return JSON.parse(value);
    } catch (error) {
      console.error(`Não foi possível ler os dados locais (${key}).`, error);
      return fallback;
    }
  };

  const saveStored = (key, value) => {
    window.localStorage.setItem(key, JSON.stringify(value));
  };

  const accessibilitySettings = {
    theme: "light",
    contrast: false,
    largeText: false,
    reduceMotion: false,
    ...readStored(storageKeys.accessibility, {}),
  };
  const applyAccessibilitySettings = () => {
    document.body.dataset.theme = accessibilitySettings.theme;
    document.body.classList.toggle("high-contrast", accessibilitySettings.contrast);
    document.body.classList.toggle("large-text", accessibilitySettings.largeText);
    document.body.classList.toggle("reduce-motion", accessibilitySettings.reduceMotion);
    document.querySelectorAll("[data-accessibility-setting]").forEach((button) => {
      const setting = button.dataset.accessibilitySetting;
      button.setAttribute("aria-pressed", String(Boolean(accessibilitySettings[setting])));
    });
    const themeButton = document.querySelector('[data-accessibility-setting="theme"]');
    if (themeButton) {
      themeButton.setAttribute("aria-pressed", String(accessibilitySettings.theme === "dark"));
      const label = themeButton.querySelector("[data-setting-label]");
      if (label) label.textContent = accessibilitySettings.theme === "dark" ? "Modo claro" : "Modo escuro";
    }
    saveStored(storageKeys.accessibility, accessibilitySettings);
  };

  const accessPanel = document.createElement("section");
  accessPanel.className = "accessibility-panel";
  accessPanel.id = "accessibilityPanel";
  accessPanel.setAttribute("aria-label", "Opções de acessibilidade");
  accessPanel.hidden = true;
  accessPanel.innerHTML = `
    <h2>Acessibilidade</h2>
    <button class="accessibility-option" type="button" data-accessibility-setting="theme" aria-pressed="false">
      <span data-setting-label>Modo escuro</span><i data-lucide="moon"></i>
    </button>
    <button class="accessibility-option" type="button" data-accessibility-setting="contrast" aria-pressed="false">
      <span>Alto contraste</span><i data-lucide="contrast"></i>
    </button>
    <button class="accessibility-option" type="button" data-accessibility-setting="largeText" aria-pressed="false">
      <span>Aumentar texto</span><i data-lucide="type"></i>
    </button>
    <button class="accessibility-option" type="button" data-accessibility-setting="reduceMotion" aria-pressed="false">
      <span>Reduzir movimento</span><i data-lucide="accessibility"></i>
    </button>`;
  const accessButton = document.createElement("button");
  accessButton.className = "accessibility-launcher";
  accessButton.type = "button";
  accessButton.setAttribute("aria-label", "Abrir opções de acessibilidade");
  accessButton.setAttribute("aria-controls", accessPanel.id);
  accessButton.setAttribute("aria-expanded", "false");
  accessButton.innerHTML = '<i data-lucide="accessibility"></i>';
  document.body.append(accessPanel, accessButton);

  accessButton.addEventListener("click", () => {
    accessPanel.hidden = !accessPanel.hidden;
    accessButton.setAttribute("aria-expanded", String(!accessPanel.hidden));
  });
  accessPanel.addEventListener("click", (event) => {
    const button = event.target.closest("[data-accessibility-setting]");
    if (!button) return;
    const setting = button.dataset.accessibilitySetting;
    accessibilitySettings[setting] =
      setting === "theme"
        ? accessibilitySettings.theme !== "dark" ? "dark" : "light"
        : !accessibilitySettings[setting];
    applyAccessibilitySettings();
  });
  applyAccessibilitySettings();

  const iconLibrary = window.lucide;
  if (iconLibrary && typeof iconLibrary.createIcons === "function") {
    iconLibrary.createIcons();
  }

  let profile = readStored(storageKeys.profile, null);
  const renderAccount = () => {
    const userName = profile?.name?.trim() || profile?.email?.split("@")[0] || "";
    const welcome = document.querySelector("[data-welcome-user]");
    if (welcome) {
      welcome.textContent = userName
        ? `Bem-vindo(a), ${userName}!`
        : "Bem-vindo(a) ao CUIDA+";
    }

    const accountLink = document.querySelector("[data-account-link]");
    const accountName = document.querySelector("[data-account-name]");
    const accountEmail = document.querySelector("[data-account-email]");
    const accountAvatar = document.querySelector("[data-account-avatar]");
    if (accountName) accountName.textContent = userName || "Visitante";
    if (accountEmail) {
      accountEmail.textContent = profile?.email || "Entre para acessar seu perfil";
    }
    if (accountLink) accountLink.href = profile ? "profile.html" : "login.html";
    if (accountAvatar) {
      if (userName) {
        const initials = userName
          .split(/\s+/)
          .slice(0, 2)
          .map((part) => part.charAt(0).toLocaleUpperCase())
          .join("");
        accountAvatar.textContent = initials;
      } else {
        accountAvatar.replaceChildren();
        const userIcon = document.createElement("i");
        userIcon.dataset.lucide = "user-round";
        accountAvatar.append(userIcon);
      }
    }

    const authAction = document.querySelector("[data-auth-action]");
    if (authAction) {
      const label = profile ? "Sair" : "Entrar";
      authAction.setAttribute("aria-label", label);
      authAction.title = label;
      authAction.innerHTML = `<i data-lucide="${profile ? "log-out" : "log-in"}"></i>`;
      if (iconLibrary && typeof iconLibrary.createIcons === "function") {
        iconLibrary.createIcons();
      }
    }
  };
  renderAccount();

  document.querySelector("[data-auth-action]")?.addEventListener("click", (event) => {
    if (!profile) return;
    event.preventDefault();
    window.localStorage.removeItem(storageKeys.profile);
    profile = null;
    renderAccount();
    window.location.assign("login.html");
  });

  const form = document.querySelector("#medicineForm");
  const timeFields = document.querySelector("#medicineTimes");
  const medicineList = document.querySelector("#medicineList");
  const medicineStatus = document.querySelector("#medicineStatus");
  let medicines = readStored(storageKeys.medicines, []);

  const announce = (message) => {
    if (!medicineStatus) return;
    medicineStatus.textContent = message;
    medicineStatus.classList.add("show");
    window.setTimeout(() => medicineStatus.classList.remove("show"), 6000);
  };

  const renderMedicines = () => {
    if (!medicineList) return;
    medicineList.replaceChildren();
    if (medicines.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-medicines";
      empty.textContent = "Nenhum medicamento cadastrado. Use o formulário para adicionar o primeiro.";
      medicineList.append(empty);
      return;
    }

    medicines.forEach((medicine) => {
      const item = document.createElement("article");
      item.className = "medicine-item";
      const details = document.createElement("div");
      const name = document.createElement("h3");
      name.textContent = medicine.name;
      details.append(name);
      const dosage = document.createElement("p");
      dosage.textContent = medicine.dosage || "Dose não informada";
      details.append(dosage);
      if (medicine.notes) {
        const notes = document.createElement("p");
        notes.textContent = medicine.notes;
        details.append(notes);
      }
      const times = document.createElement("div");
      times.className = "medicine-times";
      medicine.times.forEach((time) => {
        const timeTag = document.createElement("span");
        timeTag.className = "medicine-time";
        timeTag.textContent = time;
        times.append(timeTag);
      });
      details.append(times);
      const remove = document.createElement("button");
      remove.className = "care-button danger";
      remove.type = "button";
      remove.textContent = "Excluir";
      remove.setAttribute("aria-label", `Excluir ${medicine.name}`);
      remove.addEventListener("click", () => {
        medicines = medicines.filter((entry) => entry.id !== medicine.id);
        saveStored(storageKeys.medicines, medicines);
        renderMedicines();
        announce("Medicamento removido.");
      });
      item.append(details, remove);
      medicineList.append(item);
    });
  };

  if (form && timeFields) {
    document.querySelector("#addMedicineTime")?.addEventListener("click", () => {
      const timeInput = document.createElement("input");
      timeInput.type = "time";
      timeInput.required = true;
      timeInput.setAttribute("aria-label", "Outro horário para tomar o medicamento");
      timeFields.append(timeInput);
      timeInput.focus();
    });

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const times = [...timeFields.querySelectorAll('input[type="time"]')]
        .map((input) => input.value)
        .filter(Boolean);
      const uniqueTimes = [...new Set(times)].sort();
      if (uniqueTimes.length === 0) {
        announce("Adicione ao menos um horário para o medicamento.");
        return;
      }

      const data = new FormData(form);
      medicines.push({
        id: window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        name: String(data.get("name")).trim(),
        dosage: String(data.get("dosage")).trim(),
        notes: String(data.get("notes")).trim(),
        times: uniqueTimes,
      });
      saveStored(storageKeys.medicines, medicines);
      form.reset();
      timeFields.replaceChildren();
      const firstTime = document.createElement("input");
      firstTime.type = "time";
      firstTime.name = "time";
      firstTime.required = true;
      firstTime.setAttribute("aria-label", "Horário para tomar o medicamento");
      timeFields.append(firstTime);
      renderMedicines();
      announce("Medicamento salvo. Ative as notificações para receber alertas do navegador.");
    });
  }

  const checkReminders = () => {
    if (medicines.length === 0) return;
    const now = new Date();
    const timeNow = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    const alreadySent = Object.fromEntries(
      Object.entries(readStored(storageKeys.reminders, {})).filter(([key]) =>
        key.startsWith(`${today}:`),
      ),
    );
    medicines.forEach((medicine) => {
      medicine.times.forEach((time) => {
        if (time > timeNow) return;
        const [hours, minutes] = time.split(":").map(Number);
        const scheduledTime = new Date(now);
        scheduledTime.setHours(hours, minutes, 0, 0);
        const elapsed = now.getTime() - scheduledTime.getTime();
        if (elapsed > 120000) return;
        const reminderId = `${today}:${medicine.id}:${time}`;
        if (alreadySent[reminderId]) return;
        alreadySent[reminderId] = true;
        announce(`Hora de tomar ${medicine.name}${medicine.dosage ? ` — ${medicine.dosage}` : ""}.`);
        if ("Notification" in window && Notification.permission === "granted") {
          new Notification("Lembrete CUIDA+", {
            body: `Hora de tomar ${medicine.name}${medicine.dosage ? ` — ${medicine.dosage}` : ""}.`,
            tag: reminderId,
          });
        }
      });
    });
    saveStored(storageKeys.reminders, alreadySent);
  };

  document.querySelector("#enableMedicineNotifications")?.addEventListener("click", async () => {
    if (!("Notification" in window)) {
      announce("Este navegador não oferece notificações. O lembrete aparece enquanto esta página estiver aberta.");
      return;
    }
    const permission = await Notification.requestPermission();
    announce(permission === "granted"
      ? "Notificações ativadas para este navegador."
      : "Permissão não concedida. Os alertas aparecerão somente nesta página aberta.");
  });

  if (medicineList) {
    renderMedicines();
    checkReminders();
    window.setInterval(checkReminders, 20000);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) checkReminders();
    });
  }

  const loginForm = document.querySelector("#loginForm");
  if (loginForm) {
    if (profile) {
      const message = document.querySelector("#loginMessage");
      if (message) message.textContent = `Você já está conectado como ${profile.email}.`;
    }
    loginForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const data = new FormData(loginForm);
      const email = String(data.get("email")).trim();
      const name = String(data.get("name")).trim() || email.split("@")[0];
      profile = { name, email };
      saveStored(storageKeys.profile, profile);
      renderAccount();
      window.location.assign("profile.html");
    });
  }

  const profileForm = document.querySelector("#profileForm");
  if (profileForm) {
    const nameInput = profileForm.elements.namedItem("name");
    const emailInput = profileForm.elements.namedItem("email");
    if (profile) {
      nameInput.value = profile.name || "";
      emailInput.value = profile.email || "";
    }
    profileForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const data = new FormData(profileForm);
      profile = {
        name: String(data.get("name")).trim(),
        email: String(data.get("email")).trim(),
      };
      saveStored(storageKeys.profile, profile);
      renderAccount();
      announce("Seus dados foram atualizados neste navegador.");
    });
    document.querySelector("#logoutButton")?.addEventListener("click", () => {
      window.localStorage.removeItem(storageKeys.profile);
      window.location.assign("login.html");
    });
  }
});
