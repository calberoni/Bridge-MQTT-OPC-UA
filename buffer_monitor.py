#!/usr/bin/env python3
"""
Monitor del Buffer Persistente SQLite
Herramienta para monitorear y gestionar el buffer del bridge
"""

import sqlite3
import json
import argparse
import time
from datetime import datetime, timedelta
from typing import Dict, Any
import os
import sys

class BufferMonitor:
    """Monitor para el buffer persistente SQLite"""
    
    def __init__(self, db_path: str = "buffer.db"):
        self.db_path = db_path
        if not os.path.exists(db_path):
            print(f"Error: No se encuentra la base de datos {db_path}")
            sys.exit(1)
    
    def get_connection(self):
        """Obtiene conexión a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def show_statistics(self):
        """Muestra estadísticas generales del buffer"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            print("\n" + "="*60)
            print("ESTADÍSTICAS DEL BUFFER PERSISTENTE")
            print("="*60)
            
            # Total de mensajes
            cursor.execute("SELECT COUNT(*) as total FROM messages")
            total = cursor.fetchone()['total']
            print(f"\nTotal de mensajes: {total}")
            
            # Mensajes por estado
            print("\nMensajes por estado:")
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM messages 
                GROUP BY status 
                ORDER BY count DESC
            """)
            for row in cursor.fetchall():
                print(f"  {row['status']:15s}: {row['count']:6d}")
            
            # Mensajes por ruta
            print("\nMensajes por ruta:")
            cursor.execute("""
                SELECT source, destination, COUNT(*) as count 
                FROM messages 
                GROUP BY source, destination
                ORDER BY count DESC
            """)
            for row in cursor.fetchall():
                print(f"  {row['source']:6s} -> {row['destination']:6s}: {row['count']:6d}")
            
            # Mensajes por prioridad
            print("\nMensajes por prioridad:")
            cursor.execute("""
                SELECT priority, COUNT(*) as count 
                FROM messages 
                WHERE status IN ('pending', 'processing')
                GROUP BY priority 
                ORDER BY priority DESC
            """)
            priorities = {0: "LOW", 1: "NORMAL", 2: "HIGH", 3: "CRITICAL"}
            for row in cursor.fetchall():
                priority_name = priorities.get(row['priority'], str(row['priority']))
                print(f"  {priority_name:8s}: {row['count']:6d}")
            
            # Mensaje más antiguo pendiente
            cursor.execute("""
                SELECT MIN(created_at) as oldest, MAX(created_at) as newest
                FROM messages 
                WHERE status = 'pending'
            """)
            row = cursor.fetchone()
            if row['oldest']:
                print(f"\nMensaje pendiente más antiguo: {row['oldest']}")
                print(f"Mensaje pendiente más reciente: {row['newest']}")
            
            # Mensajes expirados
            cursor.execute("""
                SELECT COUNT(*) as expired 
                FROM messages 
                WHERE expire_at < CURRENT_TIMESTAMP
            """)
            expired = cursor.fetchone()['expired']
            if expired > 0:
                print(f"\n⚠️  Mensajes expirados: {expired}")
            
            # Mensajes fallidos
            cursor.execute("SELECT COUNT(*) as failed FROM failed_messages")
            failed = cursor.fetchone()['failed']
            if failed > 0:
                print(f"\n❌ Mensajes fallidos totales: {failed}")
            
            print("="*60)
    
    def show_pending_messages(self, limit: int = 20):
        """Muestra los mensajes pendientes"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, source, destination, topic_or_node, 
                       created_at, retry_count, priority
                FROM messages 
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            
            print(f"\nMENSAJES PENDIENTES (mostrando {len(rows)} de máximo {limit})")
            print("-"*80)
            
            if not rows:
                print("No hay mensajes pendientes")
            else:
                print(f"{'ID':6s} {'Origen':6s} {'Destino':7s} {'Topic/Nodo':30s} {'Creado':20s} {'Reintentos':10s} {'Prior':5s}")
                print("-"*80)
                
                for row in rows:
                    topic_node = row['topic_or_node'][:28] + ".." if len(row['topic_or_node']) > 30 else row['topic_or_node']
                    created = datetime.fromisoformat(row['created_at']).strftime("%Y-%m-%d %H:%M:%S")
                    
                    print(f"{row['id']:6d} {row['source']:6s} {row['destination']:7s} "
                          f"{topic_node:30s} {created:20s} {row['retry_count']:10d} {row['priority']:5d}")
    
    def show_failed_messages(self, limit: int = 20):
        """Muestra los mensajes fallidos"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, source, destination, topic_or_node, 
                       error_message, failed_at, retry_count
                FROM failed_messages 
                ORDER BY failed_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            
            print(f"\nMENSAJES FALLIDOS (mostrando {len(rows)} de máximo {limit})")
            print("-"*100)
            
            if not rows:
                print("No hay mensajes fallidos")
            else:
                for row in rows:
                    print(f"\nID: {row['id']}")
                    print(f"  Ruta: {row['source']} -> {row['destination']}")
                    print(f"  Topic/Nodo: {row['topic_or_node']}")
                    print(f"  Error: {row['error_message']}")
                    print(f"  Fallado: {row['failed_at']}")
                    print(f"  Reintentos: {row['retry_count']}")
    
    def monitor_realtime(self, interval: int = 5):
        """Monitoreo en tiempo real"""
        try:
            print("\nMONITOREO EN TIEMPO REAL")
            print("Presiona Ctrl+C para detener\n")
            
            prev_stats = {}
            
            while True:
                os.system('clear' if os.name == 'posix' else 'cls')
                
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Header
                    print(f"📊 MONITOR DE BUFFER - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    print("="*70)
                    
                    # Estadísticas actuales
                    cursor.execute("""
                        SELECT status, COUNT(*) as count 
                        FROM messages 
                        GROUP BY status
                    """)
                    
                    status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
                    
                    # Calcular tasas de cambio
                    pending_current = status_counts.get('pending', 0)
                    completed_current = status_counts.get('completed', 0)
                    failed_current = status_counts.get('failed', 0)
                    
                    pending_prev = prev_stats.get('pending', pending_current)
                    completed_prev = prev_stats.get('completed', completed_current)
                    failed_prev = prev_stats.get('failed', failed_current)
                    
                    pending_rate = (pending_current - pending_prev) / interval
                    completed_rate = (completed_current - completed_prev) / interval
                    failed_rate = (failed_current - failed_prev) / interval
                    
                    # Mostrar estadísticas
                    print(f"\n📨 MENSAJES:")
                    print(f"  Pendientes:  {pending_current:6d} ({pending_rate:+.1f}/s)")
                    print(f"  Procesando:  {status_counts.get('processing', 0):6d}")
                    print(f"  Completados: {completed_current:6d} ({completed_rate:+.1f}/s)")
                    print(f"  Fallidos:    {failed_current:6d} ({failed_rate:+.1f}/s)")
                    print(f"  Expirados:   {status_counts.get('expired', 0):6d}")
                    
                    # Throughput
                    if completed_rate > 0:
                        print(f"\n⚡ THROUGHPUT: {completed_rate:.2f} msg/s")
                    
                    # Rutas activas
                    cursor.execute("""
                        SELECT source, destination, COUNT(*) as count 
                        FROM messages 
                        WHERE status IN ('pending', 'processing')
                        GROUP BY source, destination
                    """)
                    
                    routes = cursor.fetchall()
                    if routes:
                        print("\n🔄 RUTAS ACTIVAS:")
                        for row in routes:
                            print(f"  {row['source']:6s} -> {row['destination']:6s}: {row['count']:4d} mensajes")
                    
                    # Mensajes recientes
                    cursor.execute("""
                        SELECT topic_or_node, source, destination, created_at
                        FROM messages 
                        WHERE status = 'completed'
                        ORDER BY processed_at DESC
                        LIMIT 5
                    """)
                    
                    recent = cursor.fetchall()
                    if recent:
                        print("\n📝 ÚLTIMOS PROCESADOS:")
                        for row in recent:
                            topic = row['topic_or_node'][:40] + ".." if len(row['topic_or_node']) > 42 else row['topic_or_node']
                            print(f"  [{row['source']}->{row['destination']}] {topic}")
                    
                    # Alertas
                    if pending_current > 1000:
                        print(f"\n⚠️  ALERTA: Alto número de mensajes pendientes ({pending_current})")
                    
                    if failed_rate > 1:
                        print(f"\n⚠️  ALERTA: Alta tasa de fallos ({failed_rate:.1f}/s)")
                    
                    cursor.execute("""
                        SELECT COUNT(*) as stuck 
                        FROM messages 
                        WHERE status = 'processing' 
                        AND datetime(created_at, '+5 minutes') < datetime('now')
                    """)
                    
                    stuck = cursor.fetchone()['stuck']
                    if stuck > 0:
                        print(f"\n⚠️  ALERTA: {stuck} mensajes atascados en procesamiento")
                    
                    # Guardar estadísticas para siguiente iteración
                    prev_stats = {
                        'pending': pending_current,
                        'completed': completed_current,
                        'failed': failed_current
                    }
                    
                    print("\n" + "="*70)
                    print(f"Actualización cada {interval} segundos | Ctrl+C para salir")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\nMonitoreo detenido")
    
    def cleanup_old_messages(self, days: int = 7):
        """Limpia mensajes antiguos"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            print(f"\nLimpiando mensajes completados de más de {days} días...")
            
            cursor.execute("""
                DELETE FROM messages 
                WHERE status = 'completed' 
                AND processed_at < datetime('now', ? || ' days')
            """, (-days,))
            
            completed_deleted = cursor.rowcount
            
            cursor.execute("""
                DELETE FROM messages 
                WHERE status = 'expired' 
                AND expire_at < datetime('now', ? || ' days')
            """, (-days,))
            
            expired_deleted = cursor.rowcount
            
            cursor.execute("""
                DELETE FROM failed_messages 
                WHERE failed_at < datetime('now', ? || ' days')
            """, (-days,))
            
            failed_deleted = cursor.rowcount
            
            conn.commit()
            
            print(f"Eliminados:")
            print(f"  - {completed_deleted} mensajes completados")
            print(f"  - {expired_deleted} mensajes expirados")
            print(f"  - {failed_deleted} mensajes fallidos")
            print(f"Total: {completed_deleted + expired_deleted + failed_deleted} mensajes")
    
    def reset_stuck_messages(self):
        """Reinicia mensajes atascados en procesamiento"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Buscar mensajes atascados (más de 5 minutos en procesamiento)
            cursor.execute("""
                UPDATE messages 
                SET status = 'pending'
                WHERE status = 'processing' 
                AND datetime(created_at, '+5 minutes') < datetime('now')
            """)
            
            conn.commit()
            
            if cursor.rowcount > 0:
                print(f"✓ {cursor.rowcount} mensajes atascados reiniciados a 'pending'")
            else:
                print("No hay mensajes atascados")
    
    def export_statistics(self, output_file: str = "buffer_stats.json"):
        """Exporta estadísticas detalladas"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Conteos generales
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM messages 
                GROUP BY status
            """)
            stats['status_counts'] = {row['status']: row['count'] for row in cursor.fetchall()}
            
            # Estadísticas por hora (últimas 24 horas)
            cursor.execute("""
                SELECT 
                    strftime('%Y-%m-%d %H:00', created_at) as hour,
                    COUNT(*) as created,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM messages
                WHERE created_at > datetime('now', '-24 hours')
                GROUP BY hour
                ORDER BY hour
            """)
            
            stats['hourly_stats'] = []
            for row in cursor.fetchall():
                stats['hourly_stats'].append({
                    'hour': row['hour'],
                    'created': row['created'],
                    'completed': row['completed'],
                    'failed': row['failed']
                })
            
            # Top topics/nodes
            cursor.execute("""
                SELECT topic_or_node, COUNT(*) as count 
                FROM messages 
                GROUP BY topic_or_node 
                ORDER BY count DESC 
                LIMIT 20
            """)
            
            stats['top_topics'] = []
            for row in cursor.fetchall():
                stats['top_topics'].append({
                    'topic': row['topic_or_node'],
                    'count': row['count']
                })
            
            # Guardar a archivo
            with open(output_file, 'w') as f:
                json.dump(stats, f, indent=2, default=str)
            
            print(f"✓ Estadísticas exportadas a {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Monitor del Buffer Persistente SQLite")
    parser.add_argument('--db', default='buffer.db', help='Ruta a la base de datos SQLite')
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Comando stats
    subparsers.add_parser('stats', help='Mostrar estadísticas generales')
    
    # Comando pending
    pending_parser = subparsers.add_parser('pending', help='Mostrar mensajes pendientes')
    pending_parser.add_argument('--limit', type=int, default=20, help='Número máximo de mensajes a mostrar')
    
    # Comando failed
    failed_parser = subparsers.add_parser('failed', help='Mostrar mensajes fallidos')
    failed_parser.add_argument('--limit', type=int, default=20, help='Número máximo de mensajes a mostrar')
    
    # Comando monitor
    monitor_parser = subparsers.add_parser('monitor', help='Monitoreo en tiempo real')
    monitor_parser.add_argument('--interval', type=int, default=5, help='Intervalo de actualización en segundos')
    
    # Comando cleanup
    cleanup_parser = subparsers.add_parser('cleanup', help='Limpiar mensajes antiguos')
    cleanup_parser.add_argument('--days', type=int, default=7, help='Días de antigüedad')
    
    # Comando reset
    subparsers.add_parser('reset', help='Reiniciar mensajes atascados')
    
    # Comando export
    export_parser = subparsers.add_parser('export', help='Exportar estadísticas')
    export_parser.add_argument('--output', default='buffer_stats.json', help='Archivo de salida')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    monitor = BufferMonitor(args.db)
    
    if args.command == 'stats':
        monitor.show_statistics()
    elif args.command == 'pending':
        monitor.show_pending_messages(args.limit)
    elif args.command == 'failed':
        monitor.show_failed_messages(args.limit)
    elif args.command == 'monitor':
        monitor.monitor_realtime(args.interval)
    elif args.command == 'cleanup':
        monitor.cleanup_old_messages(args.days)
    elif args.command == 'reset':
        monitor.reset_stuck_messages()
    elif args.command == 'export':
        monitor.export_statistics(args.output)

if __name__ == "__main__":
    main()