# CUIDA+ Dashboard

Dashboard em HTML, CSS e JavaScript conectado à pulseira do projeto `CURA`. A interface consulta a API Python para exibir telemetria real, alertas manuais e histórico de leituras.

## Visão geral

Este projeto integra o dashboard CUIDA+ à pulseira vestível e sua telemetria, com:

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
├── .github/
│   └── agents/
├── .vscode/
│   └── tasks.json
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
│   ├── Sensor_Saturacao.chip.c
│   ├── platformio.ini
│   ├── src/
│   ├── include/
│   └── test/
├── tools/
│   └── dev_services.py
├── README.md
└── .gitignore
```

## Como executar

Ao abrir o workspace no VS Code, aceite a tarefa automática **Iniciar CUIDA+ para Wokwi**. Ela mantém a API e o site ativos nas portas `8000` e `8080`; o servidor web entrega somente arquivos em `frontend/`, sem expor o banco, segredos ou metadados Git. Se os serviços seguros já estiverem ativos, a tarefa os reutiliza. Também pode iniciar manualmente:

```bash
cd /workspaces/tinkercad
python3 tools/dev_services.py
```

Abra o dashboard em:

```text
http://localhost:8080/frontend/pages/home.html
```

Com a API ativa e o Wokwi Private IoT Gateway habilitado, inicie ou reinicie a simulação. O firmware envia a primeira leitura assim que um sensor fornece dados e depois envia leituras regulares a cada 15 segundos; o dashboard consulta a API a cada 10 segundos e sinaliza leituras mais antigas que 45 segundos.

O terminal da tarefa mostra a inicialização e cada leitura recebida pela API. No terminal serial do Wokwi, acompanhe `[Wi-Fi] Conectado` e `[API] POST ... -> 201`; no dashboard, confira os valores e o horário da última leitura. O terminal da tarefa fica visível enquanto os serviços estiverem ativos.

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

O site servido por `tools/dev_services.py` consulta a API pela mesma origem, usando um proxy local para `/api/v1/latest` e `/api/v1/history`. Para hospedar frontend e API separadamente, defina `window.CUIDA_API_URL` antes de `frontend/assets/js/api.js` ou use `data-api-base` no elemento `<html>`. A API permite CORS por padrão para o ambiente local; restrinja `API_CORS_ORIGIN` e altere o token de desenvolvimento antes de usar em uma rede compartilhada.

## Autor

Projeto de interface para demonstração de sistema embarcado de monitoramento ambiental.

