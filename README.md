# CUIDA+ | Monitoramento remoto

Projeto integrado de firmware ESP32, simulação Wokwi, API Python e dashboard web. Este é o README único do repositório; instruções de interface, hardware, firmware, execução e testes ficam centralizadas aqui.

## Componentes

- Firmware PlatformIO para ESP32 DOIT DevKit v1.
- Sensor MAX30102 para frequência cardíaca e SpO2; MAX30205 para temperatura de contato.
- MPU6050 para movimento e sinalização experimental de possível queda; MAX17048 para carga e tensão da célula.
- Botão de pânico ligado ao GPIO27.
- API Python com persistência SQLite em `CURA/readings.sqlite3`.
- Dashboard responsivo em HTML, CSS e JavaScript, com página inicial em `docs/pages/index.html` e recursos em `docs/`.

## Páginas do dashboard

As páginas compartilham uma navegação fixa que conecta a Home, Medicamentos, Perfil, Login, Hardware, Firmware, Documentação e Bancada:

- `docs/pages/index.html`: página inicial com telemetria, estado dos sensores e histórico.
- `docs/pages/hardware.html`: componentes, ligações e diagnóstico da API.
- `docs/pages/firmware.html`: código, dependências e informações do firmware.
- `docs/pages/docs.html`: fluxo de operação e endpoints da API.
- `docs/pages/workbench.html`: resumo da bancada Wokwi.
- `docs/pages/medications.html`: cadastro local de medicamentos, doses e horários com lembretes no navegador.
- `docs/pages/login.html` e `docs/pages/profile.html`: telas demonstrativas de login e perfil, sem autenticação de servidor.

O botão flutuante de acessibilidade permite alternar tema claro/escuro, alto contraste, texto ampliado e movimento reduzido. Os dados de perfil e medicamentos ficam no armazenamento local do navegador. Os lembretes só funcionam enquanto a página estiver aberta; notificações do sistema dependem da permissão do navegador.

O acesso ao perfil e a ação de entrar/sair ficam nos ícones do canto superior direito. O rodapé da navegação identifica a conta ativa, e a saudação exibe o nome do usuário conectado.

## Iniciar site e API

O modo local pode ser usado em cada computador separadamente, inclusive no computador da escola: obtenha uma cópia deste repositório nesse computador, instale Python 3 e execute o launcher. O dashboard e a API usam apenas a biblioteca padrão do Python, sem instalação de pacotes adicionais.

### Passo a passo para outro colaborador

1. Aceite o convite de colaborador enviado pelo GitHub e entre na conta autorizada. Se o repositório estiver privado, essa autorização é necessária para cloná-lo.
2. Instale Python 3 e Git for Windows. Para conferir o Python, abra o PowerShell e execute:

   ```powershell
   py -3 --version
   ```

3. Baixe a versão mais recente da branch `main`. No PowerShell, escolha uma pasta de destino e execute:

   ```powershell
   cd $HOME\Documents
   git clone https://github.com/gustax1708-bot/tinkercad.git
   cd tinkercad
   ```

   Se o projeto já estiver nesse computador, atualize a cópia existente em vez de cloná-la novamente:

   ```powershell
   cd CAMINHO\PARA\tinkercad
   git switch main
   git pull origin main
   ```

4. Na pasta `tinkercad`, inicie o dashboard, a API e o banco SQLite:

   ```powershell
   py -3 tools/dev_services.py
   ```

   Mantenha esse terminal aberto e acesse `http://localhost:8080/` no navegador. O banco `CURA/readings.sqlite3` será criado localmente; os dados dessa máquina não são compartilhados com os outros colaboradores.

5. Para confirmar a API e o site, abra um segundo PowerShell, entre na pasta `tinkercad` e execute:

   ```powershell
   py -3 tools/dev_services.py --check
   ```

   O resultado esperado é `API: online` e `Site: online`. Para encerrar os serviços, volte ao terminal do launcher e pressione `Ctrl+C`.

