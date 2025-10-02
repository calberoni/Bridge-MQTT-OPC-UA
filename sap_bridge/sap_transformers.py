"""Transformaciones entre SAP y el bridge."""

from typing import Any, Dict
from datetime import datetime

from persistent_buffer import BufferedMessage, MessagePriority
from config import SAPMapping
from sap_bridge.transform_utils import load_transform


def _identity_outbound(value: Any, mapping: SAPMapping, message: BufferedMessage) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"value": value}


def _identity_inbound(payload: Dict[str, Any], mapping: SAPMapping) -> Any:
    return payload


class SAPTransformer:
    """Gestiona transformaciones bidireccionales con SAP."""

    def __init__(self):
        self._outbound_cache = {}
        self._inbound_cache = {}

    def bridge_to_sap(self, message: BufferedMessage, mapping: SAPMapping) -> Dict[str, Any]:
        transform = self._get_outbound_transform(mapping)
        return transform(message.value, mapping, message)

    def sap_to_bridge(self, payload: Dict[str, Any], mapping: SAPMapping) -> BufferedMessage:
        transform = self._get_inbound_transform(mapping)
        value = transform(payload, mapping)
        priority = self._get_priority_value(mapping.priority)
        metadata = {
            "sap_mapping_id": mapping.mapping_id,
            "fetched_at": datetime.utcnow().isoformat(),
        }
        return BufferedMessage(
            source="sap",
            destination=mapping.inbound.destination,
            topic_or_node=mapping.inbound.target,
            value=value,
            data_type=mapping.inbound.data_type,
            mapping_id=mapping.mapping_id,
            priority=priority,
            metadata=metadata,
        )

    def _get_outbound_transform(self, mapping: SAPMapping):
        if mapping.mapping_id not in self._outbound_cache:
            self._outbound_cache[mapping.mapping_id] = load_transform(
                mapping.outbound.transform,
                _identity_outbound,
            )
        return self._outbound_cache[mapping.mapping_id]

    def _get_inbound_transform(self, mapping: SAPMapping):
        if mapping.mapping_id not in self._inbound_cache:
            self._inbound_cache[mapping.mapping_id] = load_transform(
                mapping.inbound.transform,
                _identity_inbound,
            )
        return self._inbound_cache[mapping.mapping_id]

    @staticmethod
    def _get_priority_value(name: str) -> int:
        try:
            return MessagePriority[name.upper()].value
        except KeyError:
            return MessagePriority.NORMAL.value
