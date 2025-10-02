# Playbook del Servidor SAP Simulado

Este documento describe cómo utilizar `sap_bridge/sap_mock_server.py` para pruebas locales.

## Inicio rápido

```bash
python sap_bridge/sap_mock_server.py
```

El servidor escucha por defecto en `http://0.0.0.0:8081`. Expone endpoints como:

- `GET /ProductionOrders` → devuelve una lista de órdenes ficticias.
- `POST /ProductionOrders` → almacena el payload recibido en memoria.

## Uso sugerido

1. Inicia el mock.
2. Configura `bridge_config.yaml` para apuntar a `http://localhost:8081/ProductionOrders`.
3. Ejecuta el bridge o `sap_sync.py` para sincronizar datos.
4. Observa las inserciones en el mock (se mantienen en memoria hasta reiniciar el proceso).

## Ejemplos cURL

```bash
# Insertar orden
curl -X POST http://localhost:8081/ProductionOrders \
     -H "Content-Type: application/json" \
     -d '{"Order":"100","Status":"OPEN","Quantity":3}'

# Consultar órdenes
curl http://localhost:8081/ProductionOrders
```

## Limitaciones

- Los datos se guardan solo en memoria.
- No se valida esquema ni autenticación.
- Únicamente soporta JSON.

Personaliza el mock según tus necesidades antes de usarlo con procesos críticos.
