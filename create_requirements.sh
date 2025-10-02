#!/bin/bash
# create_requirements.sh - Crea diferentes archivos de requirements según el caso de uso

# Salir ante cualquier error
set -euo pipefail

# requirements.txt - requisitos base (uso general)
cat > requirements.txt << 'EOL'
# Base requirements for MQTT-OPCUA Bridge
# Instalar con: pip install -r requirements.txt

# MQTT & OPC-UA core
paho-mqtt==1.6.1
asyncua==1.0.4

# Config & parsing
pyyaml==6.0.1
python-dateutil==2.8.2

# Utilidades runtime
numpy==1.24.3
rich==13.7.0
tabulate==0.9.0

# Observabilidad básica
prometheus-client==0.19.0
colorlog==6.7.0
EOL

# requirements-minimal.txt - Solo lo esencial
cat > requirements-minimal.txt << 'EOL'
# Minimal requirements for MQTT-OPCUA Bridge
# Use this for production deployments with minimal dependencies

# Core
paho-mqtt==1.6.1
asyncua==1.0.4
pyyaml==6.0.1
python-dateutil==2.8.2
EOL

# requirements-dev.txt - Para desarrollo
cat > requirements-dev.txt << 'EOL'
# Development requirements for MQTT-OPCUA Bridge
# Install with: pip install -r requirements-dev.txt

# Include all base requirements
-r requirements.txt

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0
pytest-timeout==2.2.0

# Code quality
black==23.11.0
flake8==6.1.0
mypy==1.7.1
pylint==3.0.3
isort==5.12.0
pre-commit==3.5.0

# Development tools
ipython==8.18.1
ipdb==0.13.13
jupyter==1.0.0
notebook==7.0.6

# Documentation
sphinx==7.2.6
sphinx-rtd-theme==2.0.0
sphinx-autodoc-typehints==1.25.2
myst-parser==2.0.0

# Profiling
memory-profiler==0.61.0
line-profiler==4.1.1
py-spy==0.3.14
EOL

# requirements-docker.txt - Para contenedores Docker
cat > requirements-docker.txt << 'EOL'
# Docker optimized requirements for MQTT-OPCUA Bridge
# Minimal dependencies for container deployment

# Core
paho-mqtt==1.6.1
asyncua==1.0.4
pyyaml==6.0.1
python-dateutil==2.8.2
numpy==1.24.3

# Monitoring (lightweight)
prometheus-client==0.19.0

# Logging
colorlog==6.7.0
EOL

# requirements-monitoring.txt - Para sistemas con monitoreo completo
cat > requirements-monitoring.txt << 'EOL'
# Monitoring-focused requirements for MQTT-OPCUA Bridge
# For deployments with comprehensive monitoring needs

# Include base requirements
-r requirements-minimal.txt

# Metrics & Monitoring
prometheus-client==0.19.0
psutil==5.9.6
py-cpuinfo==9.0.0

# Visualization
matplotlib==3.7.3
plotly==5.18.0
seaborn==0.13.0
pandas==2.1.4

# Reporting
jinja2==3.1.2
weasyprint==60.1  # For PDF reports
xlsxwriter==3.1.9  # For Excel reports

# Time series databases
influxdb-client==1.38.0
pymongo==4.6.0  # For MongoDB metrics storage

# Alerting
requests==2.31.0
python-telegram-bot==20.6
slack-sdk==3.23.0
email-validator==2.1.0

# Advanced monitoring
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-exporter-prometheus==0.42b0
opentelemetry-instrumentation==0.42b0
EOL

# requirements-enterprise.txt - Para despliegues empresariales
cat > requirements-enterprise.txt << 'EOL'
# Enterprise requirements for MQTT-OPCUA Bridge
# Full-featured deployment with all capabilities

# Include all base requirements
-r requirements.txt

# High Availability & Scaling
redis==5.0.1
celery==5.3.4
flower==2.0.1  # Celery monitoring

# Message Queuing
kafka-python==2.0.2
confluent-kafka==2.3.0
aiokafka==0.10.0

# Databases
sqlalchemy==2.0.23
alembic==1.13.0  # Database migrations
pymongo==4.6.0
motor==3.3.2  # Async MongoDB

# Security
cryptography==41.0.7
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
ssl-checker==2.2.0

# API & Web Interface
fastapi==0.104.1
uvicorn[standard]==0.24.0
websockets==12.0
python-socketio==5.10.0
aiohttp==3.9.1

# Authentication
python-ldap==3.4.3
pysaml2==7.4.2
authlib==1.2.1

# Cloud Integrations
boto3==1.33.7  # AWS
azure-iot-device==2.12.0  # Azure IoT
google-cloud-pubsub==2.18.4  # Google Cloud

# Observability
opentelemetry-distro==0.42b0
opentelemetry-exporter-jaeger==1.21.0
opentelemetry-exporter-zipkin==1.21.0
sentry-sdk==1.38.0

# Configuration Management
python-consul==1.1.0
python-etcd==0.4.5
kazoo==2.9.0  # Zookeeper

# Performance
uvloop==0.19.0
orjson==3.9.10
msgpack==1.0.7
cachetools==5.3.2

# Analytics & BI
pandas==2.1.4
pyarrow==14.0.2
plotly==5.18.0
dash==2.14.2

# Edge & Industrial Protocols
opcua-client==0.98.13
modbus-tk==1.1.3
pymodbus==3.5.2

# Compliance & Governance
python-auditlog==2.4.0
azure-identity==1.15.0
google-auth==2.23.4

# Deployment helpers
ansible==8.6.0
fabric==3.2.2
packaging==23.2
EOL

echo "Archivos de requirements generados:"
printf '  - %s\n' \
  requirements.txt \
  requirements-minimal.txt \
  requirements-dev.txt \
  requirements-docker.txt \
  requirements-monitoring.txt \
  requirements-enterprise.txt

echo "Selecciona el archivo adecuado según el escenario de despliegue."
