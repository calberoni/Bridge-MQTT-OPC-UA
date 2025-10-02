FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py ./
COPY persistent_buffer.py ./
COPY mqtt_opcua_bridge.py ./
COPY buffer_monitor.py ./
COPY buffer_analytics.py ./
COPY bridge_config.yaml ./

RUN mkdir -p /app/logs /app/data

EXPOSE 4840
CMD ["python", "mqtt_opcua_bridge.py"]
