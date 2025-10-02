# Guía de despliegue en Raspberry Pi 2

Esta guía resume los pasos necesarios para ejecutar el bridge MQTT↔OPC-UA de forma autónoma en una Raspberry Pi 2 (ARMv7, 1 GB RAM).

## 1. Preparar el sistema operativo

1. Flashea Raspberry Pi OS Lite (32 bits) y arranca la Pi.
2. Actualiza paquetes:
   ```bash
   sudo apt update
   sudo apt full-upgrade -y
   sudo reboot
   ```
3. Instala utilidades básicas:
   ```bash
   sudo apt install -y build-essential python3-dev libffi-dev pkg-config git
   ```

## 2. Instalar Python 3.11 (recomendado)

La Pi 2 suele traer Python 3.7. Instala una versión más reciente:
```bash
sudo apt install -y python3.11 python3.11-venv python3.11-dev
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
```

## 3. Instalar Mosquitto (broker MQTT)

```bash
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
```

## 4. Descargar el proyecto

```bash
cd /home/pi
git clone https://github.com/<tu-repo>/Bridge-MQTT-OPC-UA.git
cd Bridge-MQTT-OPC-UA
```

> Ajusta la URL al origen real del repositorio.

## 5. Crear entorno virtual ligero

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-minimal.txt
```

`requirements-minimal.txt` incluye únicamente dependencias esenciales, idóneas para hardware limitado.

## 6. Ajustar configuración

El archivo `bridge_config.yaml` ya está optimizado para la Pi 2:
- `buffer.max_size = 2000`
- `buffer.worker_threads = 1`
- `buffer.cleanup_interval = 120`
- Monitoreo deshabilitado (`monitoring.enabled = false`)

Asegúrate de editar los topics, nodos OPC-UA y credenciales MQTT según tu planta.

## 7. Probar manualmente

```bash
source venv/bin/activate
python mqtt_opcua_bridge.py
```

En otra terminal, publica mensajes de prueba:
```bash
mosquitto_pub -h localhost -t "sensores/temperatura/sala" -m "22.5"
```

Para verificar OPC-UA puedes usar el script opcional `test_opcua_client.py` (ver `install.sh`).

## 8. Configurar servicio `systemd`

Copia `systemd/mqtt-opcua-bridge.service` hacia `/etc/systemd/system` y ajusta la ruta si es necesario:
```bash
sudo cp systemd/mqtt-opcua-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mqtt-opcua-bridge
```

El servicio utiliza `/home/pi/Bridge-MQTT-OPC-UA/venv` y registra logs en `logs/bridge.log`.

## 9. Mantenimiento

- Monitorea el estado del buffer:
  ```bash
  source venv/bin/activate
  python buffer_monitor.py stats
  ```
- Haz copias de seguridad de `buffer.db` periódicamente (ubicado en `data/` o raíz según configuración).
- Revisa logs con `journalctl -u mqtt-opcua-bridge -f` o el archivo en `logs/`.

## 10. Optimización opcional

- Si necesitas métricas Prometheus, instala `prometheus-client` manualmente: `pip install prometheus-client` y reactiva `monitoring.enabled`.
- Para habilitar seguridad TLS en MQTT u OPC-UA, actualiza los campos correspondientes en `bridge_config.yaml` y coloca certificados en la Pi.

---

Con estos pasos, la Raspberry Pi 2 quedará ejecutando el bridge de manera autónoma al iniciar el sistema.
