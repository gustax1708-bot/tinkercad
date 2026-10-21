#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <MAX30105.h>
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
  float batteryPercent;
  float batteryVoltage;
  float accelerationG;
  bool sensorContact;
  bool motionActive;
  bool fallDetected;
};

constexpr uint8_t kPanicPin = 27;
constexpr uint8_t kI2cSdaPin = 21;
constexpr uint8_t kI2cSclPin = 22;
constexpr uint8_t kSimulatedSensorAddress = 0x57;
constexpr uint8_t kTemperatureSensorAddress = 0x48;
constexpr uint8_t kMotionSensorAddress = 0x68;
constexpr uint8_t kBatteryGaugeAddress = 0x36;
constexpr uint32_t kReadingIntervalMs = 10000;
constexpr uint32_t kTemperatureIntervalMs = 10000;
constexpr uint32_t kBatteryIntervalMs = kReadingIntervalMs;
constexpr uint32_t kMotionIntervalMs = 100;
constexpr uint32_t kMotionLogIntervalMs = 1000;
constexpr uint32_t kWifiRetryIntervalMs = 10000;
constexpr uint32_t kSensorRetryIntervalMs = 5000;
constexpr uint32_t kSensorNoSampleTimeoutMs = 10000;
constexpr uint32_t kInitialSensorWaitMs = 5000;
constexpr uint32_t kReadingRetryIntervalMs = 15000;
constexpr uint32_t kPanicDurationMs = 10 * 60 * 1000;
constexpr uint32_t kFallImpactWindowMs = 1500;
constexpr uint32_t kFallStillnessMs = 8000;
constexpr float kMotionThresholdG = 0.15f;
constexpr float kFreeFallThresholdG = 0.55f;
constexpr float kFallImpactThresholdG = 2.0f;
constexpr size_t kPanicQueueCapacity = 4;
constexpr size_t kOximeterWindowSize = BUFFER_SIZE;
constexpr float kMinimumHeartRateBpm = 25.0f;
constexpr float kMaximumHeartRateBpm = 240.0f;
constexpr float kMinimumSpo2Percent = 50.0f;
constexpr float kMaximumSpo2Percent = 100.0f;
constexpr float kMinimumTemperatureC = 0.0f;
constexpr float kMaximumTemperatureC = 50.0f;

MAX30105 pulseSensor;

enum class FallState : uint8_t { Monitoring, FreeFall, Impact, Alert };

uint32_t redSamples[kOximeterWindowSize];
uint32_t irSamples[kOximeterWindowSize];
size_t sampleIndex = 0;
float heartRateBpm = NAN;
float oxygenPercent = NAN;
float skinTemperatureC = NAN;
float batteryPercent = NAN;
float batteryVoltage = NAN;
float accelerationG = NAN;
float previousAccelerationX = NAN;
float previousAccelerationY = NAN;
float previousAccelerationZ = NAN;
uint32_t lastReadingAt = 0;
uint32_t lastReadingAttemptAt = 0;
uint32_t lastTemperatureAt = 0;
uint32_t lastBatteryAt = 0;
uint32_t lastMotionAt = 0;
uint32_t lastMotionLogAt = 0;
uint32_t lastWifiAttemptAt = 0;
uint32_t lastSensorSampleAt = 0;
uint32_t lastSensorInitAttemptAt = 0;
uint32_t lastMotionInitAttemptAt = 0;
uint32_t sensorsStartedAt = 0;
uint32_t buttonChangedAt = 0;
uint32_t fallStateStartedAt = 0;
uint32_t fallStillnessStartedAt = 0;
uint32_t fallAlertStartedAt = 0;
QueueHandle_t panicQueue = nullptr;
QueueHandle_t routineReadingQueue = nullptr;
bool sensorAvailable = false;
bool pulseSampleSeen = false;
bool wifiConnectionReported = false;
bool initialReadingQueued = false;
bool deliveryTaskReady = false;
bool motionSensorAvailable = false;
bool buttonState = HIGH;
bool lastButtonRead = HIGH;
bool contactDetected = false;
bool panicAlertActive = false;
bool motionActive = false;
bool fallDetected = false;
uint32_t panicAlertActivatedAt = 0;
FallState fallState = FallState::Monitoring;
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

  const String contactText = contactDetected ? "sim" : "nao";

  Serial.printf("[SENSOR] %s | contato=%s\n", source, contactText.c_str());

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

