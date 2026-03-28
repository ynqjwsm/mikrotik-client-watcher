import logging
import requests
from typing import Optional, Dict, Any
from datetime import datetime


logger = logging.getLogger(__name__)


class FeishuNotifier:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url

    def set_webhook_url(self, url: str):
        self.webhook_url = url

    def send_message(self, message: str) -> bool:
        if not self.webhook_url:
            logger.warning("Feishu webhook URL not configured, skipping message")
            return False

        try:
            payload = {
                "msg_type": "text",
                "content": {
                    "text": message
                }
            }

            logger.debug(f"Sending message to Feishu: {message}")
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()

            if result.get('code') == 0:
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
        template: str,
        router_name: str,
        client_name: str,
        event_type: str,
        address: Optional[str] = None,
        mac_address: Optional[str] = None,
        hostname: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> str:
        timestamp = timestamp or datetime.now()
        placeholders = {
            "{router_name}": router_name,
            "{device_name}": router_name,
            "{client_name}": client_name,
            "{event_type}": event_type,
            "{address}": address or "N/A",
            "{mac_address}": mac_address or "N/A",
            "{hostname}": hostname or "N/A",
            "{timestamp}": timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }

        message = template
        for placeholder, value in placeholders.items():
            message = message.replace(placeholder, value)

        return message


feishu_notifier = FeishuNotifier()
