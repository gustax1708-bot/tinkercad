#include <wokwi-api.h>
#include <stdbool.h>
#include <stdint.h>

#define MAX30205_ADDRESS 0x48

typedef struct {
  uint8_t register_pointer;
  bool expect_register;
  attr_t temperature_attr;
} chip_state_t;

static chip_state_t chip_storage;

static bool on_i2c_connect(void *user_data, uint32_t address, bool read) {
  chip_state_t *chip = user_data;
  if (address != MAX30205_ADDRESS) return false;
  if (!read) chip->expect_register = true;
  return true;
}

static bool on_i2c_write(void *user_data, uint8_t data) {
  chip_state_t *chip = user_data;
  if (chip->expect_register) {
    chip->register_pointer = data;
    chip->expect_register = false;
  }
  return true;
}

static uint8_t on_i2c_read(void *user_data) {
  chip_state_t *chip = user_data;
  uint8_t value = 0;

  if (chip->register_pointer == 0x00) {
    const int16_t raw = (int16_t)(attr_read_float(chip->temperature_attr) * 256.0f);
    value = (uint8_t)((uint16_t)raw >> 8);
  } else if (chip->register_pointer == 0x01) {
    const int16_t raw = (int16_t)(attr_read_float(chip->temperature_attr) * 256.0f);
    value = (uint8_t)raw;
  }
  ++chip->register_pointer;
  return value;
}

void chip_init(void) {
  chip_state_t *chip = &chip_storage;
  chip->temperature_attr = attr_init_float("temperatureC", 36.8f);

  i2c_config_t config = {
      .address = MAX30205_ADDRESS,
      .sda = pin_init("SDA", INPUT_PULLUP),
      .scl = pin_init("SCL", INPUT_PULLUP),
      .connect = on_i2c_connect,
      .read = on_i2c_read,
      .write = on_i2c_write,
      .disconnect = 0,
      .user_data = chip,
  };
  i2c_init(&config);
}