import logging
from typing import List, Dict, Any, Optional
import librouteros
from models import RosRouter


logger = logging.getLogger(__name__)


class MikroTikClient:
    def __init__(self, router: RosRouter):
        self.router = router
        self.connection: Optional[librouteros.Api] = None

    def connect(self):
        try:
            logger.debug(f"Connecting to MikroTik router: {self.router.name} ({self.router.host}:{self.router.port})")
            self.connection = librouteros.connect(
                host=self.router.host,
                port=self.router.port,
                username=self.router.username,
                password=self.router.password,
                ssl=self.router.ssl,
                timeout=10
            )
            logger.info(f"Connected to MikroTik router: {self.router.name}")
        except Exception as e:
            logger.error(f"Failed to connect to MikroTik router {self.router.name}: {e}")
            raise

    def disconnect(self):
        if self.connection:
            try:
                self.connection.close()
                logger.debug(f"Disconnected from MikroTik router: {self.router.name}")
            except Exception as e:
                logger.error(f"Error while disconnecting from MikroTik router {self.router.name}: {e}")
            finally:
                self.connection = None

    def get_dhcp_clients(self) -> List[Dict[str, Any]]:
        if not self.connection:
            self.connect()

        try:
            logger.debug(f"Fetching DHCP clients from {self.router.name}")
            dhcp_lease = self.connection.path('ip', 'dhcp-server', 'lease')
            clients = list(dhcp_lease)
            logger.info(f"Fetched {len(clients)} DHCP clients from {self.router.name}")
            return clients
        except Exception as e:
            logger.error(f"Failed to fetch DHCP clients from {self.router.name}: {e}")
            raise

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
