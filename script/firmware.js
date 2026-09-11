document.addEventListener('DOMContentLoaded', () => {
	const toast = document.querySelector('#toast');

	const showToast = (message) => {
		toast.querySelector('span').textContent = message;
		toast.classList.add('show');
		window.setTimeout(() => toast.classList.remove('show'), 3000);
	};

	document.querySelector('#copyCodeButton')?.addEventListener('click', () => showToast('Código do firmware copiado para a área de transferência.'));
	document.querySelector('#releaseButton')?.addEventListener('click', () => showToast('Formulário de nova release pronto para preencher.'));
	document.querySelector('#viewDependenciesButton')?.addEventListener('click', () => showToast('Todas as dependências estão instaladas e atualizadas.'));
});
