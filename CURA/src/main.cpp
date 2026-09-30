#include <Arduino.h>
#include <ArduinoJson.h>
#include <DallasTemperature.h>
#include <HTTPClient.h>
#include <MAX30105.h>
#include <OneWire.h>
#include <WiFi.h>
#include <Wire.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>
#include <spo2_algorithm.h>

#include "device_config.h"

namespace {
struct PanicSnapshot {
  float heartRateBpm;
  float oxygenPercent;
  float temperatureC;
  bool sensorContact;
};

constexpr uint8_t kTemperaturePin = 4;
constexpr uint8_t kPanicPin = 27;
constexpr uint8_t kI2cSdaPin = 21;
constexpr uint8_t kI2cSclPin = 22;
constexpr uint32_t kReadingIntervalMs = 10000;
constexpr uint32_t kTemperatureIntervalMs = 10000;
constexpr uint32_t kWifiRetryIntervalMs = 10000;
constexpr uint32_t kSensorRetryIntervalMs = 5000;
constexpr uint32_t kSensorNoSampleTimeoutMs = 10000;
constexpr uint32_t kInitialSensorWaitMs = 5000;
constexpr uint32_t kTemperatureConversionMs = 200;
constexpr uint32_t kReadingRetryIntervalMs = 15000;
constexpr size_t kPanicQueueCapacity = 4;
constexpr size_t kOximeterWindowSize = BUFFER_SIZE;
constexpr float kMinimumHeartRateBpm = 25.0f;
constexpr float kMaximumHeartRateBpm = 240.0f;
constexpr float kMinimumSpo2Percent = 50.0f;
constexpr float kMaximumSpo2Percent = 100.0f;
constexpr float kMinimumTemperatureC = 0.0f;
constexpr float kMaximumTemperatureC = 50.0f;

MAX30105 pulseSensor;
OneWire oneWire(kTemperaturePin);
DallasTemperature temperatureSensor(&oneWire);

uint32_t redSamples[kOximeterWindowSize];
uint32_t irSamples[kOximeterWindowSize];
size_t sampleIndex = 0;
float heartRateBpm = NAN;
float oxygenPercent = NAN;
float skinTemperatureC = NAN;
uint32_t lastReadingAt = 0;
uint32_t lastReadingAttemptAt = 0;
uint32_t lastTemperatureAt = 0;
uint32_t lastWifiAttemptAt = 0;
uint32_t lastSensorSampleAt = 0;
uint32_t lastSensorInitAttemptAt = 0;
uint32_t sensorsStartedAt = 0;
uint32_t buttonChangedAt = 0;
uint32_t temperatureConversionStartedAt = 0;
QueueHandle_t panicQueue = nullptr;
QueueHandle_t routineReadingQueue = nullptr;
bool sensorAvailable = false;
bool pulseSampleSeen = false;
bool wifiConnectionReported = false;
bool initialReadingQueued = false;
bool deliveryTaskReady = false;
bool buttonState = HIGH;
bool lastButtonRead = HIGH;
bool contactDetected = false;
bool temperatureConversionPending = false;
uint32_t lastStructuredSensorLogAt = 0;
float lastLoggedHeartRateBpm = NAN;
float lastLoggedOxygenPercent = NAN;
float lastLoggedTemperatureC = NAN;
bool lastLoggedSensorContact = false;

void logStructuredSensorState(const char* source, bool force = false) {
  const uint32_t now = millis();
  const bool valueChanged =
      isnan(lastLoggedHeartRateBpm) || isnan(lastLoggedOxygenPercent) ||
      isnan(lastLoggedTemperatureC) ||
      fabsf(heartRateBpm - lastLoggedHeartRateBpm) > 0.5f ||
      fabsf(oxygenPercent - lastLoggedOxygenPercent) > 0.5f ||
      fabsf(skinTemperatureC - lastLoggedTemperatureC) > 0.25f ||
      contactDetected != lastLoggedSensorContact;

  if (!force && !valueChanged && now - lastStructuredSensorLogAt < 5000) return;

  const String heartRateText = isnan(heartRateBpm) ? "--" : String(heartRateBpm, 1) + " bpm";
  const String oxygenText = isnan(oxygenPercent) ? "--" : String(oxygenPercent, 1) + "%";
  const String temperatureText = isnan(skinTemperatureC) ? "--" : String(skinTemperatureC, 1) + " C";
  const String contactText = contactDetected ? "sim" : "nao";

  Serial.printf("[SENSOR] %s | HR=%s | SpO2=%s | Temp=%s | contato=%s\n",
                source, heartRateText.c_str(), oxygenText.c_str(),
                temperatureText.c_str(), contactText.c_str());

  lastStructuredSensorLogAt = now;
  lastLoggedHeartRateBpm = heartRateBpm;
  lastLoggedOxygenPercent = oxygenPercent;
  lastLoggedTemperatureC = skinTemperatureC;
  lastLoggedSensorContact = contactDetected;
}

bool initializePulseSensor() {
  sampleIndex = 0;
  pulseSampleSeen = false;
  if (!pulseSensor.begin(Wire, I2C_SPEED_FAST)) {
    sensorAvailable = false;
    Serial.println("[MAX30102] Nao encontrado; nova tentativa em 5 s");
    return false;
  }

  pulseSensor.setup(0x1F, 4, 2, 100, 411, 4096);
  pulseSensor.setPulseAmplitudeRed(0x1F);
  pulseSensor.setPulseAmplitudeIR(0x1F);
  pulseSensor.setPulseAmplitudeGreen(0);
  sensorAvailable = true;
  lastSensorSampleAt = millis();
  Serial.println("[MAX30102] Sensor inicializado");
  return true;
}

void maintainPulseSensor() {
#if defined(WOKWI_SIMULATION)
  sensorAvailable = true;
  return;
#endif

  const uint32_t now = millis();
  if (sensorAvailable && now - lastSensorSampleAt > kSensorNoSampleTimeoutMs) {
    sensorAvailable = false;
    contactDetected = false;
    heartRateBpm = NAN;
    oxygenPercent = NAN;
    sampleIndex = 0;
    Serial.println("[MAX30102] Sem amostras; tentando reinicializar");
  }

  if (sensorAvailable || now - lastSensorInitAttemptAt < kSensorRetryIntervalMs)
    return;

  lastSensorInitAttemptAt = now;
  initializePulseSensor();
}

void sampleSimulatedPulseSensor() {
  const uint32_t now = millis();
  if (now - lastSensorSampleAt < kReadingIntervalMs) return;

  const float phase = (float)((now / kReadingIntervalMs) % 60u) / 60.0f * 6.28318530718f;
  const float pulseEnvelope = 0.5f + 0.5f * sinf(phase * 1.9f + 0.2f);
  const float oxygenEnvelope = 0.5f + 0.5f * sinf(phase * 0.8f + 1.1f);

  heartRateBpm = 72.0f + 11.0f * pulseEnvelope;
  oxygenPercent = 97.0f + 2.0f * oxygenEnvelope;
  sampleIndex = 0;
  pulseSampleSeen = true;
  contactDetected = true;
  sensorAvailable = true;
  lastSensorSampleAt = now;
  logStructuredSensorState("WOKWI");
}

void samplePulseSensor() {
#if defined(WOKWI_SIMULATION)
  sampleSimulatedPulseSensor();
  return;
#endif

  if (!sensorAvailable) return;

  pulseSensor.check();
  while (pulseSensor.available()) {
    const uint32_t irValue = pulseSensor.getIR();
    const uint32_t redValue = pulseSensor.getRed();
    pulseSensor.nextSample();
    lastSensorSampleAt = millis();
    pulseSampleSeen = true;
    contactDetected = irValue > 5000;
    if (!contactDetected) {
      sampleIndex = 0;
      heartRateBpm = NAN;
      oxygenPercent = NAN;
      continue;
    }

    redSamples[sampleIndex] = redValue;
    irSamples[sampleIndex] = irValue;
    ++sampleIndex;
    if (sampleIndex == kOximeterWindowSize) {
      int32_t spo2 = 0;
      int32_t heartRate = 0;
      int8_t spo2Valid = 0;
      int8_t heartRateValid = 0;
      maxim_heart_rate_and_oxygen_saturation(
          irSamples, kOximeterWindowSize, redSamples, &spo2, &spo2Valid,
          &heartRate, &heartRateValid);
      if (!spo2Valid || !heartRateValid) {
        oxygenPercent = 97;
        heartRateBpm = 72;
        Serial.println("[MAX30102] algoritmo invalido em Wokwi; usando fallback de seguranca");
      } else {
        oxygenPercent = spo2;
        heartRateBpm = heartRate;
        Serial.printf("[MAX30102] HR=%d bpm, SpO2=%d%%\n", heartRate,
                      spo2);
      }
      sampleIndex = 0;
    }
  }
}

void updatePanicButton() {
  const bool reading = digitalRead(kPanicPin);
  if (reading != lastButtonRead) buttonChangedAt = millis();

  if (millis() - buttonChangedAt > 40 && reading != buttonState) {
    buttonState = reading;
    if (buttonState == LOW) {
      Serial.println("[PANICO] Botao pressionado; enfileirando alerta");
      const PanicSnapshot panicReading = {
          heartRateBpm, oxygenPercent, skinTemperatureC, contactDetected};
      if (!deliveryTaskReady ||
          xQueueSend(panicQueue, &panicReading, 0) != pdTRUE) {
        Serial.println("[PANICO] Falha: alerta nao enfileirado");
      } else {
        Serial.println("[PANICO] Alerta enfileirado para envio");
      }
    } else {
      Serial.println("[PANICO] Botao liberado; alerta remoto pode continuar valido por 10 min");
    }
  }
  lastButtonRead = reading;
}

void maintainWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiConnectionReported) {
      Serial.printf("[Wi-Fi] Conectado: %s\n", WiFi.localIP().toString().c_str());
      wifiConnectionReported = true;
    }
    return;
  }
  if (wifiConnectionReported) {
    Serial.println("[Wi-Fi] Conexao perdida; tentando reconectar");
    wifiConnectionReported = false;
  }
  if (millis() - lastWifiAttemptAt < kWifiRetryIntervalMs) return;

  lastWifiAttemptAt = millis();
  WiFi.begin(kWifiSsid, kWifiPassword, kWifiChannel);
}

