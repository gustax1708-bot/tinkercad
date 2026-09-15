document.addEventListener('DOMContentLoaded', () => {
	const toast = document.querySelector('#toast');

	const showToast = (message) => {
		if (!toast) return;
		const toastText = toast.querySelector('span');
		if (toastText) toastText.textContent = message;
		toast.classList.add('show');
		window.setTimeout(() => toast.classList.remove('show'), 3000);
	};

	const runDiagnosticsButton = document.querySelector('#runDiagnosticsButton');
	if (runDiagnosticsButton) {
		runDiagnosticsButton.addEventListener('click', () => showToast('Diagnóstico concluído: todos os módulos respondendo.'));
	}

	document.querySelectorAll('.hardware-doc').forEach((documentButton) => {
		const strong = documentButton.querySelector('strong');
		documentButton.addEventListener('click', () => showToast(strong ? `${strong.textContent} selecionado.` : 'Documento selecionado.'));
	});
});
