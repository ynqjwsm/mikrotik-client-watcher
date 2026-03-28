from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class PushRuleType(str, Enum):
    APPEAR = "appear"
    DISAPPEAR = "disappear"
    ALIVE = "alive"


class ClientPushRule(BaseModel):
    type: PushRuleType
    enabled: bool = True
    interval_minutes: Optional[int] = Field(None, ge=1)


class ClientMonitor(BaseModel):
    id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S%f"))
    name: str
    address: Optional[str] = None
    mac_address: Optional[str] = None
    active_hostname: Optional[str] = None
    push_rules: List[ClientPushRule] = Field(default_factory=list)
    last_seen: Optional[datetime] = None
    is_online: bool = False
    last_push_times: Dict[str, Any] = Field(default_factory=dict)
    message_template: Optional[str] = None
    enabled: bool = True

    @field_validator('last_push_times', mode='before')
    @classmethod
    def parse_last_push_times(cls, v):
        if isinstance(v, dict):
            parsed = {}
            for key, value in v.items():
                if isinstance(value, str):
                    try:
                        parsed[key] = datetime.fromisoformat(value)
                    except (ValueError, TypeError):
                        parsed[key] = value
                else:
                    parsed[key] = value
            return parsed
        return v

    @field_validator('address', 'mac_address', 'active_hostname')
    @classmethod
    def check_at_least_one_identifier(cls, v, info):
        if info.field_name == 'active_hostname':
            values = info.data
            if not any([values.get('address'), values.get('mac_address'), v]):
                raise ValueError('At least one of address, mac_address, or active_hostname must be provided')
        return v

    def matches(self, dhcp_client: Dict[str, Any]) -> bool:
        if self.address and self.address not in str(dhcp_client.get('address', '')):
            return False
        if self.mac_address and self.mac_address.lower() not in str(dhcp_client.get('mac-address', '')).lower():
            return False
        if self.active_hostname:
            hostname = str(dhcp_client.get('host-name', '')).lower()
            if self.active_hostname.lower() not in hostname:
                return False
        return True


class RosRouter(BaseModel):
    id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S%f"))
    name: str
    host: str
    port: int = 8728
    username: str
    password: str
    ssl: bool = False
    poll_interval_seconds: int = 30
    clients: List[ClientMonitor] = Field(default_factory=list)
    enabled: bool = True


class Config(BaseModel):
    feishu_webhook_url: Optional[str] = None
    routers: List[RosRouter] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.now)
