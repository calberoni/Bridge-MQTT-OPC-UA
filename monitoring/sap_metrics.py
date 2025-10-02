"""Hooks opcionales de métricas para SAP."""

try:
    from prometheus_client import Counter, Histogram
except ImportError:  # pragma: no cover
    Counter = Histogram = None  # type: ignore

SAP_MESSAGES_PROCESSED = Counter("sap_bridge_processed_total", "Mensajes procesados hacia SAP", ["direction"]) if Counter else None
SAP_MESSAGES_FAILED = Counter("sap_bridge_failed_total", "Mensajes fallidos hacia SAP", ["direction"]) if Counter else None
SAP_LATENCY = Histogram("sap_bridge_latency_seconds", "Latencia de operaciones SAP") if Histogram else None


def record_success(direction: str):
    if SAP_MESSAGES_PROCESSED:
        SAP_MESSAGES_PROCESSED.labels(direction=direction).inc()


def record_failure(direction: str):
    if SAP_MESSAGES_FAILED:
        SAP_MESSAGES_FAILED.labels(direction=direction).inc()


def observe_latency(seconds: float):
    if SAP_LATENCY:
        SAP_LATENCY.observe(seconds)
