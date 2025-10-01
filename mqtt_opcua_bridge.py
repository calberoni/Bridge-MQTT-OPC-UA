# mqtt_opcua_bridge.py
"""
Bridge bidireccional MQTT ↔ OPC-UA con buffer persistente
"""

import asyncio
import json
import signal
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from dataclasses import asdict
import threading

import paho.mqtt.client as mqtt
from asyncua import Server, Node, ua
from asyncua.common.subscription import SubHandler
import numpy as np

from config import BridgeConfig, BridgeMapping, load_config, setup_logging
from persistent_buffer import PersistentBuffer, BufferedMessage, MessagePriority

class DataTransformer:
    """Maneja las transformaciones de datos entre MQTT y OPC-UA"""
    
    @staticmethod
    def mqtt_to_opcua(value: Any, data_type: str) -> Any:
        """Convierte valores MQTT a tipos OPC-UA"""
        if data_type == "Boolean":
            return bool(value)
        elif data_type == "Int32":
            return int(value)
        elif data_type == "Float":
            return float(value)
        elif data_type == "Double":
            return float(value)
        elif data_type == "String":
            return str(value)
        elif data_type == "DateTime":
            return datetime.fromisoformat(value) if isinstance(value, str) else value
        elif data_type == "JSON":
            return json.dumps(value) if not isinstance(value, str) else value
        else:
            return value
    
    @staticmethod
    def opcua_to_mqtt(value: Any, data_type: str) -> Any:
        """Convierte valores OPC-UA a formato MQTT"""
        if isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, (bool, int, float, str)):
            return value
        elif isinstance(value, bytes):
            return value.decode('utf-8')
        else:
            return str(value)

