# CUIDA+ | Monitoramento remoto

Projeto integrado de firmware ESP32, simulação Wokwi, API Python e dashboard web. Este é o README único do repositório; instruções de interface, hardware, firmware, execução e testes ficam centralizadas aqui.

## Componentes

- Firmware PlatformIO para ESP32 DOIT DevKit v1.
- Sensor MAX30102 para frequência cardíaca e SpO2; MAX30205 para temperatura de contato.
- MPU6050 para movimento e sinalização experimental de possível queda; MAX17048 para carga e tensão da célula.
- Botão de pânico ligado ao GPIO27.
- API Python com persistência SQLite em `CURA/readings.sqlite3`.
- Dashboard responsivo em HTML, CSS e JavaScript, servido em `frontend/`.

## Páginas do dashboard

As páginas compartilham um menu que conecta a Home, Hardware, Firmware, Documentação e Bancada:

- `frontend/pages/index.html`: telemetria, estado dos sensores e histórico.
- `frontend/pages/hardware.html`: componentes, ligações e diagnóstico da API.
- `frontend/pages/firmware.html`: código, dependências e informações do firmware.
- `frontend/pages/docs.html`: fluxo de operação e endpoints da API.
- `frontend/pages/workbench.html`: resumo da bancada Wokwi.

## Publicar uma demonstração no Render

O repositório inclui `render.yaml` para publicar o dashboard e a API no mesmo serviço. No Render, crie um **Blueprint** conectado a este repositório e confirme a criação dos recursos descritos no arquivo. O serviço publica a página inicial em `/`, verifica a saúde em `/healthz` e grava o SQLite no disco persistente montado em `/var/data`.

O Render gera um `DEVICE_TOKEN` secreto automaticamente. As gravações de telemetria continuam exigindo esse token; as rotas de leitura usadas pelo dashboard são públicas. Portanto, use apenas dados fictícios nessa demonstração: qualquer pessoa com o endereço do serviço pode consultar as leituras. Não copie telemetria real para essa instância nem compartilhe o token.

O disco persistente está configurado no plano pago `starter` do Render. Consulte os preços e confirme os recursos antes de criar o serviço. A integração de uma placa física ou do Wokwi remoto não faz parte desta publicação de demonstração.

## Iniciar site e API

No VS Code, execute a tarefa **Iniciar CUIDA+ para Wokwi** ou inicie manualmente:

```bash
# Windows
py -3 tools/dev_services.py

# Linux/macOS
python3 tools/dev_services.py
```

O launcher cria ou reutiliza os serviços locais:

| Serviço | Endereço | Uso |
| --- | --- | --- |
| Dashboard | `http://localhost:8080/frontend/pages/index.html` | Acesso local |
| API HTTP | `http://localhost:8000` | Firmware e Wokwi |

O dashboard usa HTTP local e encaminha `/api/v1/latest` e `/api/v1/history` para a API. O firmware e o Wokwi também enviam telemetria à API HTTP na porta `8000`.

O dashboard e a API locais escutam somente em `127.0.0.1` por padrão. O servidor web entrega apenas arquivos de `frontend/`. Todas as rotas de telemetria locais exigem `X-Device-Token`; o proxy local encaminha o token sem expô-lo ao JavaScript. O CORS permite apenas `http://localhost:8080`, e as respostas incluem cabeçalhos contra sniffing e incorporação em frames.

O token padrão `dev-token` serve somente para desenvolvimento local. Para Wokwi via gateway ou placa física, habilite a interface de rede explicitamente com `API_HOST=0.0.0.0`, defina um token aleatório próprio em `DEVICE_TOKEN`, copie o mesmo valor para `CURA/include/secrets.h` e limite a porta 8000 no firewall à rede/dispositivo confiável. Nunca encaminhe essa porta à internet. Não abra a porta 8080 no firewall.

**Limites de segurança:** a demonstração pública no Render usa HTTPS fornecido pela plataforma, mas não tem login individual: as rotas de leitura são públicas. Ela não é adequada para dados biométricos reais ou para acesso remoto da equipe. Isso exige, no mínimo, autenticação e autorização por usuário, gestão de tokens por dispositivo e os controles de consentimento e retenção exigidos para dados pessoais sensíveis pela LGPD.

## Configurar o firmware

Crie `CURA/include/secrets.h` a partir do exemplo e configure SSID, senha, URL e um token aleatório próprio:

```bash
cd CURA
cp include/secrets.example.h include/secrets.h
```

`secrets.h` é ignorado pelo Git. Para uma placa física, a URL deve apontar para o IPv4 do computador que executa a API, não para `localhost`; permita conexões de entrada na porta `8000` somente na rede privada necessária. No Wokwi, se `secrets.h` existir, o firmware usa o mesmo `DEVICE_API_TOKEN`; sem ele, usa o token demonstrativo `dev-token`.

### Ligações

| Componente | Ligação ao ESP32 DOIT |
| --- | --- |
| MAX30102, MAX30205, MPU6050, MAX17048 SDA | GPIO21 (barramento compartilhado) |
| MAX30102, MAX30205, MPU6050, MAX17048 SCL | GPIO22 (barramento compartilhado) |
| Sensores I2C VCC | 3V3, conforme o breakout |
| Sensores I2C GND | GND comum |
| MAX30102 | Endereço I2C 0x57 |
| MAX30205 | Endereço I2C 0x48 |
| MPU6050 | Endereço I2C 0x68 (AD0 em GND) |
| MAX17048 | Endereço I2C 0x36; medir diretamente a célula 1S |
| Botão, contato 1 | GPIO27 |
| Botão, contato 2 | GND |

