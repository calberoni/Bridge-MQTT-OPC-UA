#!/bin/bash
# setup_rpi.sh - Preparación rápida del bridge en Raspberry Pi 2 / ARMv7

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"

if [[ $EUID -eq 0 ]]; then
  echo "Ejecuta este script como usuario normal, no como root." >&2
  exit 1
fi

echo "=== Instalando dependencias del sistema (se requiere sudo) ==="
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev build-essential \
  libffi-dev pkg-config mosquitto mosquitto-clients

if [[ ! -d "$VENV_DIR" ]]; then
  echo "=== Creando entorno virtual ==="
  python3.11 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "=== Actualizando pip ==="
pip install --upgrade pip

echo "=== Instalando dependencias mínimas ==="
pip install -r requirements-minimal.txt

echo "=== Preparando rutas ==="
mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/data"

echo "Listo. Configura bridge_config.yaml y ejecuta:"
echo "  source venv/bin/activate && python mqtt_opcua_bridge.py"