class MQTTClient:
    """Cliente MQTT con capacidades de reconexión"""
    
    def __init__(self, config: BridgeConfig, buffer: PersistentBuffer):
        self.config = config.mqtt
        self.bridge_config = config
        self.buffer = buffer
        self.client = mqtt.Client(self.config.client_id)
        self.logger = setup_logging(config.log_level)
        self.connected = False
        self.subscribed_topics = set()
        
        self._setup_client()
    
    def _setup_client(self):
        """Configura el cliente MQTT"""
        # Configurar autenticación
        if self.config.username and self.config.password:
            self.client.username_pw_set(self.config.username, self.config.password)
        
        # Configurar TLS/SSL
        if self.config.tls_enabled:
            self.client.tls_set(
                ca_certs=self.config.ca_cert,
                certfile=self.config.client_cert,
                keyfile=self.config.client_key
            )
        
        # Configurar callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_subscribe = self._on_subscribe
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback de conexión MQTT"""
        if rc == 0:
            self.connected = True
            self.logger.info(f"Conectado al broker MQTT: {self.config.broker_host}:{self.config.broker_port}")
            # Suscribirse a los topics configurados
            self._subscribe_to_topics()
        else:
            self.logger.error(f"Error de conexión MQTT, código: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback de desconexión MQTT"""
        self.connected = False
        if rc != 0:
            self.logger.warning(f"Desconexión inesperada del broker MQTT, código: {rc}")
            self._reconnect()
    
    def _on_message(self, client, userdata, msg):
        """Callback de mensaje MQTT recibido"""
        try:
            # Decodificar payload
            payload = msg.payload.decode('utf-8')
            
            # Intentar parsear como JSON
            try:
                value = json.loads(payload)
            except json.JSONDecodeError:
                value = payload
            
            # Encontrar el mapeo correspondiente
            for mapping in self.bridge_config.mappings:
                if mapping.mqtt_topic == msg.topic and mapping.direction in ["mqtt_to_opcua", "bidirectional"]:
                    # Crear mensaje buffered
                    buffered_msg = BufferedMessage(
                        source='mqtt',
                        destination='opcua',
                        topic_or_node=msg.topic,
                        value=value,
                        data_type=mapping.data_type,
                        mapping_id=f"{mapping.mqtt_topic}:{mapping.opcua_node_id}",
                        priority=MessagePriority.NORMAL.value,
                        metadata={'mapping': asdict(mapping), 'qos': msg.qos}
                    )
                    
                    # Agregar al buffer persistente
                    message_id = self.buffer.add_message(buffered_msg)
                    if message_id:
                        self.logger.debug(f"MQTT mensaje recibido y buffereado: {msg.topic} = {value}, ID={message_id}")
                    else:
                        self.logger.error(f"Error agregando mensaje al buffer: {msg.topic}")
                    
        except Exception as e:
            self.logger.error(f"Error procesando mensaje MQTT: {e}")ua", "bidirectional"]:
                    # Agregar a la cola para procesar en OPC-UA
                    self.message_queue.put({
                        'source': 'mqtt',
                        'topic': msg.topic,
                        'value': value,
                        'mapping': mapping,
                        'timestamp': datetime.now()
                    })
                    self.logger.debug(f"MQTT mensaje recibido: {msg.topic} = {value}")
                    
        except Exception as e:
            self.logger.error(f"Error procesando mensaje MQTT: {e}")
    
    def _on_subscribe(self, client, userdata, mid, granted_qos):
        """Callback de suscripción MQTT"""
        self.logger.info(f"Suscripción MQTT exitosa, QoS: {granted_qos}")
    
    def _subscribe_to_topics(self):
        """Suscribe a todos los topics configurados"""
        for mapping in self.bridge_config.mappings:
            if mapping.direction in ["mqtt_to_opcua", "bidirectional"]:
                if mapping.mqtt_topic not in self.subscribed_topics:
                    self.client.subscribe(mapping.mqtt_topic, self.config.qos)
                    self.subscribed_topics.add(mapping.mqtt_topic)
                    self.logger.info(f"Suscrito a topic MQTT: {mapping.mqtt_topic}")
    
    def _reconnect(self):
        """Intenta reconectar al broker MQTT"""
        while not self.connected:
            try:
                self.logger.info("Intentando reconectar al broker MQTT...")
                self.client.reconnect()
                break
            except Exception as e:
                self.logger.error(f"Error de reconexión: {e}")
                asyncio.sleep(self.bridge_config.reconnect_interval)
    
    def connect(self):
        """Conecta al broker MQTT"""
        try:
            self.client.connect(
                self.config.broker_host,
                self.config.broker_port,
                self.config.keep_alive
            )
            self.client.loop_start()
            return True
        except Exception as e:
            self.logger.error(f"Error conectando al broker MQTT: {e}")
            return False
    
    def publish(self, topic: str, value: Any, qos: int = None):
        """Publica un mensaje en MQTT"""
        if not self.connected:
            self.logger.warning("No conectado al broker MQTT")
            return False
        
        try:
            # Serializar el valor
            if isinstance(value, (dict, list)):
                payload = json.dumps(value)
            else:
                payload = str(value)
            
            # Publicar
            result = self.client.publish(
                topic,
                payload,
                qos=qos or self.config.qos
            )
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.debug(f"MQTT publicado: {topic} = {payload}")
                return True
            else:
                self.logger.error(f"Error publicando en MQTT: {result.rc}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error publicando mensaje MQTT: {e}")
            return False
    
    def disconnect(self):
        """Desconecta del broker MQTT"""
        self.client.loop_stop()
        self.client.disconnect()
        self.logger.info("Desconectado del broker MQTT")

