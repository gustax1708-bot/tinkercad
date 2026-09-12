document.addEventListener('DOMContentLoaded', () => {
	const sidebar = document.querySelector('#sidebar');
	const toast = document.querySelector('#toast');
	let toastTimer;

	lucide.createIcons();

	const showToast = (message) => {
		toast.querySelector('span').textContent = message;
		toast.classList.add('show');
		window.clearTimeout(toastTimer);
		toastTimer = window.setTimeout(() => toast.classList.remove('show'), 3000);
	};

	const shareProject = async () => {
		try {
			await navigator.clipboard.writeText(window.location.href);
			showToast('Link do projeto copiado para a área de transferência.');
		} catch {
			showToast('Link público pronto para compartilhar.');
		}
	};

	document.querySelector('#menuButton').addEventListener('click', () => sidebar.classList.toggle('open'));
	document.querySelectorAll('#shareButton, #shareTopButton').forEach((button) => button.addEventListener('click', shareProject));
	document.querySelector('#downloadButton').addEventListener('click', () => showToast('Pacote do projeto preparado para exportação.'));
	document.querySelector('#uploadButton').addEventListener('click', () => showToast('Área de arquivos pronta para receber um novo documento.'));
	document.querySelector('#openWorkbench').addEventListener('click', () => showToast('Bancada de testes conectada ao ESP32.'));
	document.querySelector('#helpButton').addEventListener('click', () => showToast('Consulte a documentação para entender cada módulo.'));
	document.querySelector('#viewDocsButton').addEventListener('click', () => showToast('A documentação completa está disponível no README.md.'));

	document.querySelectorAll('.nav-item[data-section]').forEach((item) => {
		item.addEventListener('click', () => {
			const pageBySection = { overview: 'home.html', hardware: 'hardware.html', software: 'firmware.html' };
			const currentPage = window.location.pathname.split('/').pop() || 'home.html';
			const targetPage = pageBySection[item.dataset.section];

			if (!item.getAttribute('href') && targetPage && targetPage !== currentPage) {
				window.location.assign(targetPage);
				return;
			}

			if (item.tagName === 'A' && !item.getAttribute('href').startsWith('#')) {
				return;
			}

			document.querySelector('.nav-item.active').classList.remove('active');
			item.classList.add('active');
			document.querySelector('.breadcrumbs strong').textContent = item.querySelector('span').textContent;
			const target = document.querySelector(`#${item.dataset.section}`) || document.querySelector('#overview');
			target.scrollIntoView({ behavior: 'smooth', block: 'start' });
			sidebar.classList.remove('open');
		});
	});

	document.querySelectorAll('.file-row').forEach((file) => {
		file.addEventListener('click', () => showToast(`${file.querySelector('strong').textContent} selecionado.`));
	});
});
