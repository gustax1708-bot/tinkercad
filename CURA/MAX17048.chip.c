#include <wokwi-api.h>
#include <stdbool.h>
#include <stdint.h>

#define MAX17048_ADDRESS 0x36

typedef struct {
  uint8_t register_pointer;
  bool expect_register;
  attr_t battery_percent_attr;
} chip_state_t;

static chip_state_t chip_storage;

static bool on_i2c_connect(void *user_data, uint32_t address, bool read) {
  chip_state_t *chip = user_data;
  if (address != MAX17048_ADDRESS) return false;
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

static float estimate_cell_voltage(float percent) {
  if (percent <= 5.0f) return 3.30f + percent * 0.04f;
  if (percent <= 20.0f) return 3.50f + (percent - 5.0f) * 0.01f;
  if (percent <= 80.0f) return 3.65f + (percent - 20.0f) * 0.005f;
  return 3.95f + (percent - 80.0f) * 0.0125f;
}

static uint8_t on_i2c_read(void *user_data) {
  chip_state_t *chip = user_data;
  const float percent = attr_read_float(chip->battery_percent_attr);
  uint16_t raw = 0;

  if (chip->register_pointer == 0x02 || chip->register_pointer == 0x03) {
    raw = (uint16_t)(estimate_cell_voltage(percent) / 0.000078125f) & 0xFFF0;
  } else if (chip->register_pointer == 0x04 || chip->register_pointer == 0x05) {
    raw = (uint16_t)(percent * 256.0f);
  }

  const uint8_t value = (chip->register_pointer & 1)
                            ? (uint8_t)raw
                            : (uint8_t)(raw >> 8);
  ++chip->register_pointer;
  return value;
}

void chip_init(void) {
  chip_state_t *chip = &chip_storage;
  chip->battery_percent_attr = attr_init_float("batteryPercent", 100.0f);

  i2c_config_t config = {
      .address = MAX17048_ADDRESS,
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