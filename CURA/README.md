# Pulseira de monitoramento remoto

Projeto PlatformIO com ESP32 DOIT, MAX30102, DS18B20, botão de pânico, API Python e painel local. O firmware envia a primeira leitura quando um sensor entrega um valor e depois envia dados regularmente a cada 15 s. Ao clicar no botão, captura os valores disponíveis e enfileira um alerta manual até receber confirmação HTTP. A fila tem quatro eventos em RAM e se perde se o ESP32 reiniciar.

## Hardware e ligações

| Componente | Ligação ao ESP32 DOIT |
|---|---|
| MAX30102 SDA | GPIO21 |
| MAX30102 SCL | GPIO22 |
| MAX30102 VCC/VIN | 3V3, conforme o breakout |
| MAX30102 GND | GND |
| DS18B20 DQ | GPIO4 |
| DS18B20 VDD/GND | 3V3/GND |
| Resistor 4,7 kOhm | Entre DQ/GPIO4 e 3V3 |
| Botão, contato 1 | GPIO27 |
| Botão, contato 2 | GND |

O botão usa pull-up interno, sem resistor externo. O firmware evita GPIO15 para não interferir com a configuração de boot do ESP32. O MAX30102 deve ser um breakout que aceite 3,3 V no barramento I2C; diversos módulos já incluem pull-ups.

## Preparar Wi-Fi e API

Copie `include/secrets.example.h` para `include/secrets.h` e edite SSID, senha, URL e token. `secrets.h` é ignorado pelo Git. A URL precisa usar o IPv4 do computador servidor na rede local, não `localhost`; confirme também que o firewall permite conexões de entrada na porta 8000.

Para iniciar apenas a API, configure o mesmo token do firmware:

```bash
export DEVICE_TOKEN=dev-token
python3 api.py
```

O dashboard completo é servido na porta `8080` pelo launcher do workspace (`python3 ../tools/dev_services.py`, a partir de `CURA/`). A raiz da API na porta `8000` redireciona para ele. A API oferece `POST /api/v1/readings`, `GET /api/v1/latest` e `GET /api/v1/history`, e persiste em `readings.sqlite3` ao lado de `api.py`. A API é de demonstração, usa token de desenvolvimento por padrão e não deve ser exposta à internet.

## Compilar e carregar

```bash
pio run -e esp32doit-devkit-v1
pio run -e esp32doit-devkit-v1 -t upload
python3 -m unittest discover -s test -v
```

## Simular no Wokwi

Compile o firmware do alvo `wokwi` e o chip customizado com a imagem oficial do Wokwi:

```bash
pio run -e wokwi
docker run --rm -v "$PWD":/workspace -w /workspace wokwi/builder-clang-wasm make build-chip
```

Se `pio` não estiver instalado no ambiente local, compile o firmware pelo Docker:

```bash
docker run --rm -v "$PWD":/workspace -w /workspace \
	python:3.12-slim sh -lc \
	'python -m pip install --no-cache-dir platformio && pio run -e wokwi'
```

Os comandos geram `Sensor_Saturacao.chip.wasm` e `.pio/build/wokwi/firmware.bin`, os artefatos referenciados por `wokwi.toml`. Depois use `Wokwi: Start Simulator`. O MAX30102 está configurado a 100 Hz com média de 4 amostras, resultando em 25 amostras/s, como no exemplo oficial SparkFun/Maxim; o modelo customizado também produz amostras a 25 Hz.

O chip customizado oferece controles deslizantes para frequência cardíaca (40-180 bpm) e SpO2 (80-100%). Eles ajustam as amostras I2C simuladas; após recompilar o chip, reinicie a simulação para recarregar os controles.

Para que o ESP32 simulado envie dados à API local, o Wokwi Private IoT Gateway precisa estar instalado e habilitado; o endpoint usa `host.wokwi.internal`. Com o gateway público, a simulação de sensores ainda pode ser feita, mas o POST não alcança o servidor local.

## Limites e alimentação

O MAX30102 e o algoritmo não são dispositivos médicos. A saturação e o pulso não têm calibração nem validação clínica. O DS18B20 mede temperatura de contato e não temperatura corporal clínica.

Para protótipo alimentado por bateria, use LiPo 1S protegida com circuito de carga apropriado e regulador para o pino VIN/5V do DevKit. Nunca ligue uma célula diretamente a 3V3 ou 5V. A placa DOIT não é otimizada para longa autonomia; meça o consumo real antes de uso vestível prolongado.