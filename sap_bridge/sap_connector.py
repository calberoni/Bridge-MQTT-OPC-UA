"""Conector HTTP hacia SAP."""

import time
from typing import Any, Dict, Optional

import requests

from config import SAPConfig, SAPMapping


class SAPConnector:
    """Cliente HTTP simple para SAP."""

    def __init__(self, config: SAPConfig, logger):
        self.config = config
        self.logger = logger.getChild("sap.connector")
        self.session = requests.Session()
        self._token_info: Optional[Dict[str, Any]] = None
        if self.config.auth.type.lower() == "basic":
            self.session.auth = (
                self.config.auth.username,
                self.config.auth.password,
            )

    def push(self, payload: Dict[str, Any], mapping: SAPMapping) -> bool:
        url = self._build_url(mapping.outbound.resource_path or mapping.resource_path)
        headers = self._build_headers()
        for attempt in range(1, mapping.retry.max_attempts + 1):
            try:
                response = self.session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.config.timeout,
                )
                if response.status_code in (200, 201, 202):
                    return True
                self.logger.warning(
                    "SAP push fallo status=%s body=%s", response.status_code, response.text
                )
            except requests.RequestException as exc:
                self.logger.error(
                    "SAP push error intento %s/%s: %s",
                    attempt,
                    mapping.retry.max_attempts,
                    exc,
                )
            time.sleep(mapping.retry.backoff_seconds)
        return False

    def fetch(self, mapping: SAPMapping) -> Optional[Any]:
        url = self._build_url(mapping.resource_path)
        headers = self._build_headers()
        try:
            response = self.session.get(
                url,
                params=mapping.query_params,
                headers=headers,
                timeout=self.config.timeout,
            )
            if response.status_code == 200:
                return response.json()
            self.logger.warning(
                "SAP fetch fallo status=%s body=%s", response.status_code, response.text
            )
        except requests.RequestException as exc:
            self.logger.error("SAP fetch error: %s", exc)
        return None

    def _build_url(self, path: str) -> str:
        base = self.config.endpoint.rstrip('/')
        path = (path or '').lstrip('/')
        return f"{base}/{path}" if path else base

    def _build_headers(self) -> Dict[str, str]:
        if self.config.auth.type.lower() == "oauth2":
            token = self._get_oauth_token()
            if token:
                return {"Authorization": f"Bearer {token}"}
        return {}

    def _get_oauth_token(self) -> Optional[str]:
        if self._token_info and self._token_info.get("expires_at", 0) > time.time():
            return self._token_info.get("access_token")
        creds = self.config.auth
        if not creds.token_url or not creds.client_id or not creds.client_secret:
            self.logger.error("OAuth2 mal configurado")
            return None
        try:
            response = self.session.post(
                creds.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scope": creds.scope or "",
                },
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            data = response.json()
            expires_in = data.get("expires_in", 3600)
            self._token_info = {
                "access_token": data.get("access_token"),
                "expires_at": time.time() + max(30, int(expires_in) - 60),
            }
            return self._token_info["access_token"]
        except requests.RequestException as exc:
            self.logger.error("OAuth2 token error: %s", exc)
        return None
