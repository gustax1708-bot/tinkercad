# CUIDA+ | Monitoramento remoto

Projeto integrado de firmware ESP32, simulação Wokwi, API Python e dashboard web. Este é o README único do repositório; instruções de interface, hardware, firmware, execução e testes ficam centralizadas aqui.

## Componentes

- Firmware PlatformIO para ESP32 DOIT DevKit v1.
- Sensor MAX30102 para frequência cardíaca e SpO2; DS18B20 para temperatura de contato.
- Botão de pânico ligado ao GPIO27.
- API Python com persistência SQLite em `CURA/readings.sqlite3`.
- Dashboard responsivo em HTML, CSS e JavaScript, servido em `frontend/`.

## Páginas do dashboard

As páginas compartilham um menu que conecta a Home, Hardware, Firmware, Documentação e Bancada:

- `frontend/pages/home.html`: telemetria, estado dos sensores e histórico.
- `frontend/pages/hardware.html`: componentes, ligações e diagnóstico da API.
- `frontend/pages/firmware.html`: código, dependências e informações do firmware.
- `frontend/pages/docs.html`: fluxo de operação e endpoints da API.
- `frontend/pages/workbench.html`: resumo da bancada Wokwi.

## Iniciar site e API

No VS Code, execute a tarefa **Iniciar CUIDA+ para Wokwi** ou inicie manualmente:

```bash
python3 tools/dev_services.py
```

O launcher cria ou reutiliza os serviços locais:

| Serviço | Endereço | Uso |
| --- | --- | --- |
| Dashboard | `http://localhost:8080/frontend/pages/home.html` | Acesso local |
| API HTTP | `http://localhost:8000` | Firmware e Wokwi |

O dashboard usa HTTP local e encaminha `/api/v1/latest` e `/api/v1/history` para a API. O firmware e o Wokwi também enviam telemetria à API HTTP na porta `8000`.

O servidor web entrega apenas arquivos de `frontend/` e não expõe arquivos do banco, segredos ou metadados Git. A API usa um token de desenvolvimento por padrão e não deve ser exposta à internet. Antes de usar em uma rede compartilhada, defina um token próprio e restrinja `API_CORS_ORIGIN`.

## Configurar o firmware

Crie `CURA/include/secrets.h` a partir do exemplo e configure SSID, senha, URL e token:

```bash
cd CURA
cp include/secrets.example.h include/secrets.h
```

`secrets.h` é ignorado pelo Git. Para uma placa física, a URL deve apontar para o IPv4 do computador que executa a API, não para `localhost`; permita conexões de entrada na porta `8000` no firewall.

### Ligações

| Componente | Ligação ao ESP32 DOIT |
| --- | --- |
| MAX30102 SDA | GPIO21 |
| MAX30102 SCL | GPIO22 |
| MAX30102 VCC/VIN | 3V3, conforme o breakout |
| MAX30102 GND | GND |
| DS18B20 DQ | GPIO4 |
| DS18B20 VDD/GND | 3V3/GND |
| Resistor 4,7 kOhm | Entre DQ/GPIO4 e 3V3 |
| Botão, contato 1 | GPIO27 |
| Botão, contato 2 | GND |

O botão usa o pull-up interno do ESP32. O MAX30102 deve ser um breakout compatível com barramento I2C de 3,3 V; vários módulos já incluem resistores pull-up.
O firmware evita usar GPIO15 para não interferir na configuração de boot do ESP32.

## Telemetria e alerta

- O firmware amostra o MAX30102 continuamente e envia telemetria de rotina a cada 10 segundos.
- A temperatura DS18B20 é consultada a cada 10 segundos.
- Envios não confirmados são tentados novamente após 15 segundos.
- Ao pressionar o botão, o firmware enfileira um evento de pânico; a fila comporta até quatro eventos em RAM e é perdida se o ESP32 reiniciar.
- O alerta confirmado permanece vigente no painel por 10 minutos. O botão físico é momentâneo; sua liberação não encerra o alerta remoto.
- O dashboard consulta a API a cada 10 segundos.

## Executar no Wokwi

Inicie os serviços locais e habilite o **Wokwi Private IoT Gateway**. O firmware simulado usa `host.wokwi.internal` para alcançar a API local; o gateway público não encaminha o POST para o servidor local.

Compile o firmware e o chip customizado a partir de `CURA/`:

```bash
pio run -e wokwi
docker run --rm -v "$PWD":/workspace -w /workspace \
	wokwi/builder-clang-wasm make build-chip
```

Depois, use **Wokwi: Start Simulator** no VS Code. Os artefatos gerados são `CURA/.pio/build/wokwi/firmware.bin` e `CURA/Sensor_Saturacao.chip.wasm`. O MAX30102 simulado usa 100 Hz com média de quatro amostras, resultando em 25 amostras por segundo.

O chip customizado oferece controles de frequência cardíaca (40-180 bpm) e SpO2 (80-100%). Eles alteram as amostras I2C; após recompilar o chip, reinicie a simulação para carregar os controles.

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
python3 -m unittest discover -s test -v
```

A API oferece `POST /api/v1/readings`, `GET /api/v1/latest` e `GET /api/v1/history`. Os endpoints de leitura e histórico também são acessíveis pelo proxy do dashboard na mesma origem.

Para executar apenas a API, configure o token correspondente ao firmware e inicie o servidor a partir de `CURA/`:

```bash
export DEVICE_TOKEN=dev-token
python3 api.py
```

## Limites de uso

Este protótipo não é um dispositivo médico. O pulso e a saturação não têm calibração ou validação clínica; o DS18B20 mede temperatura de contato, não temperatura corporal clínica.

Para alimentação por bateria, use uma LiPo 1S protegida com carregador apropriado e regulação para VIN/5V do DevKit. Nunca conecte uma célula diretamente a 3V3 ou 5V; meça o consumo antes de uso prolongado.

