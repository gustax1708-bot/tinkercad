(function () {
	const configuredBaseUrl = document.documentElement.dataset.apiBase || window.CUIDA_API_URL || 'http://localhost:8000';
	const apiBaseUrl = configuredBaseUrl.replace(/\/$/, '');

	const formatValue = (value, suffix = '') => value == null ? '--' : `${value}${suffix}`;

	const setText = (selector, value) => {
		document.querySelectorAll(selector).forEach((element) => {
			element.textContent = value;
		});
	};

	const formatTime = (value) => {
		if (!value) return 'sem leitura';
		const date = new Date(value);
		return Number.isNaN(date.getTime()) ? value : date.toLocaleString('pt-BR');
	};

	const updateReading = (reading, latestPanic) => {
		if (!reading) {
			setText('[data-reading-status]', 'Aguardando dados da pulseira');
			setText('[data-reading-updated]', 'Nenhuma leitura recebida');
			return;
		}

		setText('[data-reading="temperature"]', formatValue(reading.temperature_c, ' °C'));
		setText('[data-reading="heart-rate"]', formatValue(reading.heart_rate_bpm, ' bpm'));
		setText('[data-reading="spo2"]', formatValue(reading.spo2_percent, '%'));
		setText('[data-reading="panic"]', reading.panic ? 'Ativo' : 'Inativo');
		setText('[data-reading-status]', reading.status === 'panico' ? 'Alerta manual ativo' :
			(reading.sensor_contact ? 'Pulseira conectada' : 'Sem contato com o sensor'));
		setText('[data-reading-updated]', `Recebido em ${formatTime(reading.received_at)}`);
		setText('[data-reading-trend]', reading.temperature_trend || 'estavel');
		setText('[data-reading-device]', reading.device_id || 'pulseira-01');

		const alertMessage = latestPanic && latestPanic.panic
			? `Alerta manual em ${formatTime(latestPanic.received_at)}`
			: 'Nenhum alerta manual registrado';
		setText('[data-reading-alert]', alertMessage);
	};

	const updateHistory = (readings) => {
		const log = document.querySelector('[data-reading-log]');
		if (!log || !readings.length) return;
		log.innerHTML = readings.slice(0, 4).map((reading) =>
			`<p><span>${formatTime(reading.received_at)}</span> ${reading.panic ? 'Alerta manual' : 'Leitura enviada'} · ${reading.status}</p>`
		).join('');
	};

	const refreshDeviceData = async () => {
		try {
			const [latestResponse, historyResponse] = await Promise.all([
				fetch(`${apiBaseUrl}/api/v1/latest`),
				fetch(`${apiBaseUrl}/api/v1/history`)
			]);
			if (!latestResponse.ok || !historyResponse.ok) throw new Error('API indisponivel');
			const latest = await latestResponse.json();
			const history = await historyResponse.json();
			updateReading(latest.reading, latest.latest_panic);
			updateHistory(history.readings || []);
			document.documentElement.dataset.apiStatus = 'online';
		} catch {
			setText('[data-reading-status]', 'API indisponivel');
			document.documentElement.dataset.apiStatus = 'offline';
		}
	};

	document.addEventListener('DOMContentLoaded', () => {
		refreshDeviceData();
		window.setInterval(refreshDeviceData, 10000);
	});
})();