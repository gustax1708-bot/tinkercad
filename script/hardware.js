document.addEventListener('DOMContentLoaded', () => {
	const toast = document.querySelector('#toast');

	const showToast = (message) => {
		toast.querySelector('span').textContent = message;
		toast.classList.add('show');
		window.setTimeout(() => toast.classList.remove('show'), 3000);
	};

	document.querySelector('#runDiagnosticsButton')?.addEventListener('click', () => showToast('Diagnóstico concluído: todos os módulos respondendo.'));
	document.querySelectorAll('.hardware-doc').forEach((documentButton) => {
		documentButton.addEventListener('click', () => showToast(`${documentButton.querySelector('strong').textContent} selecionado.`));
	});
});
