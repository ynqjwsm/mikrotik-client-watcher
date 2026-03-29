import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from models import Config, RosRouter, ClientMonitor, FeishuConfig, EmailConfig
from settings import settings
from time_utils import now


logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self):
        self.data_dir = settings.data_dir
        self.config_file = self.data_dir / "config.json"
        self.log_dir = self.data_dir / "logs"

        self._initialize_directories()
        self._config: Optional[Config] = None
        self._load_config()

    def _initialize_directories(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _migrate_config(self, data: dict) -> dict:
        if "feishu_webhook_url" in data and "feishu" not in data:
            data["feishu"] = {
                "enabled": True,
                "webhook_url": data["feishu_webhook_url"]
            }
            del data["feishu_webhook_url"]
        if "feishu" not in data:
            data["feishu"] = {"enabled": True, "webhook_url": None}
        if "email" not in data:
            data["email"] = {
                "enabled": False,
                "smtp_host": "",
                "smtp_port": 587,
                "smtp_username": "",
                "smtp_password": "",
                "use_tls": True,
                "use_ssl": False,
                "from_email": None,
                "to_emails": []
            }
        return data

    def _load_config(self) -> None:
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data = self._migrate_config(data)
                self._config = Config(**data)
                logger.info(f"Loaded configuration from {self.config_file}")
            except Exception as e:
                logger.error(f"Failed to load config, creating default: {e}")
                self._create_default_config()
        else:
            self._create_default_config()

    def _create_default_config(self) -> None:
        self._config = Config()
        self._save_config()
        logger.info(f"Created default configuration at {self.config_file}")

    def _save_config(self) -> None:
        if self._config is None:
            return
        self._config.last_updated = now()
        data = self._config.model_dump(mode="json")
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @property
    def config(self) -> Config:
        if self._config is None:
            raise RuntimeError("Config not initialized")
        return self._config

    def get_feishu_config(self) -> FeishuConfig:
        return self._config.feishu if self._config else FeishuConfig()

    def set_feishu_config(self, config: FeishuConfig) -> None:
        if self._config:
            self._config.feishu = config
            self._save_config()

    def get_feishu_webhook_url(self) -> Optional[str]:
        return self._config.feishu.webhook_url if self._config else None

    def set_feishu_webhook_url(self, url: str) -> None:
        if self._config:
            self._config.feishu.webhook_url = url
            self._save_config()

    def get_email_config(self) -> EmailConfig:
        return self._config.email if self._config else EmailConfig()

    def set_email_config(self, config: EmailConfig) -> None:
        if self._config:
            self._config.email = config
            self._save_config()

    def get_routers(self) -> list[RosRouter]:
        return self._config.routers if self._config else []

    def get_router(self, router_id: str) -> Optional[RosRouter]:
        if not self._config:
            return None
        for router in self._config.routers:
            if router.id == router_id:
                return router
        return None

    def add_router(self, router: RosRouter) -> None:
        if self._config:
            self._config.routers.append(router)
            self._save_config()

    def update_router(self, router_id: str, router: RosRouter) -> None:
        if not self._config:
            raise ValueError("Config not initialized")
        for i, r in enumerate(self._config.routers):
            if r.id == router_id:
                router.id = router_id
                self._config.routers[i] = router
                self._save_config()
                return
        raise ValueError(f"Router with id {router_id} not found")

    def delete_router(self, router_id: str) -> None:
        if self._config:
            self._config.routers = [r for r in self._config.routers if r.id != router_id]
            self._save_config()

    def add_client(self, router_id: str, client: ClientMonitor) -> None:
        router = self.get_router(router_id)
        if router:
            router.clients.append(client)
            self._save_config()
        else:
            raise ValueError(f"Router with id {router_id} not found")

    def update_client(self, router_id: str, client_id: str, client: ClientMonitor) -> None:
        router = self.get_router(router_id)
        if not router:
            raise ValueError(f"Router with id {router_id} not found")
        for i, c in enumerate(router.clients):
            if c.id == client_id:
                client.id = client_id
                router.clients[i] = client
                self._save_config()
                return
        raise ValueError(f"Client with id {client_id} not found")

    def delete_client(self, router_id: str, client_id: str) -> None:
        router = self.get_router(router_id)
        if router:
            router.clients = [c for c in router.clients if c.id != client_id]
            self._save_config()

    def update_client_state(
        self, router_id: str, client_id: str, is_online: bool, last_seen: datetime
    ) -> None:
        router = self.get_router(router_id)
        if router:
            for client in router.clients:
                if client.id == client_id:
                    client.is_online = is_online
                    client.last_seen = last_seen
                    self._save_config()
                    return

    def update_client_last_push(
        self, router_id: str, client_id: str, rule_type: str, push_time: datetime
    ) -> None:
        router = self.get_router(router_id)
        if router:
            for client in router.clients:
                if client.id == client_id:
                    client.last_push_times[rule_type] = push_time
                    self._save_config()
                    return

    def toggle_router_enabled(self, router_id: str, enabled: bool) -> bool:
        router = self.get_router(router_id)
        if router:
            router.enabled = enabled
            self._save_config()
            return True
        return False

    def toggle_client_enabled(self, router_id: str, client_id: str, enabled: bool) -> bool:
        router = self.get_router(router_id)
        if router:
            for client in router.clients:
                if client.id == client_id:
                    client.enabled = enabled
                    self._save_config()
                    return True
        return False


config_manager = ConfigManager()
