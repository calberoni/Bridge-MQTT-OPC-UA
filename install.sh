#!/bin/bash
# install.sh - Script de instalación para Ubuntu

echo "======================================"
echo "Instalación de Bridge MQTT-OPCUA"
echo "======================================"

# Actualizar sistema
echo "Actualizando sistema..."
sudo apt-get update
sudo apt-get upgrade -y

# Instalar Python 3.9+ si no está instalado
echo "Verificando Python..."
if ! command -v python3 &> /dev/null; then
    echo "Instalando Python 3..."
    sudo apt-get install -y python3 python3-pip python3-venv
fi

# Instalar mosquitto (broker MQTT) para pruebas locales
echo "¿Desea instalar Mosquitto (broker MQTT local)? (s/n)"
read -r install_mosquitto
if [ "$install_mosquitto" = "s" ]; then
    sudo apt-get install -y mosquitto mosquitto-clients
    sudo systemctl enable mosquitto
    sudo systemctl start mosquitto
fi

# Crear entorno virtual
echo "Creando entorno virtual Python..."
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias Python
echo "Instalando dependencias Python..."
pip install --upgrade pip

# requirements.txt content
cat > requirements.txt << 'EOL'
# Core Dependencies
# =================

# MQTT Client
paho-mqtt==1.6.1

# OPC-UA Server/Client
asyncua==1.0.4

# Configuration
pyyaml==6.0.1

# Utilities
python-dateutil==2.8.2
numpy==1.24.3

# Database (SQLite3 viene con Python, no requiere instalación)
# pero agregamos herramientas adicionales para mejor manejo
sqlalchemy==2.0.23  # Optional: Para ORM si se desea en el futuro

# Monitoring & Analytics
# ======================

# Logging mejorado
colorlog==6.7.0

# Métricas y monitoreo
prometheus-client==0.19.0  # Para exportar métricas a Prometheus
psutil==5.9.6  # Para monitoreo de recursos del sistema

# Visualización y reportes
matplotlib==3.7.3  # Para gráficos de métricas
tabulate==0.9.0  # Para tablas formateadas en terminal
rich==13.7.0  # Para UI mejorada en terminal

# Web Reports (opcional)
jinja2==3.1.2  # Para generar reportes HTML
plotly==5.18.0  # Para gráficos interactivos en HTML

# Performance & Optimization
# ==========================

# Async improvements
aiofiles==23.2.1  # Para operaciones de archivo asíncronas
aiodns==3.1.1  # Para resolución DNS asíncrona

# Threading y concurrencia
concurrent-futures==3.1.1  # Backport para Python < 3.8

# Testing & Development
# =====================

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0

# Code quality
black==23.11.0  # Formateo de código
flake8==6.1.0  # Linting
mypy==1.7.1  # Type checking
pylint==3.0.3  # Análisis estático

# Development tools
ipython==8.18.1  # Shell interactivo mejorado
ipdb==0.13.13  # Debugger mejorado

# Documentation
# =============

sphinx==7.2.6  # Generación de documentación
sphinx-rtd-theme==2.0.0  # Tema para documentación
myst-parser==2.0.0  # Para usar Markdown en Sphinx

# Optional Dependencies
# =====================

# Para integración con sistemas externos
redis==5.0.1  # Si se quiere usar Redis como cache
kafka-python==2.0.2  # Para integración con Apache Kafka
influxdb-client==1.38.0  # Para enviar métricas a InfluxDB

# Seguridad
cryptography==41.0.7  # Para TLS/SSL avanzado
python-jose==3.3.0  # Para JWT tokens
passlib==1.7.4  # Para manejo seguro de passwords

# API REST (si se quiere agregar API al bridge)
fastapi==0.104.1  # Framework web moderno
uvicorn==0.24.0  # Servidor ASGI
pydantic==2.5.2  # Validación de datos

# Notificaciones
requests==2.31.0  # Para webhooks y llamadas HTTP
python-telegram-bot==20.6  # Para notificaciones Telegram
slack-sdk==3.23.0  # Para notificaciones Slack

# Utilidades adicionales
python-dotenv==1.0.0  # Para manejo de variables de entorno
schedule==1.2.0  # Para tareas programadas simples
watchdog==3.0.0  # Para monitorear cambios en archivos
EOL

pip install -r requirements.txt

# Crear estructura de directorios
echo "Creando estructura de directorios..."
mkdir -p logs
mkdir -p data
mkdir -p certs

# Crear archivo de servicio systemd
echo "Creando servicio systemd..."
sudo tee /etc/systemd/system/mqtt-opcua-bridge.service > /dev/null << 'EOL'
[Unit]
Description=MQTT to OPC-UA Bridge Service
After=network.target
Wants=mosquitto.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/mqtt-opcua-bridge
Environment="PATH=/home/$USER/mqtt-opcua-bridge/venv/bin"
ExecStart=/home/$USER/mqtt-opcua-bridge/venv/bin/python /home/$USER/mqtt-opcua-bridge/mqtt_opcua_bridge.py
Restart=always
RestartSec=10
StandardOutput=append:/home/$USER/mqtt-opcua-bridge/logs/bridge.log
StandardError=append:/home/$USER/mqtt-opcua-bridge/logs/bridge_error.log

[Install]
WantedBy=multi-user.target
EOL

# Reemplazar $USER con el usuario actual
sudo sed -i "s/\$USER/$USER/g" /etc/systemd/system/mqtt-opcua-bridge.service