Se as portas padrão estiverem ocupadas, use portas alternativas no mesmo terminal antes de iniciar:

```powershell
$env:SITE_PORT = "18080"
$env:API_PORT = "18000"
py -3 tools/dev_services.py
```

Nesse caso, abra `http://localhost:18080/`. O comando de verificação `--check` deve ser executado no terminal onde essas variáveis foram definidas.

Para apenas abrir o dashboard e testar a API com dados simulados, não é necessário instalar PlatformIO, Wokwi, Docker ou dependências Python adicionais. Para também compilar ou simular o firmware, instale o VS Code com as extensões **PlatformIO IDE** e **Wokwi**; a primeira compilação precisa de internet para baixar o toolchain e as bibliotecas. Na simulação, use **Wokwi: Start Simulator**. O envio de telemetria do Wokwi para a API local pode exigir o **Private IoT Gateway** e depender das regras da rede da escola.

No VS Code, abra a pasta do repositório e execute a tarefa **Iniciar CUIDA+ local**. Ou abra um terminal na pasta do projeto e execute:

```bash
# Windows
py -3 tools/dev_services.py

# Linux/macOS
python3 tools/dev_services.py
```

O launcher inicia ou reutiliza o dashboard e a API naquele computador:

| Serviço | Endereço | Uso |
| --- | --- | --- |
| Dashboard | `http://localhost:8080/` | Acesso local |
| API HTTP | `http://localhost:8000` | Dashboard e desenvolvimento local |

O dashboard usa HTTP local e encaminha `/api/v1/latest` e `/api/v1/history` para a API.
O banco SQLite fica em `CURA/readings.sqlite3` e mantém as leituras e alertas entre reinicializações do serviço nesse computador. Para iniciar sem conflito caso as portas padrão já estejam em uso, configure portas alternativas antes de executar:

```powershell
$env:SITE_PORT = "18080"
$env:API_PORT = "18000"
py -3 tools/dev_services.py
```

Nesse exemplo, abra `http://localhost:18080/`. Para encerrar, pressione `Ctrl+C` no terminal do launcher. O banco continua salvo localmente.

Confirme que ambos os serviços estão respondendo com `py -3 tools/dev_services.py --check`. A verificação mostra a API como online somente se o endpoint de saúde confirmar que o SQLite está acessível.

## Publicar o dashboard na internet

O GitHub Actions publica automaticamente os arquivos estáticos de `docs/` no GitHub Pages a cada atualização enviada para `main`. Para ativar a publicação, no GitHub abra **Settings → Pages** e selecione **GitHub Actions** em **Build and deployment → Source**. Depois, acompanhe a execução em **Actions**. O endereço do site é `https://gustax1708-bot.github.io/tinkercad/`; a página inicial encaminha para o dashboard.

Após a publicação, qualquer pessoa com o endereço pode abrir a versão mais recente em computadores diferentes. Uma atualização aparece depois que o workflow de publicação termina.

O Pages hospeda apenas o frontend estático: a API Python, o banco SQLite, as leituras ao vivo e as ações de alerta continuam disponíveis somente quando a API local está em execução. O login demonstrativo, perfil, preferências e medicamentos são armazenados no navegador de cada dispositivo e não são sincronizados entre máquinas. Não use dados pessoais ou médicos reais neste protótipo.

Por padrão, cada computador executa sua própria cópia do dashboard, API e banco SQLite, e a API escuta apenas em `127.0.0.1`. Para usar uma placa física na mesma rede Wi-Fi ou conectar o Wokwi pelo **Private IoT Gateway**, inicie a API em modo de rede local. Isso não publica o dashboard nem a API na internet:

```powershell
# Gere um token aleatório forte e mantenha-o privado.
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$token = [BitConverter]::ToString($bytes).Replace("-", "").ToLowerInvariant()
$token

# Use o mesmo token no firmware e na API.
$env:API_HOST = "0.0.0.0"
$env:DEVICE_TOKEN = $token
py -3 tools/dev_services.py
```

