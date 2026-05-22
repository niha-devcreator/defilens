"""Price and portfolio alert system with webhook support."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any

import httpx

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PORTFOLIO_CHANGE = "portfolio_change"
    YIELD_DROP = "yield_drop"
    WHALE_DETECTED = "whale_detected"


@dataclass
class Alert:
    id: str
    alert_type: AlertType
    target: str  # symbol, address, or "portfolio"
    threshold: float
    message: str = ""
    webhook_url: str = ""
    triggered: bool = False
    created_at: float = field(default_factory=time.time)
    last_checked: float = 0.0


class AlertManager:
    """Manages price and portfolio alerts with webhook delivery."""

    def __init__(self):
        self._alerts: dict[str, Alert] = {}
        self._callbacks: list[Callable] = []

    def add_alert(self, alert: Alert) -> str:
        self._alerts[alert.id] = alert
        logger.info("Alert created: %s %s %s", alert.alert_type.value, alert.target, alert.threshold)
        return alert.id

    def remove_alert(self, alert_id: str) -> bool:
        return self._alerts.pop(alert_id, None) is not None

    def list_alerts(self, active_only: bool = True) -> list[Alert]:
        alerts = list(self._alerts.values())
        if active_only:
            alerts = [a for a in alerts if not a.triggered]
        return alerts

    async def check_price_alert(self, symbol: str, current_price: float) -> list[Alert]:
        triggered = []
        for alert in self._alerts.values():
            if alert.triggered or alert.alert_type not in (AlertType.PRICE_ABOVE, AlertType.PRICE_BELOW):
                continue
            if alert.target.upper() != symbol.upper():
                continue

            should_trigger = False
            if alert.alert_type == AlertType.PRICE_ABOVE and current_price >= alert.threshold:
                should_trigger = True
            elif alert.alert_type == AlertType.PRICE_BELOW and current_price <= alert.threshold:
                should_trigger = True

            if should_trigger:
                alert.triggered = True
                alert.message = f"{symbol} hit ${current_price:.2f} (threshold: ${alert.threshold:.2f})"
                triggered.append(alert)
                if alert.webhook_url:
                    await self._send_webhook(alert)

        return triggered

    async def _send_webhook(self, alert: Alert):
        payload = {
            "alert_id": alert.id,
            "type": alert.alert_type.value,
            "target": alert.target,
            "message": alert.message,
            "timestamp": alert.last_checked,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(alert.webhook_url, json=payload)
                logger.info("Webhook sent (%d): %s", resp.status_code, alert.webhook_url)
        except Exception as e:
            logger.warning("Webhook failed: %s", e)

    def on_alert(self, callback: Callable):
        self._callbacks.append(callback)
