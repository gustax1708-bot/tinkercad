document.addEventListener('DOMContentLoaded', () => {
	const toast = document.querySelector('#toast');

	const showToast = (message) => {
		if (!toast) return;
		const toastText = toast.querySelector('span');
		if (toastText) toastText.textContent = message;
		toast.classList.add('show');
		window.setTimeout(() => toast.classList.remove('show'), 3000);
	};

	const copyCodeButton = document.querySelector('#copyCodeButton');
	if (copyCodeButton) {
		copyCodeButton.addEventListener('click', () => showToast('Código do firmware copiado para a área de transferência.'));
	}

	const releaseButton = document.querySelector('#releaseButton');
	if (releaseButton) {
		releaseButton.addEventListener('click', () => showToast('Formulário de nova release pronto para preencher.'));
	}

	const viewDependenciesButton = document.querySelector('#viewDependenciesButton');
	if (viewDependenciesButton) {
		viewDependenciesButton.addEventListener('click', () => showToast('Todas as dependências estão instaladas e atualizadas.'));
	}
});
