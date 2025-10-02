# Bridge MQTT ↔ OPC-UA con Buffer Persistente SQLite

Un servicio bidireccional que actúa como puente entre protocolos MQTT y OPC-UA, con un sistema de buffer persistente en SQLite que garantiza cero pérdida de mensajes durante desconexiones o reinicios.

## 🚀 Características

### Características Principales
- **Comunicación Bidireccional**: Soporte completo para flujo de datos en ambas direcciones
- **Buffer Persistente SQLite**: Garantiza cero pérdida de mensajes incluso con reinicios del sistema
- **Mapeo Flexible**: Configuración mediante YAML para mapear topics MQTT a nodos OPC-UA
- **Tipos de Datos Soportados**: Boolean, Int32, Float, Double, String, DateTime, JSON
- **Reconexión Automática**: Manejo robusto de desconexiones
- **Sistema de Reintentos**: Reintentos automáticos con backoff exponencial
- **Priorización de Mensajes**: Soporte para diferentes niveles de prioridad
- **Logging Detallado**: Sistema de logs configurable para debugging y monitoreo
- **Docker Ready**: Incluye configuración Docker Compose para despliegue rápido

### Buffer Persistente SQLite
- **Almacenamiento en disco**: Los mensajes se guardan en SQLite hasta ser procesados
- **Recuperación ante fallos**: Al reiniciar, los mensajes pendientes se procesan automáticamente
- **Gestión de memoria**: Limpieza automática de mensajes antiguos
- **Monitoreo en tiempo real**: Herramienta incluida para monitorear el estado del buffer
- **Exportación de estadísticas**: Análisis detallado del rendimiento
- **Manejo de mensajes fallidos**: Registro separado para análisis post-mortem

## 📋 Requisitos

- Ubuntu 20.04+ o similar
- Python 3.9+
- Mosquitto MQTT Broker (o cualquier broker MQTT)
- Cliente OPC-UA compatible (para pruebas)

## 🔧 Instalación

### Método 1: Instalación Manual

1. **Clonar o crear el proyecto**:
```bash
mkdir mqtt-opcua-bridge
cd mqtt-opcua-bridge
```

2. **Copiar todos los archivos del proyecto**:
- `config.py`
- `mqtt_opcua_bridge.py`
- `bridge_config.yaml`
- `requirements.txt`
- `install.sh`

3. **Instalar dependencias**:
   - Entornos estándar: `pip install -r requirements.txt`
   - Raspberry Pi / hardware limitado: `pip install -r requirements-minimal.txt`

4. **Opcional (Raspberry Pi 2 +)**: sigue la guía específica en `docs/raspberry-pi-setup.md` o ejecuta `./setup_rpi.sh` para automatizar los pasos básicos.

5. **Configurar el bridge**:
```bash
nano bridge_config.yaml
```

6. **Iniciar el servicio**:
```bash
./start_bridge.sh
```

### Método 2: Docker Compose

1. **Copiar todos los archivos incluyendo**:
- `docker-compose.yml`
- `Dockerfile`
- Archivos de configuración

2. **Construir e iniciar**:
```bash
docker-compose up -d
```

## ⚙️ Configuración

### Configuración MQTT

```yaml
mqtt:
  broker_host: "localhost"
  broker_port: 1883
  client_id: "mqtt_opcua_bridge_01"
  username: null  # Opcional
  password: null  # Opcional
  qos: 1
```

### Configuración OPC-UA

```yaml
opcua:
  endpoint: "opc.tcp://0.0.0.0:4840/bridge/server/"
  server_name: "MQTT-OPCUA Bridge Server"
  namespace: "http://mqtt-opcua-bridge.com"
  security_policy: "NoSecurity"
```

### Mapeo de Datos

```yaml
mappings:
  - mqtt_topic: "sensores/temperatura/sala"
    opcua_node_id: "ns=2;s=Temperature.Room"
    data_type: "Float"
    direction: "mqtt_to_opcua"  # Opciones: mqtt_to_opcua, opcua_to_mqtt, bidirectional
```

### Direcciones de Mapeo

