WASI_CC ?= clang
WASI_SYSROOT ?= $(if $(wildcard /opt/wasi-libc),/opt/wasi-libc,)
WASI_SYSROOT_FLAG := $(if $(WASI_SYSROOT),--sysroot $(WASI_SYSROOT),)
CHIP_SOURCE := Sensor_Saturacao.chip.c
CHIP_BINARY := Sensor_Saturacao.chip.wasm
OFFICIAL_EXAMPLE := https://github.com/wokwi/inverter-chip.git

.PHONY: all test-official build-chip clean

all: test-official build-chip

test-official:
	@set -eu; temp_dir=$$(mktemp -d); trap 'rm -rf "$$temp_dir"' EXIT; \
	git clone --depth 1 $(OFFICIAL_EXAMPLE) "$$temp_dir/inverter-chip"; \
	$(MAKE) -C "$$temp_dir/inverter-chip"

build-chip: $(CHIP_BINARY)

$(CHIP_BINARY): $(CHIP_SOURCE) Sensor_Saturacao.chip.json include/wokwi-api.h
	$(WASI_CC) --target=wasm32-unknown-wasi $(WASI_SYSROOT_FLAG) \
		-nostdlib -Wl,--import-memory -Wl,--export-table \
		-Wl,--no-entry -Werror -Iinclude -o $@ $(CHIP_SOURCE) -lm

clean:
	rm -f $(CHIP_BINARY)