class OPCUASubscriptionHandler(SubHandler):
    """Manejador de suscripciones OPC-UA"""
    
    def __init__(self, buffer: PersistentBuffer, mappings: list, logger):
        self.buffer = buffer
        self.mappings = mappings
        self.logger = logger
    
    def datachange_notification(self, node: Node, val, data):
        """Callback cuando cambia un valor en OPC-UA"""
        try:
            node_id = node.nodeid.to_string()
            
            # Encontrar el mapeo correspondiente
            for mapping in self.mappings:
                if mapping.opcua_node_id == node_id and mapping.direction in ["opcua_to_mqtt", "bidirectional"]:
                    # Crear mensaje buffered
                    buffered_msg = BufferedMessage(
                        source='opcua',
                        destination='mqtt',
                        topic_or_node=node_id,
                        value=val,
                        data_type=mapping.data_type,
                        mapping_id=f"{mapping.mqtt_topic}:{mapping.opcua_node_id}",
                        priority=MessagePriority.NORMAL.value,
                        metadata={'mapping': asdict(mapping)}
                    )
                    
                    # Agregar al buffer persistente
                    message_id = self.buffer.add_message(buffered_msg)
                    if message_id:
                        self.logger.debug(f"OPC-UA cambio detectado y buffereado: {node_id} = {val}, ID={message_id}")
                    else:
                        self.logger.error(f"Error agregando cambio OPC-UA al buffer: {node_id}")
                    
        except Exception as e:
            self.logger.error(f"Error procesando cambio OPC-UA: {e}")

class OPCUAServer:
    """Servidor OPC-UA con nodos dinámicos"""
    
    def __init__(self, config: BridgeConfig, buffer: PersistentBuffer):
        self.config = config.opcua
        self.bridge_config = config
        self.buffer = buffer
        self.logger = setup_logging(config.log_level)
        self.server = None
        self.nodes = {}
        self.subscription = None
        self.handler = None
        
    async def init(self):
        """Inicializa el servidor OPC-UA"""
        self.server = Server()
        await self.server.init()
        
        # Configurar endpoint
        self.server.set_endpoint(self.config.endpoint)
        self.server.set_server_name(self.config.server_name)
        
        # Configurar seguridad
        if self.config.security_policy != "NoSecurity":
            await self._setup_security()
        
        # Registrar namespace
        uri = self.config.namespace
        self.idx = await self.server.register_namespace(uri)
        
        # Crear nodos según los mapeos
        await self._create_nodes()
        
        # Configurar suscripciones
        await self._setup_subscriptions()
        
        self.logger.info(f"Servidor OPC-UA inicializado en: {self.config.endpoint}")
    
    async def _setup_security(self):
        """Configura la seguridad del servidor OPC-UA"""
        if self.config.certificate and self.config.private_key:
            await self.server.load_certificate(self.config.certificate)
            await self.server.load_private_key(self.config.private_key)
        
        # Configurar políticas de seguridad
        if not self.config.allow_anonymous:
            self.server.set_security_policy([ua.SecurityPolicyType.Basic256Sha256])
    
    async def _create_nodes(self):
        """Crea los nodos OPC-UA según los mapeos"""
        root = self.server.get_objects_node()
        
        # Crear carpeta para el bridge
        bridge_folder = await root.add_folder(self.idx, "MQTTBridge")
        
        for mapping in self.bridge_config.mappings:
            try:
                # Determinar el tipo de dato OPC-UA
                variant_type = self._get_variant_type(mapping.data_type)
                
                # Crear el nodo
                node_name = mapping.opcua_node_id.split(".")[-1]
                node = await bridge_folder.add_variable(
                    self.idx,
                    node_name,
                    self._get_initial_value(mapping.data_type),
                    varianttype=variant_type
                )
                
                # Hacer el nodo escribible si es bidireccional o opcua_to_mqtt
                if mapping.direction in ["opcua_to_mqtt", "bidirectional"]:
                    await node.set_writable()
                
                # Guardar referencia al nodo
                self.nodes[mapping.opcua_node_id] = node
                
                self.logger.info(f"Nodo OPC-UA creado: {mapping.opcua_node_id}")
                
            except Exception as e:
                self.logger.error(f"Error creando nodo {mapping.opcua_node_id}: {e}")
    
    def _get_variant_type(self, data_type: str):
        """Obtiene el tipo de variante OPC-UA"""
        type_mapping = {
            "Boolean": ua.VariantType.Boolean,
            "Int32": ua.VariantType.Int32,
            "Float": ua.VariantType.Float,
            "Double": ua.VariantType.Double,
            "String": ua.VariantType.String,
            "DateTime": ua.VariantType.DateTime,
            "JSON": ua.VariantType.String
        }
        return type_mapping.get(data_type, ua.VariantType.String)
    
    def _get_initial_value(self, data_type: str):
        """Obtiene un valor inicial según el tipo de dato"""
        initial_values = {
            "Boolean": False,
            "Int32": 0,
            "Float": 0.0,
            "Double": 0.0,
            "String": "",
            "DateTime": datetime.now(),
            "JSON": "{}"
        }
        return initial_values.get(data_type, "")
    
    async def _setup_subscriptions(self):
        """Configura las suscripciones a cambios en los nodos"""
        # Crear handler de suscripción
        self.handler = OPCUASubscriptionHandler(
            self.buffer,
            self.bridge_config.mappings,
            self.logger
        )
        
        # Crear suscripción
        self.subscription = await self.server.create_subscription(500, self.handler)
        
        # Suscribir a los nodos configurados
        for mapping in self.bridge_config.mappings:
            if mapping.direction in ["opcua_to_mqtt", "bidirectional"]:
                if mapping.opcua_node_id in self.nodes:
                    node = self.nodes[mapping.opcua_node_id]
                    await self.subscription.subscribe_data_change(node)
                    self.logger.info(f"Suscrito a cambios en nodo: {mapping.opcua_node_id}")
    
    async def update_node_value(self, node_id: str, value: Any):
        """Actualiza el valor de un nodo OPC-UA"""
        if node_id in self.nodes:
            try:
                node = self.nodes[node_id]
                await node.write_value(value)
                self.logger.debug(f"Nodo actualizado: {node_id} = {value}")
                return True
            except Exception as e:
                self.logger.error(f"Error actualizando nodo {node_id}: {e}")
                return False
        else:
            self.logger.warning(f"Nodo no encontrado: {node_id}")
            return False
    
    async def start(self):
        """Inicia el servidor OPC-UA"""
        await self.server.start()
        self.logger.info("Servidor OPC-UA iniciado")
    
    async def stop(self):
        """Detiene el servidor OPC-UA"""
        if self.subscription:
            await self.subscription.delete()
        await self.server.stop()
        self.logger.info("Servidor OPC-UA detenido")