- `mqtt_to_opcua`: Datos fluyen solo de MQTT hacia OPC-UA
- `opcua_to_mqtt`: Datos fluyen solo de OPC-UA hacia MQTT
- `bidirectional`: Datos fluyen en ambas direcciones

## 🧪 Pruebas

### Probar publicación MQTT

```bash
# Publicar temperatura
mosquitto_pub -h localhost -t "sensores/temperatura/sala" -m "23.5"

# Publicar estado JSON
mosquitto_pub -h localhost -t "datos/json/dispositivo1" -m '{"id":1,"status":"OK"}'

# O usar el script de prueba incluido
./test_mqtt.sh
```

### Probar cliente OPC-UA

```bash
# Ejecutar cliente de prueba
python test_opcua_client.py
```

### Monitorear Buffer Persistente

```bash
# Ver estadísticas del buffer
python buffer_monitor.py stats

# Monitoreo en tiempo real
python buffer_monitor.py monitor

# Ver mensajes pendientes
python buffer_monitor.py pending --limit 50

# Ver mensajes fallidos
python buffer_monitor.py failed

# Limpiar mensajes antiguos (más de 7 días)
python buffer_monitor.py cleanup --days 7

# Reiniciar mensajes atascados
python buffer_monitor.py reset

# Exportar estadísticas detalladas
python buffer_monitor.py export --output stats.json
```

### Monitorear mensajes MQTT

```bash
# Monitorear todos los topics configurados
./monitor_bridge.sh

# O manualmente
mosquitto_sub -h localhost -t "#" -v
```

## 🐳 Docker

### Construir imagen

```bash
docker build -t mqtt-opcua-bridge .
```

### Ejecutar con Docker Compose

```bash
# Iniciar todos los servicios
docker-compose up -d

# Ver logs
docker-compose logs -f mqtt-opcua-bridge

# Detener servicios
docker-compose down
```

### Acceso a servicios

- **MQTT Broker**: `localhost:1883`
- **OPC-UA Server**: `opc.tcp://localhost:4840/bridge/server/`
- **Grafana** (si está habilitado): `http://localhost:3000`
- **OPC-UA Web Viewer** (si está habilitado): `http://localhost:8080` (no está implementado aún)

## 🔄 Systemd Service

### Habilitar servicio

```bash
sudo systemctl daemon-reload
sudo systemctl enable mqtt-opcua-bridge
sudo systemctl start mqtt-opcua-bridge
```

### Ver estado y logs

```bash
# Estado del servicio
sudo systemctl status mqtt-opcua-bridge

# Logs en tiempo real
journalctl -u mqtt-opcua-bridge -f

# Últimas 100 líneas
journalctl -u mqtt-opcua-bridge -n 100
```

## 📊 Monitoreo

### Buffer Persistente SQLite

El sistema incluye un buffer persistente SQLite que garantiza:
- **Cero pérdida de mensajes** durante reinicios o desconexiones
- **Reintentos automáticos** con límite configurable
- **Priorización de mensajes** (CRITICAL, HIGH, NORMAL, LOW)
- **TTL (Time To Live)** para evitar acumulación infinita

Estructura de la base de datos:
```sql
-- Tabla principal de mensajes
messages (
    id, source, destination, topic_or_node, value,
    status (pending/processing/completed/failed/expired),
    priority, retry_count, created_at, processed_at, expire_at
)

-- Tabla de mensajes fallidos para análisis
failed_messages (
    id, original_id, source, destination, error_message,
    failed_at, retry_count
)

-- Tabla de estadísticas
statistics (
    timestamp, metric_name, metric_value
)
```

### Herramienta de Monitoreo

El archivo `buffer_monitor.py` proporciona:
- Visualización en tiempo real del estado del buffer
- Estadísticas de throughput y tasas de error
- Gestión de mensajes atascados
- Limpieza de mensajes antiguos
- Exportación de métricas para análisis

### Logs

Los logs se guardan en:
- `logs/bridge.log`: Log principal
- `logs/bridge_error.log`: Errores (cuando se ejecuta como servicio)
- `buffer.db`: Base de datos SQLite con todo el historial de mensajes