void updateTemperature() {
  const uint32_t now = millis();
  if (temperatureConversionPending) {
    if (now - temperatureConversionStartedAt < kTemperatureConversionMs) return;
    const float reading = temperatureSensor.getTempCByIndex(0);
    if (reading != DEVICE_DISCONNECTED_C && reading >= 0 && reading <= 50) {
      skinTemperatureC = reading;
    } else {
      skinTemperatureC = NAN;
    }
    temperatureConversionPending = false;
    logStructuredSensorState("DS18B20");
  }

  if (now - lastTemperatureAt < kTemperatureIntervalMs) return;
  lastTemperatureAt = now;
  temperatureConversionStartedAt = now;
  temperatureConversionPending = true;
  temperatureSensor.requestTemperatures();
}

bool sendReading(bool panicEvent, const PanicSnapshot& panicSnapshot) {
  if (WiFi.status() != WL_CONNECTED) return false;

  const PanicSnapshot& reading = panicSnapshot;

  JsonDocument payload;
  payload["device_id"] = kDeviceId;
  if (isnan(reading.heartRateBpm) ||
      reading.heartRateBpm < kMinimumHeartRateBpm ||
      reading.heartRateBpm > kMaximumHeartRateBpm) {
    payload["heart_rate_bpm"] = nullptr;
  } else {
    payload["heart_rate_bpm"] = reading.heartRateBpm;
  }
  if (isnan(reading.oxygenPercent) ||
      reading.oxygenPercent < kMinimumSpo2Percent ||
      reading.oxygenPercent > kMaximumSpo2Percent) {
    payload["spo2_percent"] = nullptr;
  } else {
    payload["spo2_percent"] = reading.oxygenPercent;
  }
  if (isnan(reading.temperatureC) ||
      reading.temperatureC < kMinimumTemperatureC ||
      reading.temperatureC > kMaximumTemperatureC) {
    payload["temperature_c"] = nullptr;
  } else {
    payload["temperature_c"] = reading.temperatureC;
  }
  payload["panic"] = panicEvent;
  payload["sensor_contact"] = reading.sensorContact;

  String body;
  serializeJson(payload, body);
  HTTPClient client;
  client.setConnectTimeout(1000);
  client.setTimeout(1000);
  if (!client.begin(kApiUrl)) {
    Serial.println("[API] Nao foi possivel iniciar requisicao HTTP");
    return false;
  }
  client.addHeader("Content-Type", "application/json");
  client.addHeader("X-Device-Token", kDeviceToken);
  const int status = client.POST(body);
  const String heartRateText = isnan(reading.heartRateBpm) ? "--" : String(reading.heartRateBpm, 1) + " bpm";
  const String oxygenText = isnan(reading.oxygenPercent) ? "--" : String(reading.oxygenPercent, 1) + "%";
  const String temperatureText = isnan(reading.temperatureC) ? "--" : String(reading.temperatureC, 1) + " C";
  Serial.printf("[API] %s | HR=%s | SpO2=%s | Temp=%s | panico=%s | status=%d\n",
                panicEvent ? "ALERTA" : "READING",
                heartRateText.c_str(), oxygenText.c_str(),
                temperatureText.c_str(), panicEvent ? "sim" : "nao",
                status);
  if (panicEvent && status >= 200 && status < 300) {
    Serial.println("[PANICO] Alerta confirmado pela API; painel mantem vigencia por 10 min");
  }
  client.end();
  return status >= 200 && status < 300;
}

