import requests_mock

from config import SAPAuthConfig, SAPConfig, SAPMapping, SAPOutboundConfig, SAPRetryConfig, SAPInboundConfig
from sap_bridge.sap_connector import SAPConnector


def build_config():
    return SAPConfig(
        enabled=True,
        endpoint="https://sap.example.com/api",
        auth=SAPAuthConfig(type="basic", username="user", password="pass"),
        mappings=[],
    )


def test_push_success():
    config = build_config()
    mapping = SAPMapping(
        mapping_id="test",
        resource_path="orders",
        direction="bridge_to_sap",
        priority="normal",
        inbound=SAPInboundConfig(destination="mqtt", target="sap/test", data_type="JSON"),
        outbound=SAPOutboundConfig(resource_path="orders"),
        retry=SAPRetryConfig(max_attempts=1, backoff_seconds=0),
    )
    connector = SAPConnector(config, _DummyLogger())
    with requests_mock.Mocker() as m:
        m.post("https://sap.example.com/api/orders", json={"status": "ok"}, status_code=201)
        assert connector.push({"foo": "bar"}, mapping) is True


def test_fetch_returns_payload():
    config = build_config()
    mapping = SAPMapping(
        mapping_id="test",
        resource_path="orders",
        direction="sap_to_bridge",
        priority="normal",
        inbound=SAPInboundConfig(destination="mqtt", target="sap/test", data_type="JSON"),
        outbound=SAPOutboundConfig(resource_path="orders"),
        retry=SAPRetryConfig(max_attempts=1, backoff_seconds=0),
    )
    connector = SAPConnector(config, _DummyLogger())
    with requests_mock.Mocker() as m:
        m.get("https://sap.example.com/api/orders", json={"value": []}, status_code=200)
        payload = connector.fetch(mapping)
        assert payload == {"value": []}


class _DummyLogger:
    def getChild(self, name):  # noqa: D401
        return self

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass
