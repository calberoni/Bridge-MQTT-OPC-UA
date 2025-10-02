# persistent_buffer.py
"""
Buffer persistente usando SQLite para el Bridge MQTT-OPCUA
Garantiza que no se pierdan mensajes durante desconexiones o reinicios
"""

import sqlite3
import json
import threading
import queue
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from contextlib import contextmanager

class MessageStatus(Enum):
    """Estado del mensaje en el buffer"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"

class MessagePriority(Enum):
    """Prioridad del mensaje"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

@dataclass
class BufferedMessage:
    """Mensaje en el buffer persistente"""
    id: Optional[int] = None
    source: str = None  # 'mqtt' o 'opcua'
    destination: str = None  # 'mqtt', 'opcua' o 'sap'
    topic_or_node: str = None  # MQTT topic o OPC-UA node ID
    value: Any = None
    data_type: str = None
    mapping_id: str = None  # Identificador del mapeo
    status: str = MessageStatus.PENDING.value
    priority: int = MessagePriority.NORMAL.value
    retry_count: int = 0
    max_retries: int = 3
    created_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    expire_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict] = None

class PersistentBuffer:
    """
    Buffer persistente usando SQLite para almacenar mensajes
    entre reinicios y durante desconexiones
    """
    
    def __init__(self, db_path: str = "buffer.db", 
                 max_size: int = 10000,
                 ttl_minutes: int = 60,
                 cleanup_interval: int = 300,
                 logger: Optional[logging.Logger] = None):
        """
        Inicializa el buffer persistente
        
        Args:
            db_path: Ruta al archivo SQLite
            max_size: Tamaño máximo del buffer
            ttl_minutes: Tiempo de vida de los mensajes en minutos
            cleanup_interval: Intervalo de limpieza en segundos
            logger: Logger opcional
        """
        self.db_path = db_path
        self.max_size = max_size
        self.ttl_minutes = ttl_minutes
        self.cleanup_interval = cleanup_interval
        self.logger = logger or logging.getLogger(__name__)
        
        # Thread safety
        self.lock = threading.RLock()
        self.connection_pool = {}
        
        # Inicializar base de datos
        self._init_database()
        
        # Iniciar thread de limpieza
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        # Estadísticas
        self.stats = {
            'messages_added': 0,
            'messages_processed': 0,
            'messages_failed': 0,
            'messages_expired': 0
        }
    
    @contextmanager
    def _get_connection(self):
        """Context manager para obtener conexión thread-safe"""
        thread_id = threading.get_ident()
        
        if thread_id not in self.connection_pool:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
            conn.execute("PRAGMA synchronous=NORMAL")
            self.connection_pool[thread_id] = conn
        
        yield self.connection_pool[thread_id]
    
    def _init_database(self):
        """Inicializa la estructura de la base de datos"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabla principal de mensajes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    topic_or_node TEXT NOT NULL,
                    value TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    mapping_id TEXT,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 1,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    expire_at TIMESTAMP,
                    error_message TEXT,
                    metadata TEXT
                )
            """)
            
            # Índices para mejorar rendimiento
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_status 
                ON messages(status)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_priority_created 
                ON messages(priority DESC, created_at ASC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_source_dest 
                ON messages(source, destination)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_expire 
                ON messages(expire_at)
            """)
            
            # Tabla de estadísticas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    metadata TEXT
                )
            """)
            
            # Tabla de mensajes fallidos (para análisis)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS failed_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_id INTEGER,
                    source TEXT,
                    destination TEXT,
                    topic_or_node TEXT,
                    value TEXT,
                    error_message TEXT,
                    failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    retry_count INTEGER,
                    metadata TEXT
                )
            """)
            
            conn.commit()
            self.logger.info(f"Base de datos inicializada: {self.db_path}")
    
    def add_message(self, message: BufferedMessage) -> Optional[int]:
        """
        Añade un mensaje al buffer persistente
        
        Args:
            message: Mensaje a añadir
            
        Returns:
            ID del mensaje insertado o None si falla
        """
        with self.lock:
            try:
                # Verificar límite de tamaño
                if self.get_pending_count() >= self.max_size:
                    self._handle_buffer_overflow()
                
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Preparar datos
                    if message.created_at is None:
                        message.created_at = datetime.now()
                    
                    if message.expire_at is None:
                        message.expire_at = datetime.now() + timedelta(minutes=self.ttl_minutes)
                    
                    value_json = json.dumps(message.value) if not isinstance(message.value, str) else message.value
                    metadata_json = json.dumps(message.metadata) if message.metadata else None
                    
                    # Insertar mensaje
                    cursor.execute("""
                        INSERT INTO messages (
                            source, destination, topic_or_node, value, data_type,
                            mapping_id, status, priority, retry_count, max_retries,
                            created_at, expire_at, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        message.source,
                        message.destination,
                        message.topic_or_node,
                        value_json,
                        message.data_type,
                        message.mapping_id,
                        message.status,
                        message.priority,
                        message.retry_count,
                        message.max_retries,
                        message.created_at,
                        message.expire_at,
                        metadata_json
                    ))
                    
                    conn.commit()
                    message_id = cursor.lastrowid
                    
                    self.stats['messages_added'] += 1
                    self.logger.debug(f"Mensaje añadido al buffer: ID={message_id}, {message.source}->{message.destination}")
                    
                    return message_id
                    
            except Exception as e:
                self.logger.error(f"Error añadiendo mensaje al buffer: {e}")
                return None
    
    def get_next_message(self, source: Optional[str] = None, 
                        destination: Optional[str] = None) -> Optional[BufferedMessage]:
        """
        Obtiene el siguiente mensaje pendiente del buffer
        
        Args:
            source: Filtrar por fuente (opcional)
            destination: Filtrar por destino (opcional)
            
        Returns:
            Siguiente mensaje o None si no hay mensajes
        """
        with self.lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Construir query con filtros opcionales
                    query = """
                        SELECT * FROM messages 
                        WHERE status = ? 
                        AND expire_at > CURRENT_TIMESTAMP
                        AND retry_count < max_retries
                    """
                    params = [MessageStatus.PENDING.value]
                    
                    if source:
                        query += " AND source = ?"
                        params.append(source)
                    
                    if destination:
                        query += " AND destination = ?"
                        params.append(destination)
                    
                    query += " ORDER BY priority DESC, created_at ASC LIMIT 1"
                    
                    cursor.execute(query, params)
                    row = cursor.fetchone()
                    
                    if row:
                        # Marcar como procesando
                        cursor.execute("""
                            UPDATE messages 
                            SET status = ? 
                            WHERE id = ?
                        """, (MessageStatus.PROCESSING.value, row['id']))
                        conn.commit()
                        
                        # Convertir a BufferedMessage
                        return self._row_to_message(row)
                    
                    return None
                    
            except Exception as e:
                self.logger.error(f"Error obteniendo mensaje del buffer: {e}")
                return None
    
    def get_pending_messages(self, limit: int = 100, 
                            source: Optional[str] = None,
                            destination: Optional[str] = None) -> List[BufferedMessage]:
        """
        Obtiene múltiples mensajes pendientes
        
        Args:
            limit: Número máximo de mensajes
            source: Filtrar por fuente
            destination: Filtrar por destino
            
        Returns:
            Lista de mensajes pendientes
        """
        with self.lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    query = """
                        SELECT * FROM messages 
                        WHERE status = ? 
                        AND expire_at > CURRENT_TIMESTAMP
                        AND retry_count < max_retries
                    """
                    params = [MessageStatus.PENDING.value]
                    
                    if source:
                        query += " AND source = ?"
                        params.append(source)
                    
                    if destination:
                        query += " AND destination = ?"
                        params.append(destination)
                    
                    query += " ORDER BY priority DESC, created_at ASC LIMIT ?"
                    params.append(limit)
                    
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    
                    # Marcar todos como procesando
                    if rows:
                        ids = [row['id'] for row in rows]
                        placeholders = ','.join('?' * len(ids))
                        cursor.execute(f"""
                            UPDATE messages 
                            SET status = ? 
                            WHERE id IN ({placeholders})
                        """, [MessageStatus.PROCESSING.value] + ids)
                        conn.commit()
                    
                    return [self._row_to_message(row) for row in rows]
                    
            except Exception as e:
                self.logger.error(f"Error obteniendo mensajes pendientes: {e}")
                return []
    
    def mark_completed(self, message_id: int) -> bool:
        """
        Marca un mensaje como completado
        
        Args:
            message_id: ID del mensaje
            
        Returns:
            True si se actualizó correctamente
        """
        with self.lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        UPDATE messages 
                        SET status = ?, processed_at = CURRENT_TIMESTAMP 
                        WHERE id = ?
                    """, (MessageStatus.COMPLETED.value, message_id))
                    
                    conn.commit()
                    
                    if cursor.rowcount > 0:
                        self.stats['messages_processed'] += 1
                        self.logger.debug(f"Mensaje marcado como completado: ID={message_id}")
                        return True
                    
                    return False
                    
            except Exception as e:
                self.logger.error(f"Error marcando mensaje como completado: {e}")
                return False
    
    def mark_failed(self, message_id: int, error_message: str = None) -> bool:
        """
        Marca un mensaje como fallido y incrementa el contador de reintentos
        
        Args:
            message_id: ID del mensaje
            error_message: Mensaje de error opcional
            
        Returns:
            True si se actualizó correctamente
        """
        with self.lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Obtener información actual del mensaje
                    cursor.execute("""
                        SELECT retry_count, max_retries, source, destination, 
                               topic_or_node, value, metadata
                        FROM messages 
                        WHERE id = ?
                    """, (message_id,))
                    
                    row = cursor.fetchone()
                    if not row:
                        return False
                    
                    retry_count = row['retry_count'] + 1
                    
                    if retry_count >= row['max_retries']:
                        # Mover a tabla de mensajes fallidos
                        cursor.execute("""
                            INSERT INTO failed_messages (
                                original_id, source, destination, topic_or_node, 
                                value, error_message, retry_count, metadata
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            message_id, row['source'], row['destination'],
                            row['topic_or_node'], row['value'], error_message,
                            retry_count, row['metadata']
                        ))
                        
                        # Marcar como fallido definitivamente
                        status = MessageStatus.FAILED.value
                        self.stats['messages_failed'] += 1
                    else:
                        # Volver a estado pendiente para reintentar
                        status = MessageStatus.PENDING.value
                    
                    # Actualizar mensaje
                    cursor.execute("""
                        UPDATE messages 
                        SET status = ?, retry_count = ?, error_message = ?
                        WHERE id = ?
                    """, (status, retry_count, error_message, message_id))
                    
                    conn.commit()
                    
                    self.logger.debug(f"Mensaje marcado como fallido: ID={message_id}, reintentos={retry_count}")
                    return True
                    
            except Exception as e:
                self.logger.error(f"Error marcando mensaje como fallido: {e}")
                return False
    
    def get_pending_count(self) -> int:
        """Obtiene el número de mensajes pendientes"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM messages 
                    WHERE status IN (?, ?)
                """, (MessageStatus.PENDING.value, MessageStatus.PROCESSING.value))
                
                row = cursor.fetchone()
                return row['count'] if row else 0
                
        except Exception as e:
            self.logger.error(f"Error obteniendo conteo de pendientes: {e}")
            return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas del buffer"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Conteos por estado
                cursor.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM messages 
                    GROUP BY status
                """)
                status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
                
                # Conteos por origen/destino
                cursor.execute("""
                    SELECT source, destination, COUNT(*) as count 
                    FROM messages 
                    WHERE status IN (?, ?)
                    GROUP BY source, destination
                """, (MessageStatus.PENDING.value, MessageStatus.PROCESSING.value))
                
                route_counts = [
                    {'source': row['source'], 'destination': row['destination'], 'count': row['count']}
                    for row in cursor.fetchall()
                ]
                
                # Mensajes más antiguos pendientes
                cursor.execute("""
                    SELECT MIN(created_at) as oldest 
                    FROM messages 
                    WHERE status = ?
                """, (MessageStatus.PENDING.value,))
                
                row = cursor.fetchone()
                oldest_pending = row['oldest'] if row and row['oldest'] else None
                
                return {
                    'buffer_size': self.get_pending_count(),
                    'max_size': self.max_size,
                    'status_counts': status_counts,
                    'route_counts': route_counts,
                    'oldest_pending': oldest_pending,
                    'runtime_stats': self.stats,
                    'utilization_percent': (self.get_pending_count() / self.max_size) * 100
                }
                
        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas: {e}")
            return {}
    
    def _row_to_message(self, row: sqlite3.Row) -> BufferedMessage:
        """Convierte una fila de la base de datos a BufferedMessage"""
        try:
            value = json.loads(row['value']) if row['value'] else None
        except json.JSONDecodeError:
            value = row['value']
        
        try:
            metadata = json.loads(row['metadata']) if row['metadata'] else None
        except (json.JSONDecodeError, TypeError):
            metadata = None
        
        return BufferedMessage(
            id=row['id'],
            source=row['source'],
            destination=row['destination'],
            topic_or_node=row['topic_or_node'],
            value=value,
            data_type=row['data_type'],
            mapping_id=row['mapping_id'],
            status=row['status'],
            priority=row['priority'],
            retry_count=row['retry_count'],
            max_retries=row['max_retries'],
            created_at=row['created_at'],
            processed_at=row['processed_at'],
            expire_at=row['expire_at'],
            error_message=row['error_message'],
            metadata=metadata
        )
    
    def _handle_buffer_overflow(self):
        """Maneja el desbordamiento del buffer"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Eliminar mensajes completados más antiguos
                cursor.execute("""
                    DELETE FROM messages 
                    WHERE id IN (
                        SELECT id FROM messages 
                        WHERE status = ? 
                        ORDER BY processed_at ASC 
                        LIMIT 100
                    )
                """, (MessageStatus.COMPLETED.value,))
                
                if cursor.rowcount < 50:
                    # Si no hay suficientes completados, eliminar expirados
                    cursor.execute("""
                        DELETE FROM messages 
                        WHERE expire_at < CURRENT_TIMESTAMP 
                        LIMIT 100
                    """)
                
                conn.commit()
                self.logger.warning(f"Buffer overflow manejado, eliminados {cursor.rowcount} mensajes")
                
        except Exception as e:
            self.logger.error(f"Error manejando overflow del buffer: {e}")
    
    def _cleanup_loop(self):
        """Thread de limpieza periódica"""
        import time
        
        while True:
            try:
                time.sleep(self.cleanup_interval)
                self._cleanup()
            except Exception as e:
                self.logger.error(f"Error en limpieza periódica: {e}")
    
    def _cleanup(self):
        """Limpia mensajes antiguos y expirados"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Marcar mensajes expirados
                cursor.execute("""
                    UPDATE messages 
                    SET status = ? 
                    WHERE expire_at < CURRENT_TIMESTAMP 
                    AND status IN (?, ?)
                """, (
                    MessageStatus.EXPIRED.value,
                    MessageStatus.PENDING.value,
                    MessageStatus.PROCESSING.value
                ))
                
                expired_count = cursor.rowcount
                if expired_count > 0:
                    self.stats['messages_expired'] += expired_count
                
                # Eliminar mensajes completados antiguos (más de 24 horas)
                cursor.execute("""
                    DELETE FROM messages 
                    WHERE status = ? 
                    AND processed_at < datetime('now', '-1 day')
                """, (MessageStatus.COMPLETED.value,))
                
                # Eliminar mensajes expirados antiguos (más de 7 días)
                cursor.execute("""
                    DELETE FROM messages 
                    WHERE status = ? 
                    AND expire_at < datetime('now', '-7 days')
                """, (MessageStatus.EXPIRED.value,))
                
                # Limpiar estadísticas antiguas (más de 30 días)
                cursor.execute("""
                    DELETE FROM statistics 
                    WHERE timestamp < datetime('now', '-30 days')
                """)
                
                conn.commit()
                
                if expired_count > 0 or cursor.rowcount > 0:
                    self.logger.info(f"Limpieza: {expired_count} expirados, {cursor.rowcount} eliminados")
                    
        except Exception as e:
            self.logger.error(f"Error en limpieza: {e}")
    
    def reset_processing_messages(self):
        """
        Reinicia mensajes en estado 'processing' a 'pending'
        Útil al reiniciar el sistema
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE messages 
                    SET status = ? 
                    WHERE status = ?
                """, (MessageStatus.PENDING.value, MessageStatus.PROCESSING.value))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    self.logger.info(f"Reiniciados {cursor.rowcount} mensajes en procesamiento")
                    
        except Exception as e:
            self.logger.error(f"Error reiniciando mensajes: {e}")
    
    def export_failed_messages(self, output_file: str = "failed_messages.json"):
        """Exporta mensajes fallidos para análisis"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM failed_messages 
                    ORDER BY failed_at DESC
                """)
                
                failed_messages = []
                for row in cursor.fetchall():
                    failed_messages.append({
                        'id': row['id'],
                        'original_id': row['original_id'],
                        'source': row['source'],
                        'destination': row['destination'],
                        'topic_or_node': row['topic_or_node'],
                        'value': row['value'],
                        'error_message': row['error_message'],
                        'failed_at': row['failed_at'],
                        'retry_count': row['retry_count'],
                        'metadata': row['metadata']
                    })
                
                with open(output_file, 'w') as f:
                    json.dump(failed_messages, f, indent=2, default=str)
                
                self.logger.info(f"Exportados {len(failed_messages)} mensajes fallidos a {output_file}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error exportando mensajes fallidos: {e}")
            return False
    
    def close(self):
        """Cierra las conexiones y limpia recursos"""
        try:
            for conn in self.connection_pool.values():
                conn.close()
            self.connection_pool.clear()
            self.logger.info("Buffer persistente cerrado")
        except Exception as e:
            self.logger.error(f"Error cerrando buffer: {e}")
