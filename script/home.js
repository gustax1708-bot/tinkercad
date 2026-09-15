document.addEventListener('DOMContentLoaded', () => {
	const sidebar = document.querySelector('#sidebar');
	const toast = document.querySelector('#toast');
	const menuButton = document.querySelector('#menuButton');
	let toastTimer;

	if (window.lucide && typeof window.lucide.createIcons === 'function') {
		window.lucide.createIcons();
	}

	const showToast = (message) => {
		if (!toast) return;
		const toastText = toast.querySelector('span');
		if (toastText) toastText.textContent = message;
		toast.classList.add('show');
		window.clearTimeout(toastTimer);
		toastTimer = window.setTimeout(() => toast.classList.remove('show'), 3000);
	};

	const shareProject = async () => {
		try {
			if (navigator.clipboard && window.location.href) {
				await navigator.clipboard.writeText(window.location.href);
			}
			showToast('Link do projeto copiado para a área de transferência.');
		} catch {
			showToast('Link público pronto para compartilhar.');
		}
	};

	if (menuButton && sidebar) {
		menuButton.addEventListener('click', () => sidebar.classList.toggle('open'));
	}

	document.querySelectorAll('#shareButton, #shareTopButton').forEach((button) => {
		button.addEventListener('click', shareProject);
	});

	const downloadButton = document.querySelector('#downloadButton');
	if (downloadButton) {
		downloadButton.addEventListener('click', () => showToast('Pacote do projeto preparado para exportação.'));
	}

	const uploadButton = document.querySelector('#uploadButton');
	if (uploadButton) {
		uploadButton.addEventListener('click', () => showToast('Área de arquivos pronta para receber um novo documento.'));
	}

	const openWorkbench = document.querySelector('#openWorkbench');
	if (openWorkbench) {
		openWorkbench.addEventListener('click', () => showToast('Bancada de testes conectada ao ESP32.'));
	}

	const viewDocsButton = document.querySelector('#viewDocsButton');
	if (viewDocsButton) {
		viewDocsButton.addEventListener('click', () => showToast('A documentação completa está disponível no README.md.'));
	}

	document.querySelectorAll('.nav-item[data-section]').forEach((item) => {
		item.addEventListener('click', (event) => {
			const pageBySection = { overview: 'home.html', hardware: 'hardware.html', software: 'firmware.html' };
			const currentPage = window.location.pathname.split('/').pop() || 'home.html';
			const section = item.dataset.section;
			const targetPage = pageBySection[section];
			const href = item.getAttribute('href');

			if (item.tagName === 'A' && href && !href.startsWith('#') && href !== currentPage) {
				return;
			}

			if (item.tagName === 'A' && href && href.startsWith('#')) {
				event.preventDefault();
			}

			const activeItem = document.querySelector('.nav-item.active');
			if (activeItem) activeItem.classList.remove('active');
			item.classList.add('active');

			const breadcrumb = document.querySelector('.breadcrumbs strong');
			const label = item.querySelector('span');
			if (breadcrumb && label) breadcrumb.textContent = label.textContent;

			if (targetPage && targetPage !== currentPage && item.tagName !== 'A') {
				window.location.assign(targetPage);
				return;
			}

			const target = document.querySelector(`#${section}`) || document.querySelector('#overview');
			if (target) {
				target.scrollIntoView({ behavior: 'smooth', block: 'start' });
			}
			if (sidebar) sidebar.classList.remove('open');
		});
	});

	document.querySelectorAll('.file-row').forEach((file) => {
		file.addEventListener('click', () => {
			const strong = file.querySelector('strong');
			showToast(strong ? `${strong.textContent} selecionado.` : 'Arquivo selecionado.');
		});
	});
});
