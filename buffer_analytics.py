#!/usr/bin/env python3
"""
buffer_analytics.py
Sistema de análisis avanzado y métricas para el buffer persistente
Incluye predicción de carga, detección de anomalías y reportes HTML
"""

import sqlite3
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
import statistics
import math
from collections import defaultdict

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Matplotlib no instalado. Gráficos no disponibles.")
    print("Instalar con: pip install matplotlib")

class BufferAnalytics:
    """Sistema de análisis avanzado para el buffer persistente"""
    
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
    
    def analyze_performance(self, hours: int = 24) -> Dict[str, Any]:
        """
        Analiza el rendimiento del sistema en las últimas horas
        
        Returns:
            Diccionario con métricas de rendimiento
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Obtener métricas por hora
            cursor.execute("""
                SELECT 
                    strftime('%Y-%m-%d %H:00', created_at) as hour,
                    COUNT(*) as messages_created,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    AVG(CASE 
                        WHEN status = 'completed' AND processed_at IS NOT NULL 
                        THEN (julianday(processed_at) - julianday(created_at)) * 86400
                        ELSE NULL 
                    END) as avg_processing_time_seconds,
                    MAX(CASE 
                        WHEN status = 'completed' AND processed_at IS NOT NULL 
                        THEN (julianday(processed_at) - julianday(created_at)) * 86400
                        ELSE NULL 
                    END) as max_processing_time_seconds
                FROM messages
                WHERE created_at > datetime('now', ? || ' hours')
                GROUP BY hour
                ORDER BY hour
            """, (-hours,))
            
            hourly_data = []
            for row in cursor.fetchall():
                hourly_data.append({
                    'hour': row['hour'],
                    'created': row['messages_created'],
                    'completed': row['completed'] or 0,
                    'failed': row['failed'] or 0,
                    'avg_processing_time': row['avg_processing_time_seconds'] or 0,
                    'max_processing_time': row['max_processing_time_seconds'] or 0,
                    'success_rate': (row['completed'] / row['messages_created'] * 100) if row['messages_created'] > 0 else 0
                })
            
            # Calcular estadísticas generales
            if hourly_data:
                total_created = sum(h['created'] for h in hourly_data)
                total_completed = sum(h['completed'] for h in hourly_data)
                total_failed = sum(h['failed'] for h in hourly_data)
                avg_throughput = total_completed / len(hourly_data) if hourly_data else 0
                
                processing_times = [h['avg_processing_time'] for h in hourly_data if h['avg_processing_time'] > 0]
                avg_processing_time = statistics.mean(processing_times) if processing_times else 0
                
                # Detectar tendencias
                if len(hourly_data) > 1:
                    recent_throughput = statistics.mean([h['completed'] for h in hourly_data[-3:]])
                    older_throughput = statistics.mean([h['completed'] for h in hourly_data[:-3]]) if len(hourly_data) > 3 else recent_throughput
                    trend = "increasing" if recent_throughput > older_throughput * 1.1 else \
                           "decreasing" if recent_throughput < older_throughput * 0.9 else "stable"
                else:
                    trend = "insufficient_data"
                
                return {
                    'period_hours': hours,
                    'total_messages': total_created,
                    'completed_messages': total_completed,
                    'failed_messages': total_failed,
                    'success_rate': (total_completed / total_created * 100) if total_created > 0 else 0,
                    'avg_throughput_per_hour': avg_throughput,
                    'avg_processing_time_seconds': avg_processing_time,
                    'trend': trend,
                    'hourly_data': hourly_data
                }
            else:
                return {
                    'period_hours': hours,
                    'total_messages': 0,
                    'completed_messages': 0,
                    'failed_messages': 0,
                    'success_rate': 0,
                    'avg_throughput_per_hour': 0,
                    'avg_processing_time_seconds': 0,
                    'trend': 'no_data',
                    'hourly_data': []
                }
    
    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """
        Detecta anomalías en el sistema
        
        Returns:
            Lista de anomalías detectadas
        """
        anomalies = []
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Mensajes atascados en procesamiento
            cursor.execute("""
                SELECT COUNT(*) as stuck_count, MIN(created_at) as oldest
                FROM messages 
                WHERE status = 'processing' 
                AND datetime(created_at, '+5 minutes') < datetime('now')
            """)
            row = cursor.fetchone()
            if row['stuck_count'] > 0:
                anomalies.append({
                    'type': 'stuck_messages',
                    'severity': 'high',
                    'count': row['stuck_count'],
                    'oldest': row['oldest'],
                    'message': f"{row['stuck_count']} mensajes atascados en procesamiento"
                })
            
            # 2. Alta tasa de fallos
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM messages
                WHERE created_at > datetime('now', '-1 hour')
            """)
            row = cursor.fetchone()
            if row['total'] > 0:
                failure_rate = (row['failed'] / row['total']) * 100
                if failure_rate > 10:
                    anomalies.append({
                        'type': 'high_failure_rate',
                        'severity': 'high' if failure_rate > 25 else 'medium',
                        'rate': failure_rate,
                        'message': f"Alta tasa de fallos: {failure_rate:.1f}% en la última hora"
                    })
            
            # 3. Acumulación de mensajes pendientes
            cursor.execute("""
                SELECT 
                    COUNT(*) as pending_count,
                    MIN(created_at) as oldest_pending
                FROM messages 
                WHERE status = 'pending'
            """)
            row = cursor.fetchone()
            if row['pending_count'] > 1000:
                anomalies.append({
                    'type': 'queue_buildup',
                    'severity': 'high' if row['pending_count'] > 5000 else 'medium',
                    'count': row['pending_count'],
                    'oldest': row['oldest_pending'],
                    'message': f"Acumulación de {row['pending_count']} mensajes pendientes"
                })
            
            # 4. Mensajes con muchos reintentos
            cursor.execute("""
                SELECT COUNT(*) as high_retry_count
                FROM messages 
                WHERE retry_count >= max_retries - 1
                AND status NOT IN ('completed', 'failed')
            """)
            row = cursor.fetchone()
            if row['high_retry_count'] > 0:
                anomalies.append({
                    'type': 'high_retry_messages',
                    'severity': 'medium',
                    'count': row['high_retry_count'],
                    'message': f"{row['high_retry_count']} mensajes cerca del límite de reintentos"
                })
            
            # 5. Desbalance en rutas
            cursor.execute("""
                SELECT 
                    source, 
                    destination,
                    COUNT(*) as count
                FROM messages
                WHERE status IN ('pending', 'processing')
                GROUP BY source, destination
                HAVING count > 100
                ORDER BY count DESC
            """)
            
            routes = cursor.fetchall()
            for route in routes:
                if route['count'] > 500:
                    anomalies.append({
                        'type': 'route_congestion',
                        'severity': 'medium',
                        'route': f"{route['source']}->{route['destination']}",
                        'count': route['count'],
                        'message': f"Congestión en ruta {route['source']}->{route['destination']}: {route['count']} mensajes"
                    })
            
            # 6. Tiempo de procesamiento anormal
            cursor.execute("""
                SELECT 
                    AVG(julianday(processed_at) - julianday(created_at)) * 86400 as avg_time,
                    MAX(julianday(processed_at) - julianday(created_at)) * 86400 as max_time
                FROM messages
                WHERE status = 'completed'
                AND processed_at > datetime('now', '-1 hour')
            """)
            row = cursor.fetchone()
            if row['avg_time'] and row['avg_time'] > 10:  # Más de 10 segundos promedio
                anomalies.append({
                    'type': 'slow_processing',
                    'severity': 'medium',
                    'avg_time': row['avg_time'],
                    'max_time': row['max_time'],
                    'message': f"Procesamiento lento: promedio {row['avg_time']:.1f}s, máximo {row['max_time']:.1f}s"
                })
            
        return anomalies
    
    def predict_load(self, next_hours: int = 6) -> Dict[str, Any]:
        """
        Predice la carga futura basándose en patrones históricos
        
        Args:
            next_hours: Horas a predecir
            
        Returns:
            Predicción de carga
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Obtener datos históricos por hora del día y día de la semana
            cursor.execute("""
                SELECT 
                    CAST(strftime('%w', created_at) AS INTEGER) as day_of_week,
                    CAST(strftime('%H', created_at) AS INTEGER) as hour_of_day,
                    COUNT(*) as message_count
                FROM messages
                WHERE created_at > datetime('now', '-30 days')
                GROUP BY day_of_week, hour_of_day
            """)
            
            # Crear matriz de patrones
            patterns = defaultdict(list)
            for row in cursor.fetchall():
                key = (row['day_of_week'], row['hour_of_day'])
                patterns[key].append(row['message_count'])
            
            # Calcular promedios y desviación estándar
            pattern_stats = {}
            for key, values in patterns.items():
                if values:
                    pattern_stats[key] = {
                        'mean': statistics.mean(values),
                        'stdev': statistics.stdev(values) if len(values) > 1 else 0,
                        'samples': len(values)
                    }
            
            # Generar predicción
            predictions = []
            current_time = datetime.now()
            
            for hour_offset in range(next_hours):
                future_time = current_time + timedelta(hours=hour_offset)
                dow = future_time.weekday()
                hod = future_time.hour
                
                key = (dow, hod)
                if key in pattern_stats:
                    stats = pattern_stats[key]
                    predicted_load = stats['mean']
                    confidence = min(90, 50 + (stats['samples'] * 2))  # Más muestras = mayor confianza
                    
                    predictions.append({
                        'time': future_time.strftime('%Y-%m-%d %H:00'),
                        'predicted_messages': int(predicted_load),
                        'confidence': confidence,
                        'range_min': max(0, int(predicted_load - stats['stdev'])),
                        'range_max': int(predicted_load + stats['stdev'])
                    })
                else:
                    # Sin datos históricos, usar promedio general
                    cursor.execute("""
                        SELECT AVG(message_count) as avg_load
                        FROM (
                            SELECT COUNT(*) as message_count
                            FROM messages
                            WHERE created_at > datetime('now', '-7 days')
                            GROUP BY strftime('%Y-%m-%d %H', created_at)
                        )
                    """)
                    avg_load = cursor.fetchone()['avg_load'] or 50
                    
                    predictions.append({
                        'time': future_time.strftime('%Y-%m-%d %H:00'),
                        'predicted_messages': int(avg_load),
                        'confidence': 30,  # Baja confianza sin datos históricos
                        'range_min': int(avg_load * 0.5),
                        'range_max': int(avg_load * 1.5)
                    })
            
            # Calcular carga total esperada
            total_predicted = sum(p['predicted_messages'] for p in predictions)
            
            # Obtener capacidad actual
            cursor.execute("SELECT COUNT(*) as current_pending FROM messages WHERE status = 'pending'")
            current_pending = cursor.fetchone()['current_pending']
            
            return {
                'next_hours': next_hours,
                'predictions': predictions,
                'total_predicted_messages': total_predicted,
                'current_pending': current_pending,
                'estimated_total_load': current_pending + total_predicted,
                'recommendation': self._get_load_recommendation(current_pending + total_predicted)
            }
    
    def _get_load_recommendation(self, estimated_load: int) -> str:
        """Genera recomendación basada en la carga estimada"""
        if estimated_load < 1000:
            return "Carga normal. Sistema operando dentro de parámetros."
        elif estimated_load < 5000:
            return "Carga moderada. Monitorear el sistema."
        elif estimated_load < 10000:
            return "Carga alta. Considerar escalar recursos o revisar cuellos de botella."
        else:
            return "Carga crítica. Acción inmediata requerida. Escalar recursos o reducir carga."
    
    def generate_html_report(self, output_file: str = "buffer_report.html"):
        """
        Genera un reporte HTML completo del estado del sistema
        """
        performance = self.analyze_performance(24)
        anomalies = self.detect_anomalies()
        prediction = self.predict_load(6)
        
        # Obtener estadísticas actuales
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM messages
            """)
            current_stats = cursor.fetchone()
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Reporte Buffer MQTT-OPCUA - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-left: 4px solid #3498db;
            padding-left: 10px;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 36px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .stat-label {{
            font-size: 14px;
            opacity: 0.9;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #3498db;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .alert {{
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }}
        .alert-high {{
            background-color: #ffe4e1;
            border-left: 5px solid #ff6b6b;
        }}
        .alert-medium {{
            background-color: #fff3cd;
            border-left: 5px solid #ffc107;
        }}
        .alert-low {{
            background-color: #d4edda;
            border-left: 5px solid #28a745;
        }}
        .progress-bar {{
            background-color: #e0e0e0;
            border-radius: 10px;
            height: 20px;
            overflow: hidden;
        }}
        .progress-fill {{
            background: linear-gradient(90deg, #4CAF50, #8BC34A);
            height: 100%;
            transition: width 0.3s ease;
        }}
        .timestamp {{
            color: #7f8c8d;
            font-size: 12px;
            margin-top: 20px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <h1>📊 Reporte del Buffer Persistente MQTT-OPCUA</h1>
    
    <div class="card">
        <h2>Estado Actual</h2>
        <div class="stat-grid">
            <div class="stat-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                <div class="stat-label">Total Mensajes</div>
                <div class="stat-value">{current_stats['total']:,}</div>
            </div>
            <div class="stat-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                <div class="stat-label">Pendientes</div>
                <div class="stat-value">{current_stats['pending']:,}</div>
            </div>
            <div class="stat-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
                <div class="stat-label">Procesando</div>
                <div class="stat-value">{current_stats['processing']:,}</div>
            </div>
            <div class="stat-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
                <div class="stat-label">Completados</div>
                <div class="stat-value">{current_stats['completed']:,}</div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <h2>⚠️ Anomalías Detectadas</h2>
        {self._generate_anomalies_html(anomalies)}
    </div>
    
    <div class="card">
        <h2>📈 Rendimiento (Últimas 24 horas)</h2>
        <p><strong>Tendencia:</strong> {performance['trend']}</p>
        <p><strong>Tasa de éxito:</strong> {performance['success_rate']:.1f}%</p>
        <p><strong>Throughput promedio:</strong> {performance['avg_throughput_per_hour']:.0f} mensajes/hora</p>
        <p><strong>Tiempo de procesamiento promedio:</strong> {performance['avg_processing_time_seconds']:.2f} segundos</p>
        
        <div class="progress-bar">
            <div class="progress-fill" style="width: {performance['success_rate']}%"></div>
        </div>
    </div>
    
    <div class="card">
        <h2>🔮 Predicción de Carga (Próximas 6 horas)</h2>
        <p><strong>Carga total estimada:</strong> {prediction['estimated_total_load']:,} mensajes</p>
        <p><strong>Recomendación:</strong> {prediction['recommendation']}</p>
        
        <table>
            <thead>
                <tr>
                    <th>Hora</th>
                    <th>Mensajes Predichos</th>
                    <th>Rango (Min-Max)</th>
                    <th>Confianza</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for pred in prediction['predictions']:
            html += f"""
                <tr>
                    <td>{pred['time']}</td>
                    <td>{pred['predicted_messages']:,}</td>
                    <td>{pred['range_min']:,} - {pred['range_max']:,}</td>
                    <td>{pred['confidence']}%</td>
                </tr>
"""
        
        html += f"""
            </tbody>
        </table>
    </div>
    
    <div class="timestamp">
        Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Base de datos: {self.db_path}
    </div>
</body>
</html>
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✓ Reporte HTML generado: {output_file}")
        return output_file
    
    def _generate_anomalies_html(self, anomalies: List[Dict]) -> str:
        """Genera HTML para las anomalías"""
        if not anomalies:
            return '<p style="color: green;">✓ No se detectaron anomalías</p>'
        
        html = ""
        for anomaly in anomalies:
            severity_class = f"alert-{anomaly['severity']}"
            html += f'<div class="alert {severity_class}">'
            html += f"<strong>{anomaly['type'].replace('_', ' ').title()}:</strong> "
            html += anomaly['message']
            html += '</div>'
        
        return html
    
    def plot_metrics(self, output_dir: str = "metrics"):
        """
        Genera gráficos de métricas si matplotlib está disponible
        """
        if not MATPLOTLIB_AVAILABLE:
            print("Matplotlib no disponible. Instalar con: pip install matplotlib")
            return
        
        os.makedirs(output_dir, exist_ok=True)
        
        performance = self.analyze_performance(72)  # Últimas 72 horas
        
        if not performance['hourly_data']:
            print("No hay suficientes datos para generar gráficos")
            return
        
        # Preparar datos
        hours = [datetime.strptime(h['hour'], '%Y-%m-%d %H:00') for h in performance['hourly_data']]
        created = [h['created'] for h in performance['hourly_data']]
        completed = [h['completed'] for h in performance['hourly_data']]
        failed = [h['failed'] for h in performance['hourly_data']]
        
        # Gráfico 1: Throughput
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        ax1.plot(hours, created, label='Creados', color='blue', linewidth=2)
        ax1.plot(hours, completed, label='Completados', color='green', linewidth=2)
        ax1.plot(hours, failed, label='Fallidos', color='red', linewidth=2)
        ax1.set_xlabel('Tiempo')
        ax1.set_ylabel('Mensajes por hora')
        ax1.set_title('Throughput del Sistema')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:00'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
        
        # Gráfico 2: Tiempo de procesamiento
        processing_times = [h['avg_processing_time'] for h in performance['hourly_data']]
        ax2.bar(hours, processing_times, color='orange', alpha=0.7)
        ax2.set_xlabel('Tiempo')
        ax2.set_ylabel('Tiempo promedio (segundos)')
        ax2.set_title('Tiempo de Procesamiento Promedio')
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:00'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        output_file = os.path.join(output_dir, 'throughput_metrics.png')
        plt.savefig(output_file, dpi=100, bbox_inches='tight')
        print(f"✓ Gráfico generado: {output_file}")
        
        # Gráfico 3: Distribución de estados (pie chart)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM messages
                GROUP BY status
            """)
            
            statuses = []
            counts = []
            for row in cursor.fetchall():
                statuses.append(row['status'])
                counts.append(row['count'])
        
        if statuses:
            fig, ax = plt.subplots(figsize=(8, 8))
            colors = ['#4CAF50', '#FFC107', '#F44336', '#2196F3', '#9C27B0']
            ax.pie(counts, labels=statuses, colors=colors, autopct='%1.1f%%', startangle=90)
            ax.set_title('Distribución de Estados de Mensajes')
            
            output_file = os.path.join(output_dir, 'status_distribution.png')
            plt.savefig(output_file, dpi=100, bbox_inches='tight')
            print(f"✓ Gráfico generado: {output_file}")
        
        plt.close('all')

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Análisis avanzado del buffer persistente")
    parser.add_argument('--db', default='buffer.db', help='Ruta a la base de datos')
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Comando performance
    perf_parser = subparsers.add_parser('performance', help='Analizar rendimiento')
    perf_parser.add_argument('--hours', type=int, default=24, help='Horas a analizar')
    
    # Comando anomalies
    subparsers.add_parser('anomalies', help='Detectar anomalías')
    
    # Comando predict
    predict_parser = subparsers.add_parser('predict', help='Predecir carga futura')
    predict_parser.add_argument('--hours', type=int, default=6, help='Horas a predecir')
    
    # Comando report
    report_parser = subparsers.add_parser('report', help='Generar reporte HTML')
    report_parser.add_argument('--output', default='buffer_report.html', help='Archivo de salida')
    
    # Comando plot
    plot_parser = subparsers.add_parser('plot', help='Generar gráficos')
    plot_parser.ad