Copie esse token para `DEVICE_API_TOKEN` em `CURA/include/secrets.h`. Para a placa física, configure `DEVICE_API_URL` com o IPv4 do computador que está rodando a API, por exemplo `http://192.168.1.25:8000/api/v1/readings` (descubra o endereço com `ipconfig` no Windows). A placa e o computador precisam estar na mesma rede local; permita conexões TCP de entrada na porta `8000` somente no perfil de rede privada, se o firewall solicitar. Não crie encaminhamento de portas no roteador nem libere a porta para redes públicas.

Para Wokwi remoto, use o **Private IoT Gateway** no computador que executa a API. O firmware simulado já envia para `host.wokwi.internal:8000`; o gateway precisa estar ativo e autorizado a acessar o serviço local. Configure o mesmo `DEVICE_API_TOKEN` no `secrets.h` antes de iniciar a simulação. Redes escolares podem bloquear conexões entre dispositivos ou o gateway; nesse caso, a política de rede precisa permitir o tráfego local.

O servidor do dashboard continua restrito ao próprio computador em `127.0.0.1:8080`. A API, quando configurada para aceitar a rede, valida o token em todas as rotas de telemetria e recusa iniciar com o token padrão ou com menos de 32 caracteres. O servidor web redireciona a raiz para `docs/pages/index.html` e entrega os arquivos estáticos de `docs/`; o proxy do dashboard encaminha o token sem expô-lo ao JavaScript. O CORS permanece limitado a `http://localhost:8080`.

## Configurar o firmware

Crie `CURA/include/secrets.h` a partir do exemplo e configure SSID, senha, URL e um token aleatório próprio:

```bash
cd CURA
cp include/secrets.example.h include/secrets.h
```

`secrets.h` é ignorado pelo Git. No modo padrão, a API aceita somente conexões do computador local. Para receber telemetria da placa ou do Wokwi remoto, use o modo de rede local descrito acima e configure o token correspondente em `secrets.h`. Sem esse arquivo, o firmware usa o token demonstrativo `dev-token`, que só funciona no modo padrão local.

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

## Simulação Wokwi

O firmware e o diagrama continuam disponíveis para compilação e simulação. Para enviar telemetria de uma simulação remota, inicie a API em modo de rede local, configure o token em `CURA/include/secrets.h` e conecte o **Private IoT Gateway** no computador que hospeda a API, conforme descrito acima. Sem esse gateway, a simulação ainda pode ser compilada e executada, mas não alcança a API do computador.

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

Os testes de API executam cenários simulados reproduzíveis de leitura normal, falta de contato, queda com sinal repetido, pânico, reconhecimento e resolução de alertas. Eles usam um banco temporário e não alteram `CURA/readings.sqlite3`. Para o cenário interativo do MPU6050 no simulador, use `CURA/fall_detection.scenario.yaml`.

A API oferece `POST /api/v1/readings`, `GET /api/v1/latest`, `GET /api/v1/history` e `GET /api/v1/health`. Alertas podem ser reconhecidos ou resolvidos com `POST /api/v1/alerts/{id}/acknowledge` e `POST /api/v1/alerts/{id}/resolve`. Os endpoints de leitura, histórico e ações de alerta também são acessíveis pelo proxy do dashboard na mesma origem.

No serviço integrado, confira a disponibilidade da API, do banco e dos arquivos do dashboard com:

```powershell
py -3 tools/dev_services.py --check
```

Para executar apenas a API, configure o token correspondente ao firmware e inicie o servidor a partir de `CURA/`:

```bash
export DEVICE_TOKEN=dev-token
python3 api.py
```

## Limites de uso

Este protótipo funciona em simulação e não é um dispositivo médico. Pulso, saturação, temperatura de contato, detecção de quedas e alertas não têm validação clínica. Os avisos do dashboard servem somente para testar o fluxo de software e não devem orientar diagnóstico, tratamento ou resposta a emergências.
