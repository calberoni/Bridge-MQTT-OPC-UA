# config.py
"""
Configuración del Bridge MQTT-OPCUA con Buffer Persistente SQLite
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import yaml
import os

@dataclass
class MQTTConfig:
    """Configuración del cliente MQTT"""
    broker_host: str = "localhost"
    broker_port: int = 1883
    client_id: str = "mqtt_opcua_bridge"
    username: Optional[str] = None
    password: Optional[str] = None
    keep_alive: int = 60
    qos: int = 1
    tls_enabled: bool = False
    ca_cert: Optional[str] = None
    client_cert: Optional[str] = None
    client_key: Optional[str] = None
    reconnect_delay: int = 5
    max_reconnect_attempts: int = 10

@dataclass
class OPCUAConfig:
    """Configuración del servidor OPC-UA"""
    endpoint: str = "opc.tcp://0.0.0.0:4840/bridge/server/"
    server_name: str = "MQTT-OPCUA Bridge Server"
    namespace: str = "http://mqtt-opcua-bridge.com"
    security_policy: str = "NoSecurity"  # Basic256Sha256, Basic128Rsa15
    certificate: Optional[str] = None
    private_key: Optional[str] = None
    allow_anonymous: bool = True
    session_timeout: int = 3600  # segundos
    max_connections: int = 100

@dataclass
class BridgeMapping:
    """Mapeo entre topics MQTT y nodos OPC-UA"""
    mqtt_topic: str
    opcua_node_id: str
    data_type: str  # Boolean, Int32, Float, Double, String, DateTime, JSON
    direction: str  # mqtt_to_opcua, opcua_to_mqtt, bidirectional
    transform: Optional[str] = None  # Función de transformación personalizada
    priority: str = "normal"  # low, normal, high, critical
    description: Optional[str] = None

@dataclass
class BufferConfig:
    """Configuración del buffer persistente SQLite"""
    enabled: bool = True
    db_path: str = "buffer.db"
    max_size: int = 10000
    ttl_minutes: int = 60
    cleanup_interval: int = 300  # segundos
    batch_size: int = 20
    worker_threads: int = 4
    retry_max_attempts: int = 3
    retry_backoff_seconds: int = 5
    
    # Write-Ahead Logging para mejor performance
    wal_enabled: bool = True
    
    # Prioridades y sus pesos
    priority_weights: Dict[str, float] = field(default_factory=lambda: {
        'critical': 3.0,
        'high': 1.8,
        'normal': 1.0,
        'low': 0.6
    })
    
    # Límites por prioridad
    priority_limits: Dict[str, int] = field(default_factory=lambda: {
        'critical': 0,    # Sin límite
        'high': 5000,
        'normal': 3000,
        'low': 1000
    })

@dataclass
class OptimizationConfig:
    """Configuración de optimización automática"""
    enabled: bool = True
    profile: str = "balanced"  # low_latency, high_throughput, balanced, resource_constrained, burst_handling
    auto_adjust: bool = True
    check_interval: int = 300  # segundos
    
    # Umbrales para cambio de perfil
    latency_threshold_high: float = 5.0  # segundos
    latency_threshold_low: float = 1.0
    throughput_threshold_high: int = 1000  # mensajes/minuto
    throughput_threshold_low: int = 100
    pending_threshold_high: int = 5000
    pending_threshold_low: int = 100
    failure_rate_threshold: float = 10.0  # porcentaje

@dataclass
class MonitoringConfig:
    """Configuración de monitoreo y métricas"""
    enabled: bool = True
    metrics_interval: int = 30  # segundos
    export_metrics: bool = True
    metrics_port: int = 9090  # Para Prometheus
    
    # Alertas
    alerts_enabled: bool = True
    alert_email: Optional[str] = None
    alert_webhook: Optional[str] = None
    
    # Umbrales de alerta
    alert_pending_threshold: int = 8000
    alert_failure_rate: float = 20.0
    alert_latency_threshold: float = 10.0
    alert_stuck_messages_minutes: int = 5

@dataclass
class LoggingConfig:
    """Configuración de logging"""
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    file_enabled: bool = True
    file_path: str = "logs/bridge.log"
    file_rotation: str = "daily"  # daily, size, time
    file_retention_days: int = 30
    console_enabled: bool = True
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Logging específico por módulo
    module_levels: Dict[str, str] = field(default_factory=lambda: {
        'mqtt': 'INFO',
        'opcua': 'INFO',
        'buffer': 'INFO',
        'optimizer': 'INFO'
    })

@dataclass
class SAPAuthConfig:
    """Autenticación para SAP"""
    type: str = "basic"  # basic, oauth2
    username: Optional[str] = None
    password: Optional[str] = None
    token_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    scope: Optional[str] = None

@dataclass
class SAPRetryConfig:
    """Política de reintentos para SAP"""
    max_attempts: int = 3
    backoff_seconds: int = 5

@dataclass
class SAPInboundConfig:
    """Configuración inbound SAP -> Bridge"""
    destination: str = "mqtt"  # mqtt u opcua
    target: str = ""
    data_type: str = "JSON"
    transform: Optional[str] = None

@dataclass
class SAPOutboundConfig:
    """Configuración outbound Bridge -> SAP"""
    resource_path: str = ""
    transform: Optional[str] = None

@dataclass
class SAPMapping:
    """Mapeo entre SAP y MQTT/OPC-UA"""
    mapping_id: str
    mqtt_topic: Optional[str] = None
    opcua_node_id: Optional[str] = None
    direction: str = "bidirectional"  # bridge_to_sap, sap_to_bridge, bidirectional
    priority: str = "normal"
    resource_path: str = ""
    outbound: SAPOutboundConfig = field(default_factory=SAPOutboundConfig)
    inbound: SAPInboundConfig = field(default_factory=SAPInboundConfig)
    retry: SAPRetryConfig = field(default_factory=SAPRetryConfig)
    query_params: Optional[Dict[str, Any]] = None

@dataclass
class SAPConfig:
    """Configuración general de integración con SAP"""
    enabled: bool = False
    endpoint: str = ""
    timeout: int = 15
    poll_interval: int = 20
    auth: SAPAuthConfig = field(default_factory=SAPAuthConfig)
    mappings: List[SAPMapping] = field(default_factory=list)

@dataclass
class BridgeConfig:
    """Configuración general del bridge"""
    mqtt: MQTTConfig
    opcua: OPCUAConfig
    mappings: List[BridgeMapping]
    buffer: BufferConfig
    optimization: OptimizationConfig
    monitoring: MonitoringConfig
    logging: LoggingConfig
    sap: SAPConfig = field(default_factory=SAPConfig)
    
    # Configuración general
    name: str = "MQTT-OPCUA Bridge"
    description: str = "Bridge bidireccional entre MQTT y OPC-UA"
    version: str = "2.0.0"
    
    # Compatibilidad con configuración antigua
    log_level: str = "INFO"  # Deprecated, usar logging.level
    reconnect_interval: int = 5  # Deprecated, usar mqtt.reconnect_delay
    buffer_size: int = 10000  # Deprecated, usar buffer.max_size
    persistence_enabled: bool = True  # Deprecated, usar buffer.enabled
    persistence_file: str = "buffer.db"  # Deprecated, usar buffer.db_path
    
    # Nuevos parámetros
    message_ttl_minutes: int = 60  # Deprecated, usar buffer.ttl_minutes
    cleanup_interval: int = 300  # Deprecated, usar buffer.cleanup_interval
    worker_threads: int = 4  # Deprecated, usar buffer.worker_threads

def load_config(config_file: str = "bridge_config.yaml") -> BridgeConfig:
    """Carga la configuración desde un archivo YAML con validación"""
    
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {config_file}")
    
    with open(config_file, 'r') as f:
        config_dict = yaml.safe_load(f)
    
    # Configuración MQTT
    mqtt_config = MQTTConfig(**config_dict.get('mqtt', {}))
    
    # Configuración OPC-UA
    opcua_config = OPCUAConfig(**config_dict.get('opcua', {}))
    
    # Mapeos
    mappings = []
    for mapping in config_dict.get('mappings', []):
        mappings.append(BridgeMapping(**mapping))
    
    # Validar mapeos
    _validate_mappings(mappings)
    
    # Configuración del buffer
    buffer_dict = config_dict.get('buffer', {})
    # Compatibilidad con configuración antigua
    if 'buffer_size' in config_dict and 'max_size' not in buffer_dict:
        buffer_dict['max_size'] = config_dict['buffer_size']
    if 'persistence_file' in config_dict and 'db_path' not in buffer_dict:
        buffer_dict['db_path'] = config_dict['persistence_file']
    if 'message_ttl_minutes' in config_dict and 'ttl_minutes' not in buffer_dict:
        buffer_dict['ttl_minutes'] = config_dict['message_ttl_minutes']
    if 'cleanup_interval' in config_dict and 'cleanup_interval' not in buffer_dict:
        buffer_dict['cleanup_interval'] = config_dict['cleanup_interval']
    if 'worker_threads' in config_dict and 'worker_threads' not in buffer_dict:
        buffer_dict['worker_threads'] = config_dict['worker_threads']
    
    buffer_config = BufferConfig(**buffer_dict)
    
    # Configuración de optimización
    optimization_config = OptimizationConfig(**config_dict.get('optimization', {}))
    
    # Configuración de monitoreo
    monitoring_config = MonitoringConfig(**config_dict.get('monitoring', {}))
    
    # Configuración de logging
    logging_dict = config_dict.get('logging', {})
    # Compatibilidad con configuración antigua
    if 'log_level' in config_dict and 'level' not in logging_dict:
        logging_dict['level'] = config_dict['log_level']
    
    logging_config = LoggingConfig(**logging_dict)

    # Configuración SAP
    sap_dict = config_dict.get('sap', {})
    auth_config = SAPAuthConfig(**sap_dict.get('auth', {}))
    sap_mappings = []
    for mapping_cfg in sap_dict.get('mappings', []):
        outbound_cfg = SAPOutboundConfig(**mapping_cfg.get('outbound', {}))
        inbound_cfg = SAPInboundConfig(**mapping_cfg.get('inbound', {}))
        retry_cfg = SAPRetryConfig(**mapping_cfg.get('retry', {}))
        sap_mappings.append(SAPMapping(
            mapping_id=mapping_cfg.get('mapping_id'),
            mqtt_topic=mapping_cfg.get('mqtt_topic'),
            opcua_node_id=mapping_cfg.get('opcua_node_id'),
            direction=mapping_cfg.get('direction', 'bidirectional'),
            priority=mapping_cfg.get('priority', 'normal'),
            resource_path=mapping_cfg.get('resource_path', ''),
            outbound=outbound_cfg,
            inbound=inbound_cfg,
            retry=retry_cfg,
            query_params=mapping_cfg.get('query_params')
        ))

    sap_config = SAPConfig(
        enabled=sap_dict.get('enabled', False),
        endpoint=sap_dict.get('endpoint', ''),
        timeout=sap_dict.get('timeout', 15),
        poll_interval=sap_dict.get('poll_interval', 20),
        auth=auth_config,
        mappings=sap_mappings
    )

    _validate_sap_config(sap_config)

    # Crear configuración del bridge
    bridge_config = BridgeConfig(
        mqtt=mqtt_config,
        opcua=opcua_config,
        mappings=mappings,
        buffer=buffer_config,
        optimization=optimization_config,
        monitoring=monitoring_config,
        logging=logging_config,
        sap=sap_config,
        **{k: v for k, v in config_dict.items() 
           if k not in ['mqtt', 'opcua', 'mappings', 'buffer', 'optimization', 'monitoring', 'logging', 'sap']}
    )
    
    return bridge_config

def _validate_mappings(mappings: List[BridgeMapping]):
    """Valida los mapeos configurados"""
    valid_directions = ['mqtt_to_opcua', 'opcua_to_mqtt', 'bidirectional']
    valid_data_types = ['Boolean', 'Int32', 'Float', 'Double', 'String', 'DateTime', 'JSON']
    valid_priorities = ['low', 'normal', 'high', 'critical']
    
    seen_topics = set()
    seen_nodes = set()
    
    for mapping in mappings:
        # Validar dirección
        if mapping.direction not in valid_directions:
            raise ValueError(f"Dirección inválida '{mapping.direction}' para {mapping.mqtt_topic}")
        
        # Validar tipo de dato
        if mapping.data_type not in valid_data_types:
            raise ValueError(f"Tipo de dato inválido '{mapping.data_type}' para {mapping.mqtt_topic}")
        
        # Validar prioridad
        if mapping.priority not in valid_priorities:
            raise ValueError(f"Prioridad inválida '{mapping.priority}' para {mapping.mqtt_topic}")
        
        # Detectar duplicados
        if mapping.mqtt_topic in seen_topics:
            logging.warning(f"Topic MQTT duplicado: {mapping.mqtt_topic}")
        seen_topics.add(mapping.mqtt_topic)
        
        if mapping.opcua_node_id in seen_nodes:
            logging.warning(f"Nodo OPC-UA duplicado: {mapping.opcua_node_id}")
        seen_nodes.add(mapping.opcua_node_id)


def _validate_sap_config(sap_config: SAPConfig):
    """Valida la configuración SAP"""
    if not sap_config.enabled:
        return
    valid_directions = {'bridge_to_sap', 'sap_to_bridge', 'bidirectional'}
    valid_destinations = {'mqtt', 'opcua'}
    valid_priorities = {'low', 'normal', 'high', 'critical'}

    for mapping in sap_config.mappings:
        if mapping.direction not in valid_directions:
            raise ValueError(f"Dirección SAP inválida '{mapping.direction}' en {mapping.mapping_id}")
        if mapping.inbound.destination not in valid_destinations:
            raise ValueError(f"Destino SAP inválido '{mapping.inbound.destination}' en {mapping.mapping_id}")
        if mapping.priority not in valid_priorities:
            raise ValueError(f"Prioridad SAP inválida '{mapping.priority}' en {mapping.mapping_id}")
        if mapping.direction in ('bridge_to_sap', 'bidirectional') and not (mapping.mqtt_topic or mapping.opcua_node_id):
            raise ValueError(f"Mapeo SAP {mapping.mapping_id} requiere mqtt_topic u opcua_node_id")
        if mapping.direction in ('sap_to_bridge', 'bidirectional') and not mapping.inbound.target:
            raise ValueError(f"Mapeo SAP {mapping.mapping_id} requiere inbound.target")

def setup_logging(config: LoggingConfig = None):
    """Configura el sistema de logging con opciones avanzadas"""
    if config is None:
        config = LoggingConfig()
    
    # Crear directorio de logs si no existe
    if config.file_enabled:
        log_dir = os.path.dirname(config.file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
    
    # Configurar handlers
    handlers = []
    
    # Console handler
    if config.console_enabled:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(config.format))
        handlers.append(console_handler)
    
    # File handler con rotación
    if config.file_enabled:
        if config.file_rotation == 'daily':
            from logging.handlers import TimedRotatingFileHandler
            file_handler = TimedRotatingFileHandler(
                config.file_path,
                when='midnight',
                interval=1,
                backupCount=config.file_retention_days
            )
        elif config.file_rotation == 'size':
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                config.file_path,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            )
        else:
            file_handler = logging.FileHandler(config.file_path)
        
        file_handler.setFormatter(logging.Formatter(config.format))
        handlers.append(file_handler)
    
    # Configurar logger raíz
    logging.basicConfig(
        level=getattr(logging, config.level),
        handlers=handlers
    )
    
    # Configurar niveles por módulo
    for module, level in config.module_levels.items():
        logging.getLogger(module).setLevel(getattr(logging, level))
    
    # Intentar usar colorlog si está disponible
    try:
        import colorlog
        if config.console_enabled:
            color_formatter = colorlog.ColoredFormatter(
                f"%(log_color)s{config.format}",
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            )
            handlers[0].setFormatter(color_formatter)
    except ImportError:
        pass
    
    return logging.getLogger(__name__)

def save_config(config: BridgeConfig, config_file: str = "bridge_config.yaml"):
    """Guarda la configuración en un archivo YAML"""
    import dataclasses
    
    def dataclass_to_dict(obj):
        """Convierte dataclass a diccionario recursivamente"""
        if dataclasses.is_dataclass(obj):
            return {
                field.name: dataclass_to_dict(getattr(obj, field.name))
                for field in dataclasses.fields(obj)
                if not field.name.startswith('_')
            }
        elif isinstance(obj, list):
            return [dataclass_to_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: dataclass_to_dict(value) for key, value in obj.items()}
        else:
            return obj
    
    config_dict = dataclass_to_dict(config)
    
    with open(config_file, 'w') as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

def generate_default_config(config_file: str = "bridge_config_default.yaml"):
    """Genera un archivo de configuración por defecto con todas las opciones"""
    
    # Crear configuración por defecto
    default_config = BridgeConfig(
        mqtt=MQTTConfig(),
        opcua=OPCUAConfig(),
        mappings=[
            BridgeMapping(
                mqtt_topic="sensores/temperatura/sala",
                opcua_node_id="ns=2;s=Temperature.Room",
                data_type="Float",
                direction="mqtt_to_opcua",
                priority="normal",
                description="Sensor de temperatura de la sala"
            ),
            BridgeMapping(
                mqtt_topic="actuadores/luz/sala",
                opcua_node_id="ns=2;s=Light.Room",
                data_type="Boolean",
                direction="bidirectional",
                priority="high",
                description="Control de iluminación"
            ),
        ],
        buffer=BufferConfig(),
        optimization=OptimizationConfig(),
        monitoring=MonitoringConfig(),
        logging=LoggingConfig()
    )
    
    save_config(default_config, config_file)
    print(f"Configuración por defecto generada: {config_file}")
    
    return default_config
