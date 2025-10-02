"""Ejemplos de transformaciones SAP."""

from typing import Any, Dict

from config import SAPMapping
from persistent_buffer import BufferedMessage


def production_order_to_sap(value: Any, mapping: SAPMapping, message: BufferedMessage) -> Dict[str, Any]:
    """Ejemplo de transformación Bridge -> SAP."""
    if isinstance(value, dict):
        return {
            "Order": value.get("order"),
            "Status": value.get("status"),
            "Quantity": value.get("quantity", 0),
        }
    return {"value": value}


def sap_to_production_order(payload: Dict[str, Any], mapping: SAPMapping) -> Dict[str, Any]:
    """Ejemplo de transformación SAP -> Bridge."""
    return {
        "order": payload.get("Order"),
        "status": payload.get("Status"),
        "quantity": payload.get("Quantity"),
    }
