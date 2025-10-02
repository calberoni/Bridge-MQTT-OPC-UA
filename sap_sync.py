#!/usr/bin/env python3
"""Servicio standalone para sincronizar el buffer con SAP."""

import argparse
import asyncio
import signal

from config import load_config, setup_logging
from persistent_buffer import PersistentBuffer
from sap_bridge.sap_workers import SAPBridgeManager


async def main():
    parser = argparse.ArgumentParser(description="SAP Bridge Connector")
    parser.add_argument('--config', default='bridge_config.yaml', help='Archivo de configuración')
    args = parser.parse_args()

    config = load_config(args.config)
    logger = setup_logging(config.logging)

    if not getattr(config, 'sap', None) or not config.sap.enabled:
        logger.warning("SAP Bridge Connector deshabilitado en la configuración")
        return

    buffer = PersistentBuffer(
        db_path=config.persistence_file.replace('.json', '.db'),
        max_size=config.buffer_size,
        ttl_minutes=getattr(config, 'message_ttl_minutes', 60),
        cleanup_interval=getattr(config, 'cleanup_interval', 300),
        logger=logger,
    )

    manager = SAPBridgeManager(config.sap, config, buffer, logger)
    await manager.start()

    stop_event = asyncio.Event()

    def _signal_handler(signum, frame):
        logger.info("Señal recibida: %s", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    await stop_event.wait()
    await manager.stop()
    buffer.close()


if __name__ == "__main__":
    asyncio.run(main())
