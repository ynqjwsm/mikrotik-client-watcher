import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from models import EmailConfig
from feishu_notifier import MessageContext
from time_utils import format_datetime


logger = logging.getLogger(__name__)


_DEFAULT_EMAIL_SUBJECT = "{router_name} - {client_name} {event_type}"
_DEFAULT_EMAIL_TEMPLATE = """
{router_name} - {client_name} {event_type}

IP地址: {address}
MAC地址: {mac_address}
主机名: {hostname}
时间: {timestamp}
"""


class EmailNotifier:
    def __init__(self, config: Optional[EmailConfig] = None):
        self.config = config or EmailConfig()

    def set_config(self, config: EmailConfig) -> None:
        self.config = config

    def send_message(
        self,
        subject: str,
        body: str,
    ) -> bool:
        if not self.config.enabled:
            logger.debug("Email notifications are disabled")
            return False

        if not self.config.smtp_host:
            logger.warning("SMTP host not configured, skipping email")
            return False

        if not self.config.to_emails:
            logger.warning("No recipient emails configured, skipping email")
            return False

        server = None
        try:
            msg = MIMEMultipart()
            from_email = self.config.from_email or self.config.smtp_username
            msg["From"] = from_email
            msg["To"] = ", ".join(self.config.to_emails)
            msg["Subject"] = subject

            msg.attach(MIMEText(body, "plain", "utf-8"))

            if self.config.use_ssl:
                server = smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port)
            else:
                server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)
                if self.config.use_tls:
                    server.starttls()

            if self.config.smtp_username and self.config.smtp_password:
                server.login(self.config.smtp_username, self.config.smtp_password)

            text = msg.as_string()
            server.sendmail(from_email, self.config.to_emails, text)

            logger.info("Email sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    def format_subject(
        self,
        template: Optional[str],
        context: MessageContext,
    ) -> str:
        timestamp = context.timestamp
        placeholders = {
            "{router_name}": context.router_name,
            "{device_name}": context.router_name,
            "{client_name}": context.client_name,
            "{event_type}": context.event_type,
            "{address}": context.address or "N/A",
            "{mac_address}": context.mac_address or "N/A",
            "{hostname}": context.hostname or "N/A",
            "{timestamp}": format_datetime(timestamp) if timestamp else "",
        }

        subject = _DEFAULT_EMAIL_SUBJECT
        for placeholder, value in placeholders.items():
            subject = subject.replace(placeholder, value)

        return subject

    def format_body(
        self,
        template: Optional[str],
        context: MessageContext,
    ) -> str:
        timestamp = context.timestamp
        placeholders = {
            "{router_name}": context.router_name,
            "{device_name}": context.router_name,
            "{client_name}": context.client_name,
            "{event_type}": context.event_type,
            "{address}": context.address or "N/A",
            "{mac_address}": context.mac_address or "N/A",
            "{hostname}": context.hostname or "N/A",
            "{timestamp}": format_datetime(timestamp) if timestamp else "",
        }

        body = template or _DEFAULT_EMAIL_TEMPLATE
        for placeholder, value in placeholders.items():
            body = body.replace(placeholder, value)

        return body


email_notifier = EmailNotifier()
