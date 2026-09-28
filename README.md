# CUIDA+ Dashboard

Dashboard em HTML, CSS e JavaScript conectado à pulseira do projeto `CURA`. A interface consulta a API Python para exibir telemetria real, alertas manuais e histórico de leituras.

## Visão geral

Este projeto simula uma interface administrativa para um sistema embarcado de monitoramento ambiental, com:

- painel de visão geral do projeto com telemetria da pulseira;
- página de hardware com componentes e diagnósticos;
- página de firmware com código, releases e dependências;
- navegação lateral, ações rápidas e sistema de notificações via toast;
- layout responsivo para desktop, tablet e mobile.

## Tecnologias

- HTML5
- CSS3
- JavaScript vanilla com cliente compartilhado em `frontend/assets/js/api.js`;
- Lucide Icons via CDN
- Google Fonts

## Estrutura do projeto

```text
/
├── frontend/
│   ├── pages/
│   │   ├── home.html
│   │   ├── hardware.html
│   │   └── firmware.html
│   └── assets/
│       ├── css/
│       │   ├── home.css
│       │   ├── hardware.css
│       │   └── firmware.css
│       └── js/
│           ├── api.js
│           ├── home.js
│           ├── hardware.js
│           └── firmware.js
├── CURA/
│   ├── api.py
│   ├── src/
│   ├── include/
│   └── test/
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
python3 -m http.server 8080
```

3. Em outro terminal, inicie a API:

```bash
cd /workspaces/tinkercad/CURA
export DEVICE_TOKEN=dev-token
python3 api.py
```

4. Acesse no navegador:

```text
http://localhost:8080/frontend/pages/home.html
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

O site usa `http://localhost:8000` como API quando aberto em um servidor separado. Para outro endereço, defina `window.CUIDA_API_URL` antes de `frontend/assets/js/api.js` ou use `data-api-base` no elemento `<html>`. A API permite CORS por padrão; em rede compartilhada, restrinja `API_CORS_ORIGIN` ao endereço do site.

## Autor

Projeto de interface para demonstração de sistema embarcado de monitoramento ambiental.

