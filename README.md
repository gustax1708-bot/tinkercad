# AgroSense Dashboard

Dashboard estático em HTML, CSS e JavaScript para apresentação de um projeto de monitoramento ambiental com páginas de visão geral, hardware e firmware.

## Visão geral

Este projeto simula uma interface administrativa para um sistema embarcado de monitoramento ambiental, com:

- painel de visão geral do projeto;
- página de hardware com componentes e diagnósticos;
- página de firmware com código, releases e dependências;
- navegação lateral, ações rápidas e sistema de notificações via toast;
- layout responsivo para desktop, tablet e mobile.

## Tecnologias

- HTML5
- CSS3
- JavaScript vanilla
- Lucide Icons via CDN
- Google Fonts

## Estrutura do projeto

```text
/
├── index/
│   ├── home.html
│   ├── hardware.html
│   └── firmware.html
├── style/
│   ├── home.css
│   ├── hardware.css
│   └── firmware.css
├── script/
│   ├── home.js
│   ├── hardware.js
│   └── firmware.js
├── README.md
└── .gitignore
```

## Como executar

1. Abra o projeto em um servidor local simples, por exemplo:
   - VS Code Live Server
   - Python HTTP Server

2. No terminal, execute:

```bash
cd /workspaces/tinkercad
python3 -m http.server 8000
```

3. Acesse no navegador:

```text
http://localhost:8000/index/home.html
```

## Páginas principais

### Home
Apresenta a visão geral do sistema, telemetria, saúde do sistema e registros do projeto.

### Hardware
Exibe inventário de componentes, sensores conectados, diagnóstico de energia e documentação técnica.

### Firmware
Mostra sketch atual, releases, monitor serial, dependências e estado do dispositivo.

## Funcionalidades

- navegação lateral com páginas internas;
- menu mobile para telas pequenas;
- ações de compartilhar e exportar;
- toast de feedback visual;
- layout com identidade visual consistente e profissional;
- página responsiva sem dependência de framework.

## Observações

O projeto foi desenvolvido como protótipo front-end, com foco em apresentação visual e interação básica. Ele não depende de backend nem de banco de dados.

## Autor

Projeto de interface para demonstração de sistema embarcado de monitoramento ambiental.