class MQTTOPCUABridge:
    """Bridge principal que coordina MQTT y OPC-UA con buffer persistente"""
    
    def __init__(self, config_file: str = "bridge_config.yaml"):
        self.config = load_config(config_file)
        self.logger = setup_logging(self.config.log_level)
        
        # Buffer persistente con SQLite
        self.buffer = PersistentBuffer(
            db_path=self.config.persistence_file.replace('.json', '.db'),
            max_size=self.config.buffer_size,
            ttl_minutes=getattr(self.config, 'message_ttl_minutes', 60),
            cleanup_interval=getattr(self.config, 'cleanup_interval', 300),
            logger=self.logger
        )
        
        self.mqtt_client = None
        self.opcua_server = None
        self.running = False
        self.transformer = DataTransformer()
        
        # Threads de procesamiento
        self.process_threads = []
        self.num_workers = getattr(self.config, 'worker_threads', 2)
        
        # Estadísticas de rendimiento
        self.performance_stats = {
            'messages_processed': 0,
            'messages_failed': 0,
            'processing_time_total': 0,
            'last_processed': None
        }
    
    async def _process_messages(self):
        """Procesa mensajes del buffer persistente"""
        while self.running:
            try:
                # Obtener batch de mensajes del buffer
                messages = self.buffer.get_pending_messages(
                    limit=10,
                    destination='opcua'
                )
                
                for message in messages:
                    if not self.running:
                        break
                    
                    try:
                        if message.destination == 'opcua':
                            # Mensaje para OPC-UA
                            await self._handle_mqtt_to_opcua_message(message)
                        
                        # Marcar como completado
                        self.buffer.mark_completed(message.id)
                        self.performance_stats['messages_processed'] += 1
                        self.performance_stats['last_processed'] = datetime.now()
                        
                    except Exception as e:
                        self.logger.error(f"Error procesando mensaje ID={message.id}: {e}")
                        self.buffer.mark_failed(message.id, str(e))
                        self.performance_stats['messages_failed'] += 1
                
                # Procesar mensajes para MQTT en thread separado
                await self._process_mqtt_messages()
                
                # Si no hay mensajes, esperar un poco
                if not messages:
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                self.logger.error(f"Error en loop de procesamiento: {e}")
                await asyncio.sleep(1)
    
    async def _process_mqtt_messages(self):
        """Procesa mensajes destinados a MQTT"""
        messages = self.buffer.get_pending_messages(
            limit=10,
            destination='mqtt'
        )
        
        for message in messages:
            if not self.running:
                break
            
            try:
                if message.destination == 'mqtt':
                    # Mensaje para MQTT - ejecutar en thread separado
                    await self._handle_opcua_to_mqtt_message(message)
                
                # Marcar como completado
                self.buffer.mark_completed(message.id)
                self.performance_stats['messages_processed'] += 1
                
            except Exception as e:
                self.logger.error(f"Error procesando mensaje MQTT ID={message.id}: {e}")
                self.buffer.mark_failed(message.id, str(e))
                self.performance_stats['messages_failed'] += 1
    
    async def _handle_mqtt_to_opcua_message(self, message: BufferedMessage):
        """Maneja mensajes provenientes de MQTT hacia OPC-UA"""
        try:
            # Recuperar mapeo desde metadata
            mapping_data = message.metadata.get('mapping')
            if not mapping_data:
                raise ValueError("No se encontró información de mapeo")
            
            mapping = BridgeMapping(**mapping_data)
            
            # Transformar el valor si es necesario
            transformed_value = self.transformer.mqtt_to_opcua(message.value, message.data_type)
            
            # Actualizar nodo OPC-UA
            if self.opcua_server:
                success = await self.opcua_server.update_node_value(
                    mapping.opcua_node_id,
                    transformed_value
                )
                
                if success:
                    self.logger.info(f"MQTT->OPCUA: {mapping.mqtt_topic} -> {mapping.opcua_node_id} = {transformed_value}")
                else:
                    raise Exception(f"Fallo al actualizar nodo OPC-UA {mapping.opcua_node_id}")
            else:
                raise Exception("Servidor OPC-UA no disponible")
                
        except Exception as e:
            self.logger.error(f"Error manejando mensaje MQTT->OPCUA: {e}")
            raise
    
    async def _handle_opcua_to_mqtt_message(self, message: BufferedMessage):
        """Maneja cambios provenientes de OPC-UA hacia MQTT"""
        try:
            # Recuperar mapeo desde metadata
            mapping_data = message.metadata.get('mapping')
            if not mapping_data:
                raise ValueError("No se encontró información de mapeo")
            
            mapping = BridgeMapping(**mapping_data)
            
            # Transformar el valor si es necesario
            transformed_value = self.transformer.opcua_to_mqtt(message.value, message.data_type)
            
            # Publicar en MQTT
            if self.mqtt_client and self.mqtt_client.connected:
                # Ejecutar en thread separado para no bloquear asyncio
                success = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.mqtt_client.publish,
                    mapping.mqtt_topic,
                    transformed_value
                )
                
                if success:
                    self.logger.info(f"OPCUA->MQTT: {mapping.opcua_node_id} -> {mapping.mqtt_topic} = {transformed_value}")
                else:
                    raise Exception(f"Fallo al publicar en MQTT topic {mapping.mqtt_topic}")
            else:
                raise Exception("Cliente MQTT no conectado")
                
        except Exception as e:
            self.logger.error(f"Error manejando cambio OPCUA->MQTT: {e}")
            raise
    
    def _print_statistics(self):
        """Imprime estadísticas periódicamente"""
        while self.running:
            try:
                import time
                time.sleep(30)  # Cada 30 segundos
                
                buffer_stats = self.buffer.get_statistics()
                
                self.logger.info("=== Estadísticas del Bridge ===")
                self.logger.info(f"Buffer: {buffer_stats.get('buffer_size', 0)}/{buffer_stats.get('max_size', 0)} "
                               f"({buffer_stats.get('utilization_percent', 0):.1f}% utilizado)")
                self.logger.info(f"Mensajes procesados: {self.performance_stats['messages_processed']}")
                self.logger.info(f"Mensajes fallidos: {self.performance_stats['messages_failed']}")
                
                if buffer_stats.get('status_counts'):
                    self.logger.info(f"Estados: {buffer_stats['status_counts']}")
                
                if buffer_stats.get('route_counts'):
                    for route in buffer_stats['route_counts']:
                        self.logger.info(f"  {route['source']}->{route['destination']}: {route['count']} pendientes")
                
            except Exception as e:
                self.logger.error(f"Error imprimiendo estadísticas: {e}")
    
    async def start(self):
        """Inicia el bridge"""
        self.logger.info("Iniciando Bridge MQTT-OPCUA con buffer persistente...")
        self.running = True
        
        # Reiniciar mensajes en procesamiento (por si el sistema se reinició)
        self.buffer.reset_processing_messages()
        
        # Iniciar cliente MQTT
        self.mqtt_client = MQTTClient(self.config, self.buffer)
        if not self.mqtt_client.connect():
            self.logger.error("No se pudo conectar al broker MQTT")
            return False
        
        # Iniciar servidor OPC-UA
        self.opcua_server = OPCUAServer(self.config, self.buffer)
        await self.opcua_server.init()
        await self.opcua_server.start()
        
        # Iniciar procesamiento de mensajes
        asyncio.create_task(self._process_messages())
        
        # Iniciar thread de estadísticas
        stats_thread = threading.Thread(target=self._print_statistics, daemon=True)
        stats_thread.start()
        
        self.logger.info("Bridge MQTT-OPCUA iniciado correctamente con buffer persistente SQLite")
        self.logger.info(f"Buffer: {self.buffer.get_pending_count()} mensajes pendientes en el arranque")
        return True
    
    async def stop(self):
        """Detiene el bridge"""
        self.logger.info("Deteniendo Bridge MQTT-OPCUA...")
        self.running = False
        
        # Esperar a que se procesen mensajes pendientes críticos
        pending = self.buffer.get_pending_count()
        if pending > 0:
            self.logger.info(f"Esperando procesamiento de {pending} mensajes pendientes...")
            await asyncio.sleep(2)
        
        # Detener cliente MQTT
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        
        # Detener servidor OPC-UA
        if self.opcua_server:
            await self.opcua_server.stop()
        
        # Cerrar buffer persistente
        self.buffer.close()
        
        # Exportar mensajes fallidos si hay
        stats = self.buffer.get_statistics()
        if stats.get('status_counts', {}).get('failed', 0) > 0:
            self.buffer.export_failed_messages()
        
        self.logger.info("Bridge MQTT-OPCUA detenido")
    
    async def run(self):
        """Ejecuta el bridge"""
        await self.start()
        
        # Mantener el bridge ejecutándose
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Interrupción recibida")
        finally:
            await self.stop()

async def main():
    """Función principal"""
    bridge = MQTTOPCUABridge("bridge_config.yaml")
    
    # Manejar señales de sistema
    def signal_handler(sig, frame):
        asyncio.create_task(bridge.stop())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Ejecutar el bridge
    await bridge.run()

if __name__ == "__main__":
    asyncio.run(main())