# Crear script de inicio
cat > start_bridge.sh << 'EOL'
#!/bin/bash
# Activar entorno virtual y ejecutar bridge
source venv/bin/activate
python mqtt_opcua_bridge.py
EOL
chmod +x start_bridge.sh

# Crear script de prueba MQTT
cat > test_mqtt.sh << 'EOL'
#!/bin/bash
# Script de prueba para publicar mensajes MQTT

echo "Publicando datos de prueba en MQTT..."

# Temperatura
mosquitto_pub -h localhost -t "sensores/temperatura/sala" -m "22.5"
echo "Temperatura: 22.5°C"

# Humedad
mosquitto_pub -h localhost -t "sensores/humedad/sala" -m "65.3"
echo "Humedad: 65.3%"

# Estado del sistema
mosquitto_pub -h localhost -t "sistema/estado" -m "Operativo"
echo "Estado: Operativo"

# JSON complejo
mosquitto_pub -h localhost -t "datos/json/dispositivo1" -m '{"id":1,"name":"Sensor1","values":[1,2,3]}'
echo "JSON enviado"

# Timestamp
mosquitto_pub -h localhost -t "sistema/ultima_actualizacion" -m "$(date -Iseconds)"
echo "Timestamp actualizado"

echo "Datos de prueba enviados!"
EOL
chmod +x test_mqtt.sh

# Crear cliente OPC-UA de prueba
cat > test_opcua_client.py << 'EOL'
#!/usr/bin/env python3
"""
Cliente OPC-UA de prueba para verificar el bridge
"""

import asyncio
import sys
from asyncua import Client, ua

async def test_opcua():
    """Prueba la conexión OPC-UA"""
    url = "opc.tcp://localhost:4840/bridge/server/"
    
    async with Client(url=url) as client:
        print(f"Conectado a: {url}")
        
        # Obtener el nodo raíz
        root = client.get_root_node()
        print(f"Nodo raíz: {root}")
        
        # Navegar a los objetos
        objects = client.get_objects_node()
        print(f"Nodo Objects: {objects}")
        
        # Listar todos los hijos
        children = await objects.get_children()
        print("\nNodos disponibles:")
        for child in children:
            name = await child.read_browse_name()
            print(f"  - {name.Name}")
        
        # Intentar leer valores específicos
        try:
            # Buscar la carpeta MQTTBridge
            bridge_folder = None
            for child in children:
                name = await child.read_browse_name()
                if name.Name == "MQTTBridge":
                    bridge_folder = child
                    break
            
            if bridge_folder:
                print("\nVariables en MQTTBridge:")
                variables = await bridge_folder.get_children()
                
                for var in variables:
                    try:
                        name = await var.read_browse_name()
                        value = await var.read_value()
                        print(f"  {name.Name}: {value}")
                    except Exception as e:
                        print(f"  Error leyendo {name.Name}: {e}")
                
                # Escribir un valor de prueba
                print("\nEscribiendo valor de prueba...")
                for var in variables:
                    name = await var.read_browse_name()
                    if "Light" in name.Name:
                        await var.write_value(True)
                        print(f"  Luz encendida: True")
                        await asyncio.sleep(1)
                        await var.write_value(False)
                        print(f"  Luz apagada: False")
                        break
                        
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_opcua())
EOL
chmod +x test_opcua_client.py

# Crear script de monitoreo
cat > monitor_bridge.sh << 'EOL'
#!/bin/bash
# Monitorear el bridge en tiempo real

echo "Monitoreando Bridge MQTT-OPCUA"
echo "==============================="
echo ""
echo "Suscribiéndose a todos los topics MQTT configurados..."
echo ""

# Array de topics a monitorear
topics=(
    "sensores/temperatura/sala"
    "sensores/humedad/sala"
    "actuadores/luz/sala"
    "control/setpoint/temperatura"
    "sistema/estado"
    "datos/json/dispositivo1"
    "sistema/ultima_actualizacion"
    "produccion/contador"
    "alarmas/activa"
    "proceso/valor/pv1"
)

# Construir comando mosquitto_sub con múltiples topics
cmd="mosquitto_sub -h localhost -v"
for topic in "${topics[@]}"; do
    cmd="$cmd -t $topic"
done

# Ejecutar con formato mejorado
$cmd | while read -r line; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line"
done
EOL
chmod +x monitor_bridge.sh

echo ""
echo "======================================"
echo "Instalación completada!"
echo "======================================"
echo ""
echo "Archivos creados:"
echo "  - config.py: Módulo de configuración"
echo "  - mqtt_opcua_bridge.py: Bridge principal"
echo "  - bridge_config.yaml: Archivo de configuración"
echo "  - requirements.txt: Dependencias Python"
echo "  - start_bridge.sh: Script para iniciar el bridge"
echo "  - test_mqtt.sh: Script de prueba MQTT"
echo "  - test_opcua_client.py: Cliente OPC-UA de prueba"
echo "  - monitor_bridge.sh: Monitor de mensajes"
echo ""
echo "Para iniciar el bridge:"
echo "  1. Editar bridge_config.yaml según sus necesidades"
echo "  2. Ejecutar: ./start_bridge.sh"
echo ""
echo "Para ejecutar como servicio:"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable mqtt-opcua-bridge"
echo "  sudo systemctl start mqtt-opcua-bridge"
echo ""
echo "Para ver los logs:"
echo "  journalctl -u mqtt-opcua-bridge -f"
echo ""