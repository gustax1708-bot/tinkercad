#pragma once

#include <stdint.h>

#if defined(WOKWI_SIMULATION)
constexpr char kWifiSsid[] = "Wokwi-GUEST";
constexpr char kWifiPassword[] = "";
constexpr char kApiUrl[] = "http://host.wokwi.internal:8000/api/v1/readings";
constexpr uint8_t kWifiChannel = 6;
constexpr char kDeviceToken[] = "dev-token";
constexpr char kDeviceId[] = "pulseira-01";
#else
#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"
#endif
constexpr char kWifiSsid[] = DEVICE_WIFI_SSID;
constexpr char kWifiPassword[] = DEVICE_WIFI_PASSWORD;
constexpr char kApiUrl[] = DEVICE_API_URL;
constexpr uint8_t kWifiChannel = 0;
constexpr char kDeviceToken[] = DEVICE_API_TOKEN;
constexpr char kDeviceId[] = "pulseira-01";
#endif
