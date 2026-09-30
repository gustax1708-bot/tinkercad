// Wokwi Custom Chip - For docs and examples see:
// https://docs.wokwi.com/chips-api/getting-started
//
// SPDX-License-Identifier: MIT
// Copyright 2023 

#include <wokwi-api.h>
#include <math.h>
#include <stdbool.h>

#define MAX30102_ADDRESS 0x57
#define FIFO_SIZE 32
#define RED_IR_BYTES_PER_SAMPLE 6
typedef struct {
  uint8_t registers[256];
  uint8_t register_pointer;
  uint8_t fifo_read_pointer;
  uint8_t fifo_write_pointer;
  uint8_t fifo_byte_index;
  uint32_t sample_index;
  attr_t heart_rate_attr;
  attr_t spo2_attr;
  uint32_t red_fifo[FIFO_SIZE];
  uint32_t ir_fifo[FIFO_SIZE];
  bool expect_register;
} chip_state_t;

static chip_state_t chip_storage;

static bool on_i2c_connect(void *user_data, uint32_t address, bool read) {
  chip_state_t *chip = user_data;
  if (address != MAX30102_ADDRESS) return false;
  if (!read) chip->expect_register = true;
  return true;
}

static bool on_i2c_write(void *user_data, uint8_t data) {
  chip_state_t *chip = user_data;
  if (chip->expect_register) {
    chip->register_pointer = data;
    chip->expect_register = false;
    if (data == 0x07) chip->fifo_byte_index = 0;
    return true;
  }

  const uint8_t reg = chip->register_pointer;
  if (reg == 0x04) chip->fifo_write_pointer = data & 0x1F;
  if (reg == 0x06) chip->fifo_read_pointer = data & 0x1F;
  if (reg == 0x09 && (data & 0x40)) {
    chip->registers[reg] = 0;
    chip->fifo_read_pointer = 0;
    chip->fifo_write_pointer = 0;
    chip->fifo_byte_index = 0;
    return true;
  }

  chip->registers[reg] = data;
  return true;
}

static uint8_t on_i2c_read(void *user_data) {
  chip_state_t *chip = user_data;
  const uint8_t reg = chip->register_pointer;

  if (reg == 0xFF) return 0x15;
  if (reg == 0xFE) return 0x01;
  if (reg == 0x04) return chip->fifo_write_pointer;
  if (reg == 0x05) return 0;
  if (reg == 0x06) return chip->fifo_read_pointer;

  if (reg == 0x07) {
    const uint8_t sample = chip->fifo_read_pointer;
    const uint32_t value = chip->fifo_byte_index < 3
                               ? chip->red_fifo[sample]
                               : chip->ir_fifo[sample];
    const uint8_t channel_byte = chip->fifo_byte_index % 3;
    const uint8_t result = (value >> (16 - channel_byte * 8)) & 0xFF;
    ++chip->fifo_byte_index;
    if (chip->fifo_byte_index == RED_IR_BYTES_PER_SAMPLE) {
      chip->fifo_byte_index = 0;
      chip->fifo_read_pointer = (chip->fifo_read_pointer + 1) % FIFO_SIZE;
    }
    return result;
  }

  return chip->registers[reg];
}

static void on_sample_timer(void *user_data) {
  chip_state_t *chip = user_data;
  const uint8_t next_pointer = (chip->fifo_write_pointer + 1) % FIFO_SIZE;
  if (next_pointer == chip->fifo_read_pointer) return;

  const float heart_rate = attr_read_float(chip->heart_rate_attr);
  const float spo2 = attr_read_float(chip->spo2_attr);
  const uint32_t phase = chip->sample_index % 48u;
  const float pulse_cycle = phase < 24u ? (float)phase / 24.0f : (48.0f - (float)phase) / 24.0f;
  const float oxygen_cycle = phase < 32u ? (float)phase / 32.0f : (64.0f - (float)phase) / 32.0f;
  const float pulse_offset = (float)(heart_rate - 60.0f) / 30.0f;
  const float red_amplitude = 14000.0f + (100.0f - spo2) * 150.0f;
  const uint8_t slot = chip->fifo_write_pointer;

  chip->ir_fifo[slot] =
      (uint32_t)(98000.0f + 15000.0f * pulse_cycle * (1.0f + pulse_offset * 0.12f));
  chip->red_fifo[slot] =
      (uint32_t)(92000.0f + red_amplitude * (0.55f + oxygen_cycle * 0.45f));
  ++chip->sample_index;
  chip->fifo_write_pointer = next_pointer;
}

void chip_init(void) {
  chip_state_t *chip = &chip_storage;
  chip->heart_rate_attr = attr_init_float("heartRateBpm", 72.0f);
  chip->spo2_attr = attr_init_float("spo2Percent", 98.0f);

  chip->registers[0xFF] = 0x15;
  chip->registers[0xFE] = 0x01;

  i2c_config_t i2c_config = {
      .address = MAX30102_ADDRESS,
      .sda = pin_init("SDA", INPUT_PULLUP),
      .scl = pin_init("SCL", INPUT_PULLUP),
      .connect = on_i2c_connect,
      .read = on_i2c_read,
      .write = on_i2c_write,
      .disconnect = 0,
      .user_data = chip,
  };
  i2c_init(&i2c_config);

  timer_config_t timer_config = {
      .callback = on_sample_timer,
      .user_data = chip,
  };
  const timer_t sample_timer = timer_init(&timer_config);
  timer_start(sample_timer, 40000, true);
}