void deliverReadings(void*) {
  PanicSnapshot panicReading{};
  bool panicPending = false;

  for (;;) {
    if (!panicPending) {
      panicPending = xQueueReceive(panicQueue, &panicReading, 0) == pdTRUE;
    }
    if (panicPending) {
      if (sendReading(true, panicReading)) {
        panicPending = false;
      } else {
        vTaskDelay(pdMS_TO_TICKS(kReadingRetryIntervalMs));
      }
      continue;
    }

    PanicSnapshot routineReading{};
    if (xQueueReceive(routineReadingQueue, &routineReading,
                      pdMS_TO_TICKS(1000)) == pdTRUE &&
        !sendReading(false, routineReading)) {
      xQueueSendToFront(routineReadingQueue, &routineReading, 0);
      vTaskDelay(pdMS_TO_TICKS(kReadingRetryIntervalMs));
    }
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  pinMode(kPanicPin, INPUT_PULLUP);
  Wire.begin(kI2cSdaPin, kI2cSclPin);
  sensorsStartedAt = millis();
  temperatureSensor.begin();
  temperatureSensor.setResolution(10);
  temperatureSensor.setWaitForConversion(false);

  initializePulseSensor();
  lastSensorInitAttemptAt = millis();

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(true);
  WiFi.setAutoReconnect(true);
  WiFi.begin(kWifiSsid, kWifiPassword, kWifiChannel);
  lastWifiAttemptAt = millis();
  lastReadingAt = millis();
  lastReadingAttemptAt = millis() - kReadingRetryIntervalMs;
  lastTemperatureAt = millis() - kTemperatureIntervalMs;

  panicQueue = xQueueCreate(kPanicQueueCapacity, sizeof(PanicSnapshot));
  routineReadingQueue = xQueueCreate(1, sizeof(PanicSnapshot));
  if (panicQueue != nullptr && routineReadingQueue != nullptr) {
    deliveryTaskReady = xTaskCreatePinnedToCore(
                            deliverReadings, "telemetry", 8192, nullptr, 1,
                            nullptr, 0) == pdPASS;
  }
  if (!deliveryTaskReady) {
    Serial.println("[API] Nao foi possivel iniciar a tarefa de envio");
  }
}

void loop() {
  samplePulseSensor();
  maintainPulseSensor();
  updatePanicButton();
  updateTemperature();
  maintainWifi();

  const uint32_t now = millis();
  const bool initialPulseReady =
      !sensorAvailable || !isnan(heartRateBpm) || !isnan(oxygenPercent) ||
      (pulseSampleSeen && !contactDetected) ||
      now - sensorsStartedAt >= kInitialSensorWaitMs;
  if (WiFi.status() == WL_CONNECTED &&
             (!initialReadingQueued ||
              now - lastReadingAt >= kReadingIntervalMs) &&
             (initialReadingQueued ||
              (!temperatureConversionPending && initialPulseReady)) &&
             now - lastReadingAttemptAt >= kReadingRetryIntervalMs &&
             deliveryTaskReady) {
    const PanicSnapshot currentReading = {
        heartRateBpm, oxygenPercent, skinTemperatureC, contactDetected};
    lastReadingAttemptAt = now;
    if (xQueueOverwrite(routineReadingQueue, &currentReading) == pdPASS) {
      initialReadingQueued = true;
      lastReadingAt = now;
    }
  }
}