O botão usa o pull-up interno do ESP32. Ligue os dispositivos I2C em 3,3 V, com terra comum e apenas um conjunto de resistores pull-up no barramento. O MAX30102 deve ser um breakout compatível com 3,3 V. O firmware evita usar GPIO15 para não interferir na configuração de boot do ESP32.

### Alimentação por bateria

A meta inicial é 12 horas usando uma célula LiPo 1S protegida de 5.000 mAh. Use um módulo de carga com power-path, como um projeto baseado no MCP73871, e um conversor elevador regulado para 5 V, dimensionado para os picos de corrente do Wi-Fi do ESP32. Ligue a saída de 5 V ao pino VIN/5V do DevKit; nunca conecte a célula diretamente ao pino 3V3. Inclua chave e proteção contra curto-circuito, e confirme no módulo de carga que a saída para a carga é apropriada durante a recarga.

O MAX17048 deve medir a célula, não a saída de 5 V do conversor. Os 12 h são uma estimativa de projeto, não uma garantia: meça a corrente média com Wi-Fi, sensores e conversor ativos, incluindo os picos de transmissão, antes de escolher a bateria final. Não use a pulseira como dispositivo médico nem deixe a célula carregando sem supervisão.

## Telemetria e alerta

- O firmware amostra o MAX30102 continuamente e envia telemetria de rotina a cada 10 segundos.
- A temperatura MAX30205 é consultada a cada 10 segundos.
- O MAX17048 informa tensão e carga estimada a cada 10 segundos, sincronizado com a telemetria do dashboard.
- O MPU6050 é amostrado a cada 100 ms; possível queda exige queda livre, impacto e imobilidade sustentada e precisa de calibração no dispositivo final.
- Envios não confirmados são tentados novamente após 15 segundos.
- Ao pressionar o botão, o firmware enfileira um evento de pânico; a fila comporta até quatro eventos em RAM e é perdida se o ESP32 reiniciar.
- O alerta confirmado permanece vigente no painel por 10 minutos. O botão físico é momentâneo; sua liberação não encerra o alerta remoto.
- O dashboard consulta a API a cada 10 segundos.

## Executar no Wokwi

O padrão seguro mantém a API em `127.0.0.1`, inacessível ao Wokwi e a outros dispositivos da LAN. Para usar o **Wokwi Private IoT Gateway**, pare a tarefa local e inicie uma sessão do PowerShell com um token exclusivo para desenvolvimento. Mantenha a porta 8000 bloqueada para redes não confiáveis:

```powershell
$env:API_HOST = "0.0.0.0"
$env:DEVICE_TOKEN = "seu-token-aleatorio-de-desenvolvimento"
py -3 tools/dev_services.py
```

Use o mesmo token em `CURA/include/secrets.h` (o firmware Wokwi lê esse arquivo quando existe). O firmware simulado usa `host.wokwi.internal` para alcançar a API; o gateway público não encaminha o POST para o servidor local. Não reutilize o token de desenvolvimento em uma implantação real.

Compile o firmware e o chip customizado a partir de `CURA/`:

```bash
pio run -e wokwi
docker run --rm -v "$PWD":/workspace -w /workspace \
	wokwi/builder-clang-wasm make build-chip
```

Depois, use **Wokwi: Start Simulator** no VS Code. Os artefatos gerados são `CURA/.pio/build/wokwi/firmware.bin`, `CURA/Sensor_Saturacao.chip.wasm`, `CURA/MAX30205.chip.wasm` e `CURA/MAX17048.chip.wasm`. O MAX30102 simulado usa 100 Hz com média de quatro amostras, resultando em 25 amostras por segundo.

Os controles customizados ajustam frequência cardíaca (40-180 bpm), SpO2 (80-100%), temperatura MAX30205 (0-50 °C) e carga simulada da bateria (0-100%). O MPU6050 pode ser ajustado pelos atributos de aceleração do diagrama. Esses controles são apenas simulação; a carga no Wokwi não estima consumo nem comprova autonomia.

Para testar a heurística de queda com Wokwi CLI e `WOKWI_CLI_TOKEN` configurado, execute de `CURA/`:

```bash
wokwi-cli . --scenario fall_detection.scenario.yaml
```

O cenário aplica queda livre (`accelZ=0`), impacto (`accelZ=3`) e repouso (`accelZ=1`) e espera o log serial de possível queda. Sem CLI, repita essa sequência no controle do MPU6050 e aguarde cerca de 9 segundos após o impacto.

Se PlatformIO não estiver disponível no ambiente:

```bash
docker run --rm -v "$PWD":/workspace -w /workspace \
	python:3.12-slim sh -lc \
	'python -m pip install --no-cache-dir platformio && pio run -e wokwi'
```

## Compilar e testar

Com PlatformIO instalado, a partir de `CURA/`:

```bash
pio run -e esp32doit-devkit-v1
pio run -e esp32doit-devkit-v1 -t upload
pio run -e wokwi

# Windows
py -3 -m unittest discover -s test -v

# Linux/macOS
python3 -m unittest discover -s test -v
```

A API oferece `POST /api/v1/readings`, `GET /api/v1/latest` e `GET /api/v1/history`. Os endpoints de leitura e histórico também são acessíveis pelo proxy do dashboard na mesma origem.

Para executar apenas a API, configure o token correspondente ao firmware e inicie o servidor a partir de `CURA/`:

```bash
export DEVICE_TOKEN=dev-token
python3 api.py
```

## Limites de uso

Este protótipo não é um dispositivo médico. Pulso, saturação, temperatura de contato e detecção de quedas não têm validação clínica.