### Estado del Sistema

Para verificar el estado del sistema:

```bash
# Ver estadísticas generales
python buffer_monitor.py stats

# Monitoreo en tiempo real (actualización cada 5 segundos)
python buffer_monitor.py monitor --interval 5

# Ver rendimiento
sqlite3 buffer.db "SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
    SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed
FROM messages;"
```

## 🔒 Seguridad

### MQTT con TLS

```yaml
mqtt:
  tls_enabled: true
  ca_cert: "/path/to/ca.crt"
  client_cert: "/path/to/client.crt"
  client_key: "/path/to/client.key"
```

### OPC-UA con certificados

```yaml
opcua:
  security_policy: "Basic256Sha256"
  certificate: "/path/to/server.crt"
  private_key: "/path/to/server.key"
  allow_anonymous: false
```

## 📝 Tipos de Datos Soportados

| Tipo | MQTT | OPC-UA | Ejemplo |
|------|------|--------|---------|
| Boolean | "true"/"false" | Boolean | true |
| Int32 | "123" | Int32 | 123 |
| Float | "23.5" | Float | 23.5 |
| Double | "123.456789" | Double | 123.456789 |
| String | "texto" | String | "Hola Mundo" |
| DateTime | ISO 8601 | DateTime | "2024-01-15T10:30:00" |
| JSON | JSON String | String | {"key": "value"} |

## 🛠️ Solución de Problemas

### El bridge no se conecta a MQTT

1. Verificar que el broker MQTT esté ejecutándose:
```bash
sudo systemctl status mosquitto
```

2. Probar conexión manual:
```bash
mosquitto_pub -h localhost -t "test" -m "test"
```

3. Revisar configuración de firewall:
```bash
sudo ufw allow 1883
```

### El servidor OPC-UA no inicia

1. Verificar que el puerto 4840 esté disponible:
```bash
sudo netstat -tulpn | grep 4840
```

2. Revisar permisos de archivos de certificados (si usa seguridad)

### Mensajes no se transfieren

1. Verificar los mapeos en `bridge_config.yaml`
2. Revisar la dirección del mapeo (`direction`)
3. Verificar los logs para errores de transformación de datos
4. Revisar el estado del buffer:
```bash
python buffer_monitor.py stats
python buffer_monitor.py pending
```

### Buffer SQLite lleno o con problemas

1. Ver estadísticas del buffer:
```bash
python buffer_monitor.py stats
```

2. Limpiar mensajes antiguos:
```bash
python buffer_monitor.py cleanup --days 1
```

3. Reiniciar mensajes atascados:
```bash
python buffer_monitor.py reset
```

4. Verificar integridad de la base de datos:
```bash
sqlite3 buffer.db "PRAGMA integrity_check;"
```

5. En caso extremo, hacer backup y recrear:
```bash
mv buffer.db buffer.db.backup
# El sistema creará una nueva base de datos al reiniciar
```

### Alto consumo de memoria o CPU

1. Verificar tamaño del buffer:
```bash
sqlite3 buffer.db "SELECT COUNT(*) FROM messages WHERE status='pending';"
```

2. Ajustar configuración en `bridge_config.yaml`:
```yaml
buffer_size: 5000  # Reducir si es necesario
worker_threads: 1  # Reducir threads de procesamiento
message_ttl_minutes: 30  # Reducir TTL
cleanup_interval: 60  # Limpiar más frecuentemente
```

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo licencia MIT. Ver `LICENSE` para más detalles.

## 🆘 Soporte

Para reportar problemas o solicitar nuevas características, por favor abre un issue en el repositorio del proyecto.

## 🔮 Roadmap

- [ ] Soporte para autenticación OAuth2 en MQTT
- [ ] Interfaz web de administración
- [ ] Métricas Prometheus integradas
- [ ] Soporte para clustering
- [ ] Transformaciones de datos personalizables con scripts Python
- [ ] Soporte para OPC-UA histórico
- [ ] Hot-reload de configuración
