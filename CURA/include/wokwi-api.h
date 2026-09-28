#ifndef WOKWI_API_H
#define WOKWI_API_H

#if defined(__wasm__)
typedef _Bool bool;
typedef unsigned char uint8_t;
typedef unsigned int uint32_t;
typedef signed int int32_t;
#else
#include <stdbool.h>
#include <stdint.h>
#endif

enum pin_mode {
  INPUT = 0,
  OUTPUT = 1,
  INPUT_PULLUP = 2,
  INPUT_PULLDOWN = 3,
  ANALOG = 4,
  OUTPUT_LOW = 16,
  OUTPUT_HIGH = 17,
};

#if defined(__wasm__)
int __attribute__((export_name("__wokwi_api_version_1")))
    __attribute__((weak)) __wokwi_api_version_1(void) {
  return 1;
}
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef int32_t pin_t;
typedef uint32_t timer_t;
typedef uint32_t attr_t;

extern __attribute__((export_name("chipInit"))) void chip_init(void);
extern __attribute__((import_name("pinInit"))) pin_t pin_init(const char *name, uint32_t mode);

typedef struct {
  void *user_data;
  uint32_t address;
  pin_t scl;
  pin_t sda;
  bool (*connect)(void *user_data, uint32_t address, bool read);
  uint8_t (*read)(void *user_data);
  bool (*write)(void *user_data, uint8_t data);
  void (*disconnect)(void *user_data);
  uint32_t reserved[8];
} i2c_config_t;

extern __attribute__((import_name("i2cInit"))) uint32_t i2c_init(const i2c_config_t *config);

typedef struct {
  void *user_data;
  void (*callback)(void *user_data);
  uint32_t reserved[8];
} timer_config_t;

extern __attribute__((import_name("timerInit"))) timer_t timer_init(const timer_config_t *config);
extern __attribute__((import_name("timerStart"))) void timer_start(timer_t timer, uint32_t micros, bool repeat);
extern __attribute__((import_name("attrInitFloat"))) attr_t attr_init_float(const char *name, float default_value);
extern __attribute__((import_name("attrReadFloat"))) float attr_read_float(attr_t attr);

#ifdef __cplusplus
}
#endif

#endif