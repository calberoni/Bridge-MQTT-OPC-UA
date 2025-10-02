from persistent_buffer import BufferedMessage
from config import SAPMapping, SAPInboundConfig, SAPOutboundConfig, SAPRetryConfig
from sap_bridge.sap_transformers import SAPTransformer


def test_sap_to_bridge_basic():
    mapping = SAPMapping(
        mapping_id="test",
        mqtt_topic="sap/test",
        opcua_node_id=None,
        direction="sap_to_bridge",
        priority="normal",
        resource_path="Test",
        inbound=SAPInboundConfig(
            destination="mqtt",
            target="sap/test",
            data_type="JSON",
            transform=None,
        ),
        outbound=SAPOutboundConfig(resource_path="Test"),
        retry=SAPRetryConfig(),
    )
    transformer = SAPTransformer()
    payload = {"foo": "bar"}
    buffered = transformer.sap_to_bridge(payload, mapping)
    assert buffered.destination == "mqtt"
    assert buffered.topic_or_node == "sap/test"
    assert buffered.value == payload


def test_bridge_to_sap_identity():
    mapping = SAPMapping(
        mapping_id="test",
        mqtt_topic="sap/test",
        opcua_node_id=None,
        direction="bridge_to_sap",
        priority="high",
        resource_path="Test",
        inbound=SAPInboundConfig(destination="mqtt", target="sap/test", data_type="JSON"),
        outbound=SAPOutboundConfig(resource_path="Test"),
        retry=SAPRetryConfig(),
    )
    transformer = SAPTransformer()
    message = BufferedMessage(
        id=1,
        source="mqtt",
        destination="sap",
        topic_or_node="sap/test",
        value={"foo": "bar"},
        data_type="JSON",
        mapping_id="bridge",
    )
    payload = transformer.bridge_to_sap(message, mapping)
    assert payload == {"foo": "bar"}
