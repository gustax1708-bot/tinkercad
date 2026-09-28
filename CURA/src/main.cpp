#include <Arduino.h>
#include <ArduinoJson.h>
#include <DallasTemperature.h>
#include <HTTPClient.h>
#include <MAX30105.h>
#include <OneWire.h>
#include <WiFi.h>
#include <Wire.h>
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
constexpr uint32_t kReadingIntervalMs = 15000;
constexpr uint32_t kTemperatureIntervalMs = 30000;
constexpr uint32_t kWifiRetryIntervalMs = 10000;
constexpr uint32_t kTemperatureConversionMs = 200;
constexpr uint32_t kPanicRetryIntervalMs = 1000;
constexpr size_t kPanicQueueCapacity = 4;
constexpr size_t kOximeterWindowSize = BUFFER_SIZE;

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
uint32_t lastTemperatureAt = 0;
uint32_t lastWifiAttemptAt = 0;
uint32_t lastSensorSampleAt = 0;
uint32_t lastPanicAttemptAt = 0;
uint32_t buttonChangedAt = 0;
uint32_t temperatureConversionStartedAt = 0;
uint8_t pendingPanicHead = 0;
uint8_t pendingPanicCount = 0;
PanicSnapshot pendingPanicEvents[kPanicQueueCapacity];
bool sensorAvailable = false;
bool buttonState = HIGH;
bool lastButtonRead = HIGH;
bool contactDetected = false;
bool temperatureConversionPending = false;

void samplePulseSensor() {
  if (!sensorAvailable) return;

  pulseSensor.check();
  while (pulseSensor.available()) {
    const uint32_t irValue = pulseSensor.getIR();
    const uint32_t redValue = pulseSensor.getRed();
    pulseSensor.nextSample();
    lastSensorSampleAt = millis();
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
      oxygenPercent = spo2Valid ? spo2 : NAN;
      heartRateBpm = heartRateValid ? heartRate : NAN;
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
      if (pendingPanicCount < kPanicQueueCapacity) {
        const uint8_t tail =
            (pendingPanicHead + pendingPanicCount) % kPanicQueueCapacity;
        pendingPanicEvents[tail] = {
            heartRateBpm, oxygenPercent, skinTemperatureC, contactDetected};
        ++pendingPanicCount;
      } else {
        Serial.println("Fila de alertas cheia; alerta adicional nao enfileirado");
      }
    }
  }
  lastButtonRead = reading;
}

void maintainWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
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
    }
    temperatureConversionPending = false;
  }

  if (now - lastTemperatureAt < kTemperatureIntervalMs) return;
  lastTemperatureAt = now;
  temperatureConversionStartedAt = now;
  temperatureConversionPending = true;
  temperatureSensor.requestTemperatures();
}

bool sendReading(bool panicEvent, const PanicSnapshot& panicSnapshot) {
  if (WiFi.status() != WL_CONNECTED) return false;

  const PanicSnapshot currentReading = {
      heartRateBpm, oxygenPercent, skinTemperatureC, contactDetected};
  const PanicSnapshot& reading = panicEvent ? panicSnapshot : currentReading;

  JsonDocument payload;
  payload["device_id"] = kDeviceId;
  if (isnan(reading.heartRateBpm)) {
    payload["heart_rate_bpm"] = nullptr;
  } else {
    payload["heart_rate_bpm"] = reading.heartRateBpm;
  }
  if (isnan(reading.oxygenPercent)) {
    payload["spo2_percent"] = nullptr;
  } else {
    payload["spo2_percent"] = reading.oxygenPercent;
  }
  if (isnan(reading.temperatureC)) {
    payload["temperature_c"] = nullptr;
  } else {
    payload["temperature_c"] = reading.temperatureC;
  }
  payload["panic"] = panicEvent;
  payload["sensor_contact"] = reading.sensorContact;

  String body;
  serializeJson(payload, body);
  HTTPClient client;
  client.setConnectTimeout(2500);
  client.setTimeout(2500);
  client.begin(kApiUrl);
  client.addHeader("Content-Type", "application/json");
  client.addHeader("X-Device-Token", kDeviceToken);
  const int status = client.POST(body);
  Serial.printf("POST %d: %s\n", status, body.c_str());
  client.end();
  return status >= 200 && status < 300;
}
}  // namespace

void setup() {
  Serial.begin(115200);
  pinMode(kPanicPin, INPUT_PULLUP);
  Wire.begin(kI2cSdaPin, kI2cSclPin);
  temperatureSensor.begin();
  temperatureSensor.setResolution(10);
  temperatureSensor.setWaitForConversion(false);

  sensorAvailable = pulseSensor.begin(Wire, I2C_SPEED_FAST);
  if (sensorAvailable) {
    pulseSensor.setup(0x1F, 4, 2, 100, 411, 4096);
    pulseSensor.setPulseAmplitudeRed(0x1F);
    pulseSensor.setPulseAmplitudeIR(0x1F);
    pulseSensor.setPulseAmplitudeGreen(0);
  } else {
    Serial.println("MAX30102 nao encontrado no I2C");
  }

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(true);
  WiFi.setAutoReconnect(true);
  WiFi.begin(kWifiSsid, kWifiPassword, kWifiChannel);
  lastWifiAttemptAt = millis();
  lastReadingAt = millis();
  lastPanicAttemptAt = millis() - kPanicRetryIntervalMs;
  lastTemperatureAt = millis() - kTemperatureIntervalMs;
}

void loop() {
  samplePulseSensor();
  if (sensorAvailable && millis() - lastSensorSampleAt > 2000) {
    contactDetected = false;
    heartRateBpm = NAN;
    oxygenPercent = NAN;
    sampleIndex = 0;
  }
  updatePanicButton();
  updateTemperature();
  maintainWifi();

  const uint32_t now = millis();
  if (pendingPanicCount > 0 && WiFi.status() == WL_CONNECTED &&
      now - lastPanicAttemptAt >= kPanicRetryIntervalMs) {
    lastPanicAttemptAt = now;
    if (sendReading(true, pendingPanicEvents[pendingPanicHead])) {
      pendingPanicHead = (pendingPanicHead + 1) % kPanicQueueCapacity;
      --pendingPanicCount;
      lastReadingAt = now;
    }
  } else if (now - lastReadingAt >= kReadingIntervalMs) {
    const PanicSnapshot currentReading = {
        heartRateBpm, oxygenPercent, skinTemperatureC, contactDetected};
    sendReading(false, currentReading);
    lastReadingAt = now;
  }
}