# Guía de Integración SAP

Esta guía describe cómo habilitar el SAP Bridge Connector para sincronizar datos entre MQTT/OPC-UA y servicios SAP.

## 1. Requisitos

- Endpoint SAP expuesto vía REST/OData o un API compatible.
- Credenciales válidas para autenticación básica u OAuth2.
- Estructuras/mapeos definidos entre objetos SAP y temas MQTT o nodos OPC-UA.

## 2. Configuración

En `bridge_config.yaml` habilita el bloque `sap`:

```yaml
sap:
  enabled: true
  endpoint: "https://sap.example.com/odata/bridge"
  timeout: 15
  poll_interval: 20
  auth:
    type: "basic"
    username: "sap_user"
    password: "sap_password"
  mappings:
    - mapping_id: "sap_production_orders"
      mqtt_topic: "sap/ordenes"
      direction: "bidirectional"
      resource_path: "ProductionOrders"
      priority: "high"
      outbound:
        resource_path: "ProductionOrders"
        transform: "sap_bridge.transformers_examples.production_order_to_sap"
      inbound:
        destination: "mqtt"
        target: "sap/ordenes"
        data_type: "JSON"
        transform: "sap_bridge.transformers_examples.sap_to_production_order"
      retry:
        max_attempts: 5
        backoff_seconds: 5
```

### Parámetros clave

- `endpoint`: URL base del servicio SAP (sin la ruta específica).
- `poll_interval`: Frecuencia (segundos) para consultar datos desde SAP.
- `auth.type`: `basic` u `oauth2`. Para OAuth2 define `token_url`, `client_id`, `client_secret` y `scope`.
- `mappings`: definiciones específicas. Cada mapping puede apuntar a un topic MQTT y/o nodo OPC-UA.
  - `direction`: controla el flujo (`bridge_to_sap`, `sap_to_bridge`, `bidirectional`).
  - `priority`: mapea a `MessagePriority` del buffer (`low`, `normal`, `high`, `critical`).
  - `outbound.transform` / `inbound.transform`: rutas a funciones Python (módulo.función) que convierten entre formatos.
  - `query_params`: parámetros extras para las consultas GET.

## 3. Transformaciones

Las transformaciones se cargan dinámicamente usando rutas tipo `package.module:function`. Ejemplo:

```python
def production_order_to_sap(value, mapping, message):
    return {
        "Order": value.get("order_id"),
        "Status": value.get("status"),
        "Quantity": value.get("quantity", 0),
    }
```

Guarda la función en un módulo disponible en PYTHONPATH y referencia su ruta en el mapping.

## 4. Ejecución

El bridge principal (`mqtt_opcua_bridge.py`) levanta los workers SAP automáticamente. Alternativas:

- **Servicio dedicado**: `python sap_sync.py --config bridge_config.yaml`.
- **Docker**: utiliza `docker-compose.sap.yml` para levantar el mock y el bridge.

## 5. Monitoreo

- El buffer conserva mensajes con destino `sap`. Usa `python buffer_monitor.py stats` para revisar estados.
- Métricas personalizadas pueden exponerse desde `monitoring/sap_metrics.py` (hook opcional para Prometheus).

## 6. Buenas Prácticas

- Define prioridades acordes a la criticidad del proceso.
- Ajusta `max_attempts` y `backoff_seconds` según la política de reintentos de SAP.
- Mantén transformaciones idempotentes; los reintentos pueden enviar el mismo payload varias veces.
- Valida respuestas de SAP en un entorno de pruebas (usa el mock incluido) antes de apuntar a producción.

## 7. Recursos Adicionales

- [Documentación SAP OData](https://help.sap.com/)
- Ejemplos de transformaciones adicionales en `sap_bridge/transformers_examples.py` (crea tus módulos personalizados).
