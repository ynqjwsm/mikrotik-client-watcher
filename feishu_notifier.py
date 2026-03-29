import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

import requests

from time_utils import now, format_datetime


logger = logging.getLogger(__name__)


@dataclass
class MessageContext:
    router_name: str
    client_name: str
    event_type: str
    address: Optional[str] = None
    mac_address: Optional[str] = None
    hostname: Optional[str] = None
    timestamp: Optional[datetime] = None


_DEFAULT_TEMPLATE = "{router_name} - {client_name} {event_type}"


class FeishuNotifier:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url

    def set_webhook_url(self, url: str) -> None:
        self.webhook_url = url

    def send_message(self, message: str) -> bool:
        if not self.webhook_url:
            logger.warning("Feishu webhook URL not configured, skipping message")
            return False

        try:
            payload = {"msg_type": "text", "content": {"text": message}}

            logger.debug(f"Sending message to Feishu: {message}")
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("code") == 0:
                logger.info("Message sent to Feishu successfully")
                return True
            else:
                logger.error(f"Feishu API returned error: {result}")
                return False

        except Exception as e:
            logger.error(f"Failed to send message to Feishu: {e}")
            return False

    def format_message(
        self,
        template: Optional[str],
        context: MessageContext,
    ) -> str:
        timestamp = context.timestamp or now()
        placeholders = {
            "{router_name}": context.router_name,
            "{device_name}": context.router_name,
            "{client_name}": context.client_name,
            "{event_type}": context.event_type,
            "{address}": context.address or "N/A",
            "{mac_address}": context.mac_address or "N/A",
            "{hostname}": context.hostname or "N/A",
            "{timestamp}": format_datetime(timestamp),
        }

        message = template or _DEFAULT_TEMPLATE
        for placeholder, value in placeholders.items():
            message = message.replace(placeholder, value)

        return message