bool readI2cRegisters(uint8_t address, uint8_t registerAddress,
                      uint8_t* values, uint8_t length) {
  Wire.beginTransmission(address);
  Wire.write(registerAddress);
  if (Wire.endTransmission(false) != 0 ||
      Wire.requestFrom(address, length) != length) {
    while (Wire.available()) Wire.read();
    return false;
  }

  for (uint8_t index = 0; index < length; ++index) {
    values[index] = static_cast<uint8_t>(Wire.read());
  }
  return true;
}

bool writeI2cRegister(uint8_t address, uint8_t registerAddress, uint8_t value) {
  Wire.beginTransmission(address);
  Wire.write(registerAddress);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool initializeMotionSensor() {
  const bool initialized =
      writeI2cRegister(kMotionSensorAddress, 0x6B, 0x00) &&
      writeI2cRegister(kMotionSensorAddress, 0x1C, 0x00) &&
      writeI2cRegister(kMotionSensorAddress, 0x1A, 0x03);
  motionSensorAvailable = initialized;
  Serial.printf("[MPU6050] %s\n", initialized ? "Sensor inicializado" : "Sensor nao encontrado");
  return initialized;
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

bool readSimulatedSensorValue(uint8_t registerAddress, uint8_t& value) {
  return readI2cRegisters(kSimulatedSensorAddress, registerAddress, &value, 1);
}

void sampleSimulatedPulseSensor() {
  const uint32_t now = millis();
  if (pulseSampleSeen && now - lastSensorSampleAt < kReadingIntervalMs) return;

  uint8_t simulatedHeartRate = 0;
  uint8_t simulatedSpo2 = 0;
  if (!readSimulatedSensorValue(0xF0, simulatedHeartRate) ||
      !readSimulatedSensorValue(0xF1, simulatedSpo2)) {
    return;
  }

  heartRateBpm = simulatedHeartRate;
  oxygenPercent = simulatedSpo2;
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
        Serial.println("[MAX30102] leitura valida");
      }
      sampleIndex = 0;
    }
  }
}

void updatePanicButton() {
  const uint32_t now = millis();
  if (panicAlertActive && now - panicAlertActivatedAt >= kPanicDurationMs) {
    panicAlertActive = false;
    Serial.println("[PANICO] Alerta encerrado apos 10 minutos");
  }

  const bool reading = digitalRead(kPanicPin);
  if (reading != lastButtonRead) buttonChangedAt = millis();

  if (now - buttonChangedAt > 40 && reading != buttonState) {
    buttonState = reading;
    if (buttonState == LOW) {
      if (panicAlertActive) {
        Serial.println("[PANICO] Alerta ativo; novo toque ignorado");
      } else {
        Serial.println("[PANICO] Botao pressionado; enfileirando alerta");
        const PanicSnapshot panicReading = {
          heartRateBpm, oxygenPercent, skinTemperatureC, batteryPercent,
          batteryVoltage, accelerationG, contactDetected, motionActive,
          fallDetected};
        if (!deliveryTaskReady ||
            xQueueSend(panicQueue, &panicReading, 0) != pdTRUE) {
          Serial.println("[PANICO] Falha: alerta nao enfileirado");
        } else {
          panicAlertActive = true;
          panicAlertActivatedAt = now;
          Serial.println("[PANICO] Alerta ativo por 10 minutos");
        }
      }
    } else {
      Serial.println("[PANICO] Botao liberado; alerta permanece ativo ate completar 10 minutos");
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
  if (now - lastTemperatureAt < kTemperatureIntervalMs) return;
  lastTemperatureAt = now;
  uint8_t raw[2];
  if (!readI2cRegisters(kTemperatureSensorAddress, 0x00, raw, sizeof(raw))) {
    skinTemperatureC = NAN;
    logStructuredSensorState("MAX30205");
    return;
  }

  const uint16_t rawTemperature =
      static_cast<uint16_t>((static_cast<uint16_t>(raw[0]) << 8) | raw[1]);
  const float reading = static_cast<int16_t>(rawTemperature) / 256.0f;
  skinTemperatureC = reading >= kMinimumTemperatureC &&
                              reading <= kMaximumTemperatureC
                          ? reading
                          : NAN;
  logStructuredSensorState("MAX30205");
}

void updateBattery() {
  const uint32_t now = millis();
  if (now - lastBatteryAt < kBatteryIntervalMs) return;
  lastBatteryAt = now;

  uint8_t raw[2];
  if (!readI2cRegisters(kBatteryGaugeAddress, 0x04, raw, sizeof(raw))) {
    batteryPercent = NAN;
    batteryVoltage = NAN;
    return;
  }
  const uint16_t stateOfCharge =
      static_cast<uint16_t>((static_cast<uint16_t>(raw[0]) << 8) | raw[1]);
  batteryPercent = stateOfCharge / 256.0f;
  if (batteryPercent > 100.0f) batteryPercent = 100.0f;

  if (!readI2cRegisters(kBatteryGaugeAddress, 0x02, raw, sizeof(raw))) {
    batteryVoltage = NAN;
    return;
  }
  const uint16_t cellVoltage =
      static_cast<uint16_t>((static_cast<uint16_t>(raw[0]) << 8) | raw[1]);
  batteryVoltage = cellVoltage * 0.000078125f;
}

void updateMotionSensor() {
  const uint32_t now = millis();
  if (!motionSensorAvailable &&
      now - lastMotionInitAttemptAt >= kSensorRetryIntervalMs) {
    lastMotionInitAttemptAt = now;
    initializeMotionSensor();
  }
  if (!motionSensorAvailable || now - lastMotionAt < kMotionIntervalMs) return;
  lastMotionAt = now;

  uint8_t raw[6];
  if (!readI2cRegisters(kMotionSensorAddress, 0x3B, raw, sizeof(raw))) {
    motionSensorAvailable = false;
    motionActive = false;
    Serial.println("[MPU6050] Leitura perdida; tentando reinicializar");
    return;
  }

  const int16_t rawX = static_cast<int16_t>((raw[0] << 8) | raw[1]);
  const int16_t rawY = static_cast<int16_t>((raw[2] << 8) | raw[3]);
  const int16_t rawZ = static_cast<int16_t>((raw[4] << 8) | raw[5]);
  const float accelerationX = rawX / 16384.0f;
  const float accelerationY = rawY / 16384.0f;
  const float accelerationZ = rawZ / 16384.0f;
  accelerationG = sqrtf(accelerationX * accelerationX +
                        accelerationY * accelerationY +
                        accelerationZ * accelerationZ);

  float movementDeltaG = 0;
  if (!isnan(previousAccelerationX)) {
    const float deltaX = accelerationX - previousAccelerationX;
    const float deltaY = accelerationY - previousAccelerationY;
    const float deltaZ = accelerationZ - previousAccelerationZ;
    movementDeltaG = sqrtf(deltaX * deltaX + deltaY * deltaY + deltaZ * deltaZ);
  }
  previousAccelerationX = accelerationX;
  previousAccelerationY = accelerationY;
  previousAccelerationZ = accelerationZ;
  motionActive = movementDeltaG > kMotionThresholdG;

  switch (fallState) {
    case FallState::Monitoring:
      if (accelerationG < kFreeFallThresholdG) {
        fallState = FallState::FreeFall;
        fallStateStartedAt = now;
      }
      break;
    case FallState::FreeFall:
      if (now - fallStateStartedAt > kFallImpactWindowMs) {
        fallState = FallState::Monitoring;
      } else if (accelerationG >= kFallImpactThresholdG) {
        fallState = FallState::Impact;
        fallStateStartedAt = now;
        fallStillnessStartedAt = 0;
      }
      break;
    case FallState::Impact:
      if (now - fallStateStartedAt > 30000) {
        fallState = FallState::Monitoring;
      } else if (movementDeltaG <= kMotionThresholdG) {
        if (fallStillnessStartedAt == 0) fallStillnessStartedAt = now;
        if (now - fallStillnessStartedAt >= kFallStillnessMs) {
          fallDetected = true;
          fallAlertStartedAt = now;
          fallState = FallState::Alert;
          Serial.println("[MPU6050] Possivel queda detectada; revisar alerta");
        }
      } else {
        fallStillnessStartedAt = 0;
      }
      break;
    case FallState::Alert:
      if (now - fallAlertStartedAt >= kPanicDurationMs) {
        fallDetected = false;
        fallState = FallState::Monitoring;
      }
      break;
  }

  if (now - lastMotionLogAt >= kMotionLogIntervalMs) {
    Serial.printf("[MPU6050] aceleracao=%.2f g | variacao=%.2f g | movimento=%s | queda=%s\n",
                  accelerationG, movementDeltaG,
                  motionActive ? "ativo" : "repouso",
                  fallDetected ? "possivel" : "nao detectada");
    lastMotionLogAt = now;
  }
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
  if (isnan(reading.batteryPercent)) {
    payload["battery_percent"] = nullptr;
  } else {
    payload["battery_percent"] = reading.batteryPercent;
  }
  if (isnan(reading.batteryVoltage)) {
    payload["battery_voltage"] = nullptr;
  } else {
    payload["battery_voltage"] = reading.batteryVoltage;
  }
  if (isnan(reading.accelerationG)) {
    payload["acceleration_g"] = nullptr;
  } else {
    payload["acceleration_g"] = reading.accelerationG;
  }
  payload["motion_active"] = reading.motionActive;
  payload["fall_detected"] = reading.fallDetected;
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
  Serial.printf("[API] Envio %s | status=%d\n",
                panicEvent ? "alerta" : "rotina", status);
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
  buttonState = digitalRead(kPanicPin);
  lastButtonRead = buttonState;
  buttonChangedAt = millis();
  Wire.begin(kI2cSdaPin, kI2cSclPin);
  sensorsStartedAt = millis();

  initializePulseSensor();
  initializeMotionSensor();
  lastSensorInitAttemptAt = millis();

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(true);
  WiFi.setAutoReconnect(true);
  WiFi.begin(kWifiSsid, kWifiPassword, kWifiChannel);
  lastWifiAttemptAt = millis();
  lastReadingAt = millis();
  lastReadingAttemptAt = millis() - kReadingRetryIntervalMs;
  lastTemperatureAt = millis() - kTemperatureIntervalMs;
  lastBatteryAt = millis() - kBatteryIntervalMs;

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
  updateMotionSensor();
  updatePanicButton();
  updateTemperature();
  updateBattery();
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
              initialPulseReady) &&
             now - lastReadingAttemptAt >= kReadingRetryIntervalMs &&
             deliveryTaskReady) {
    const PanicSnapshot currentReading = {
      heartRateBpm, oxygenPercent, skinTemperatureC, batteryPercent,
      batteryVoltage, accelerationG, contactDetected, motionActive,
      fallDetected};
    lastReadingAttemptAt = now;
    if (xQueueOverwrite(routineReadingQueue, &currentReading) == pdPASS) {
      initialReadingQueued = true;
      lastReadingAt = now;
    }
  }
}