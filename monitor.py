import logging
from datetime import timedelta
from typing import Dict, Any, Optional

from models import RosRouter, ClientMonitor, PushRuleType
from mikrotik_client import MikroTikClient
from feishu_notifier import feishu_notifier, MessageContext
from config import config_manager
from time_utils import now


logger = logging.getLogger(__name__)


class RouterMonitor:
    def __init__(self, router: RosRouter):
        self.router = router
        self.online_client_info: Dict[str, Dict[str, Any]] = {}

    def poll(self) -> None:
        if not self.router.enabled:
            logger.debug(f"Router {self.router.name} is disabled, skipping poll")
            return

        logger.info(f"Polling router: {self.router.name}")
        try:
            with MikroTikClient(self.router) as client:
                dhcp_clients = client.get_dhcp_clients()
                self._process_clients(dhcp_clients, is_manual_refresh=False)
        except Exception as e:
            logger.error(f"Error polling router {self.router.name}: {e}")

    def manual_refresh(self) -> None:
        if not self.router.enabled:
            logger.debug(f"Router {self.router.name} is disabled, skipping manual refresh")
            return

        logger.info(f"Manual refresh for router: {self.router.name}")
        try:
            with MikroTikClient(self.router) as client:
                dhcp_clients = client.get_dhcp_clients()
                self._process_clients(dhcp_clients, is_manual_refresh=True)
        except Exception as e:
            logger.error(f"Error in manual refresh for router {self.router.name}: {e}")

    def _process_clients(
        self, dhcp_clients: list[Dict[str, Any]], is_manual_refresh: bool = False
    ) -> None:
        current_time = now()

        for client_monitor in self.router.clients:
            if not client_monitor.enabled:
                continue

            was_online = client_monitor.is_online
            is_online_now, matched_client = self._match_client(client_monitor, dhcp_clients)

            if is_online_now:
                client_monitor.last_seen = current_time
                if matched_client:
                    self.online_client_info[client_monitor.id] = matched_client.copy()

            client_info_for_push = self._get_client_info_for_push(
                is_online_now, matched_client, client_monitor.id
            )

            if is_online_now != was_online:
                self._handle_status_change(
                    client_monitor,
                    is_online_now,
                    client_info_for_push,
                    is_manual_refresh,
                )

            client_monitor.is_online = is_online_now

            if is_online_now:
                self._handle_alive_push(
                    client_monitor, matched_client, is_manual_refresh
                )

            if not is_online_now and client_monitor.id in self.online_client_info:
                del self.online_client_info[client_monitor.id]

            config_manager.update_client_state(
                self.router.id,
                client_monitor.id,
                is_online_now,
                client_monitor.last_seen,
            )

    def _match_client(
        self, client_monitor: ClientMonitor, dhcp_clients: list[Dict[str, Any]]
    ) -> tuple[bool, Optional[Dict[str, Any]]]:
        for dhcp_client in dhcp_clients:
            if client_monitor.matches(dhcp_client):
                return True, dhcp_client
        return False, None

    def _get_client_info_for_push(
        self, is_online_now: bool, matched_client: Optional[Dict[str, Any]], client_id: str
    ) -> Optional[Dict[str, Any]]:
        if is_online_now:
            return matched_client
        if not matched_client and client_id in self.online_client_info:
            return self.online_client_info[client_id]
        return matched_client

    def _handle_status_change(
        self,
        client_monitor: ClientMonitor,
        is_online: bool,
        matched_client: Optional[Dict[str, Any]],
        is_manual_refresh: bool,
    ) -> None:
        event_type = "上线" if is_online else "下线"
        logger.info(f"Client {client_monitor.name} status changed: {not is_online} -> {is_online}")

        rule_type = PushRuleType.APPEAR if is_online else PushRuleType.DISAPPEAR
        rule = self._find_rule(client_monitor, rule_type)

        if rule and rule.enabled:
            self._send_push(
                client_monitor,
                rule_type,
                event_type,
                matched_client,
                is_manual_refresh,
            )

    def _handle_alive_push(
        self,
        client_monitor: ClientMonitor,
        matched_client: Optional[Dict[str, Any]],
        is_manual_refresh: bool,
    ) -> None:
        rule = self._find_rule(client_monitor, PushRuleType.ALIVE)
        if not rule or not rule.enabled or not rule.interval_minutes:
            return

        current_time = now()
        last_push = client_monitor.last_push_times.get(PushRuleType.ALIVE)

        if last_push is None or (current_time - last_push) >= timedelta(minutes=rule.interval_minutes):
            self._send_push(
                client_monitor,
                PushRuleType.ALIVE,
                "存活",
                matched_client,
                is_manual_refresh,
            )

    def _find_rule(
        self, client_monitor: ClientMonitor, rule_type: PushRuleType
    ) -> Optional[Any]:
        for rule in client_monitor.push_rules:
            if rule.type == rule_type:
                return rule
        return None

    def _send_push(
        self,
        client_monitor: ClientMonitor,
        rule_type: PushRuleType,
        event_type: str,
        matched_client: Optional[Dict[str, Any]],
        is_manual_refresh: bool,
    ) -> None:
        current_time = now()
        address = matched_client.get("address") if matched_client else None
        mac_address = matched_client.get("mac-address") if matched_client else None
        hostname = matched_client.get("host-name") if matched_client else None

        context = MessageContext(
            router_name=self.router.name,
            client_name=client_monitor.name,
            event_type=event_type,
            address=address,
            mac_address=mac_address,
            hostname=hostname,
            timestamp=current_time,
        )

        message = feishu_notifier.format_message(
            template=client_monitor.message_template,
            context=context,
        )

        if feishu_notifier.send_message(message):
            if not is_manual_refresh:
                client_monitor.last_push_times[rule_type] = current_time
                config_manager.update_client_last_push(
                    self.router.id,
                    client_monitor.id,
                    rule_type,
                    current_time,
                )
