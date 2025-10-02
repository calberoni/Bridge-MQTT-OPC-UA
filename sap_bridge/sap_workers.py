"""Workers asíncronos para la integración SAP."""

import asyncio
import time
from typing import Any, Iterable, List

from config import BridgeConfig, SAPConfig, SAPMapping
from persistent_buffer import BufferedMessage, PersistentBuffer, MessagePriority
from sap_bridge.sap_connector import SAPConnector
from sap_bridge.sap_transformers import SAPTransformer

try:  # pragma: no cover - métricas opcionales
    from monitoring.sap_metrics import record_failure, record_success, observe_latency
except Exception:  # pragma: no cover
    def record_success(direction: str):
        return None

    def record_failure(direction: str):
        return None

    def observe_latency(seconds: float):
        return None


class SAPBridgeManager:
    """Coordina la sincronización entre el buffer y SAP."""

    def __init__(self, sap_config: SAPConfig, bridge_config: BridgeConfig, buffer: PersistentBuffer, logger):
        self.config = sap_config
        self.bridge_config = bridge_config
        self.buffer = buffer
        self.logger = logger.getChild("sap.manager")
        self.connector = SAPConnector(sap_config, self.logger)
        self.transformer = SAPTransformer()
        self._tasks: List[asyncio.Task] = []
        self._running = False

    async def start(self):
        if not self.config.enabled or self._running:
            return
        self._running = True
        loop = asyncio.get_running_loop()
        self._tasks = [
            loop.create_task(self._process_buffer_to_sap(), name="sap-buffer-to-sap"),
            loop.create_task(self._poll_sap_to_buffer(), name="sap-poll"),
        ]

    async def stop(self):
        if not self._running:
            return
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _process_buffer_to_sap(self):
        while self._running:
            messages = self.buffer.get_pending_messages(limit=10, destination="sap")
            if not messages:
                await asyncio.sleep(self.config.poll_interval)
                continue
            for message in messages:
                mapping_id = message.metadata.get("sap_mapping_id") if message.metadata else None
                mapping = self._get_mapping(mapping_id, message)
                if not mapping:
                    self.logger.error("SAP mapping no encontrado para mensaje %s", message.id)
                    self.buffer.mark_failed(message.id, "sap_mapping_missing")
                    continue
                try:
                    payload = self.transformer.bridge_to_sap(message, mapping)
                    start = time.monotonic()
                    if self.connector.push(payload, mapping):
                        observe_latency(time.monotonic() - start)
                        self.buffer.mark_completed(message.id)
                        self.logger.info("Bridge -> SAP completado id=%s", message.id)
                        record_success("bridge_to_sap")
                    else:
                        raise RuntimeError("SAP push failed")
                except Exception as exc:  # noqa: BLE001
                    self.logger.error("Error enviando a SAP id=%s: %s", message.id, exc)
                    self.buffer.mark_failed(message.id, str(exc))
                    record_failure("bridge_to_sap")

    async def _poll_sap_to_buffer(self):
        while self._running:
            for mapping in self.config.mappings:
                if mapping.direction not in ("sap_to_bridge", "bidirectional"):
                    continue
                try:
                    start = time.monotonic()
                    data = self.connector.fetch(mapping)
                    duration = time.monotonic() - start
                    if data is None:
                        record_failure("sap_to_bridge")
                    else:
                        observe_latency(duration)
                        record_success("sap_to_bridge")
                except Exception as exc:  # noqa: BLE001
                    self.logger.error("Error obteniendo de SAP %s: %s", mapping.mapping_id, exc)
                    data = None
                    record_failure("sap_to_bridge")
                if data is None:
                    continue
                for item in self._iterate_items(data):
                    buffered = self.transformer.sap_to_bridge(item, mapping)
                    buffered.metadata = buffered.metadata or {}
                    buffered.metadata.update({
                        "sap_mapping_id": mapping.mapping_id,
                        "origin": "sap",
                    })
                    buffered_id = self.buffer.add_message(buffered)
                    if buffered_id:
                        self.logger.debug("SAP -> buffer encolado id=%s", buffered_id)
            await asyncio.sleep(self.config.poll_interval)

    def _get_mapping(self, mapping_id: str, message: BufferedMessage) -> SAPMapping:
        if mapping_id:
            for mapping in self.config.mappings:
                if mapping.mapping_id == mapping_id:
                    return mapping
        topic = message.metadata.get("bridge_topic") if message.metadata else None
        node = message.metadata.get("bridge_node") if message.metadata else None
        for mapping in self.config.mappings:
            if mapping.direction in ("bridge_to_sap", "bidirectional") and (
                (topic and mapping.mqtt_topic == topic)
                or (node and mapping.opcua_node_id == node)
            ):
                return mapping
        return None

    @staticmethod
    def _iterate_items(data: Any) -> Iterable[Any]:
        if data is None:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if "value" in data and isinstance(data["value"], list):
                return data["value"]
            return [data]
        return [data]
