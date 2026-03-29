BUILD_DIR   := build
BUILD_TYPE  ?= Release
NPROC       := $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

.PHONY: build install test clean

build:
	cmake -S . -B $(BUILD_DIR) -DCMAKE_BUILD_TYPE=$(BUILD_TYPE)
	cmake --build $(BUILD_DIR) -j$(NPROC)

# Installs task binary, man pages, and docs per CMakeLists.txt install() rules.
# Use CMAKE_INSTALL_PREFIX to control destination (default: /usr/local).
install: build
	cmake --install $(BUILD_DIR)

test:
	cmake -S . -B $(BUILD_DIR) -DCMAKE_BUILD_TYPE=Debug
	cmake --build $(BUILD_DIR) --target test_runner --target task_executable -j$(NPROC)
	ctest --test-dir $(BUILD_DIR) -j$(NPROC) --output-on-failure

clean:
	rm -rf $(BUILD_DIR)
