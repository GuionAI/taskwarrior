#!/usr/bin/env bash
set -euo pipefail

TARGET="x86_64-unknown-linux-musl"
CONTEXT="--context guion-tunnel"
NAMESPACE="-n apps-dev"
LABEL="app.kubernetes.io/name=temenos"
DEST="/usr/local/bin/task"
BUILD_DIR="build"

echo "==> Checking prerequisites..."
if ! command -v zig &>/dev/null; then
  echo "Error: zig not found. Install with: brew install zig"
  exit 1
fi

echo "==> Creating musl-cc/musl-cxx wrappers..."
sudo tee /usr/local/bin/musl-cc > /dev/null << 'WRAPPER'
#!/bin/bash
args=()
skip_next=0
for arg in "$@"; do
    [ "$skip_next" = "1" ] && { skip_next=0; continue; }
    [ "$arg" = "-target" ] && { skip_next=1; continue; }
    [[ "$arg" == --target=* ]] && continue
    args+=("$arg")
done
exec zig cc -target x86_64-linux-musl "${args[@]}"
WRAPPER
sudo tee /usr/local/bin/musl-cxx > /dev/null << 'WRAPPER'
#!/bin/bash
args=()
skip_next=0
for arg in "$@"; do
    [ "$skip_next" = "1" ] && { skip_next=0; continue; }
    [ "$arg" = "-target" ] && { skip_next=1; continue; }
    [[ "$arg" == --target=* ]] && continue
    args+=("$arg")
done
exec zig c++ -target x86_64-linux-musl "${args[@]}"
WRAPPER
sudo chmod +x /usr/local/bin/musl-cc /usr/local/bin/musl-cxx

echo "==> Generating toolchain file..."
cat > /tmp/musl-toolchain.cmake << 'TOOLCHAIN'
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR x86_64)
set(CMAKE_C_COMPILER /usr/local/bin/musl-cc)
set(CMAKE_CXX_COMPILER /usr/local/bin/musl-cxx)
set(CMAKE_C_COMPILER_WORKS TRUE)
set(CMAKE_CXX_COMPILER_WORKS TRUE)
set(CMAKE_C_IMPLICIT_INCLUDE_DIRECTORIES "")
set(CMAKE_CXX_IMPLICIT_INCLUDE_DIRECTORIES "")
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY BOTH)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE BOTH)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
TOOLCHAIN

echo "==> Configuring cmake with musl toolchain..."
export CC=/usr/local/bin/musl-cc
export CXX=/usr/local/bin/musl-cxx
cmake -S . -B ${BUILD_DIR} \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE=/tmp/musl-toolchain.cmake \
  -DRust_CARGO_TARGET=${TARGET}

echo "==> Building task binary..."
cmake --build ${BUILD_DIR} --target task_executable -j$(nproc)

echo "==> Copying to cluster..."
POD=$(kubectl get pods ${CONTEXT} ${NAMESPACE} -l "${LABEL}" -o jsonpath='{.items[0].metadata.name}')
kubectl cp ${CONTEXT} "${BUILD_DIR}/src/task" "${NAMESPACE#-n }/${POD}:${DEST}"

echo "==> Done."
