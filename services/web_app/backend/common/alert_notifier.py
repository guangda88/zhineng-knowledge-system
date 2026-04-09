# -*- coding: utf-8 -*-
"""
安全告警通知系统
Security Alert Notification System

通过多种渠道发送安全告警：
- 邮件
- Slack
- 钉钉
- 企业微信
- Webhook
"""

import logging
import httpx
from typing import Optional, List, Dict
from dataclasses import dataclass
from enum import Enum

from .security_monitoring import SecurityAlert, SecurityEventSeverity

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """通知渠道"""

    EMAIL = "email"
    SLACK = "slack"
    DINGTALK = "dingtalk"
    WEWORK = "wework"
    WEBHOOK = "webhook"


@dataclass
class NotificationConfig:
    """通知配置"""

    # 邮件配置
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: str = "security@zhineng.com"
    smtp_tls: bool = True

    # 收件人列表
    email_recipients: List[str] = []

    # Slack配置
    slack_webhook_url: Optional[str] = None
    slack_channel: str = "#security-alerts"

    # 钉钉配置
    dingtalk_webhook_url: Optional[str] = None
    dingtalk_secret: Optional[str] = None

    # 企业微信配置
    wework_webhook_url: Optional[str] = None

    # 通用Webhook配置
    webhook_url: Optional[str] = None
    webhook_headers: Dict[str, str] = None

    # 通知过滤
    min_severity: SecurityEventSeverity = SecurityEventSeverity.MEDIUM
    enable_cooldown: bool = True
    cooldown_minutes: int = 30


class SecurityAlertNotifier:
    """
    安全告警通知器

    通过配置的渠道发送安全告警通知。

    Features:
    - 多渠道支持
    - 告警过滤（严重性）
    - 冷却时间（防止重复通知）
    - 通知模板
    - 通知状态跟踪
    """

    def __init__(self, config: Optional[NotificationConfig] = None):
        """
        初始化告警通知器

        Args:
            config: 通知配置
        """
        self.config = config or NotificationConfig()
        self.notified_alerts: Dict[str, float] = {}
        self.http_client = httpx.AsyncClient(timeout=30.0)

        logger.info("Security Alert Notifier initialized")

    async def send_alert(
        self, alert: "SecurityAlert", channels: Optional[List[NotificationChannel]] = None
    ) -> bool:
        """
        发送告警通知

        Args:
            alert: 安全告警
            channels: 通知渠道列表（None=使用所有已配置的渠道）

        Returns:
            是否发送成功
        """
        # 检查严重性过滤
        if alert.severity.value < self.config.min_severity.value:
            logger.debug(
                f"Alert {alert.alert_id} severity "
                f"({alert.severity.value}) below threshold "
                f"({self.config.min_severity.value}), skipping notification"
            )
            return False

        # 检查冷却时间
        if self.config.enable_cooldown:
            last_notified = self.notified_alerts.get(alert.alert_id, 0)
            import time

            cooldown_seconds = self.config.cooldown_minutes * 60

            if time.time() - last_notified < cooldown_seconds:
                logger.debug(f"Alert {alert.alert_id} in cooldown, skipping notification")
                return False

        # 确定发送渠道
        if channels is None:
            channels = self._get_available_channels()

        # 发送通知
        success = False
        for channel in channels:
            try:
                channel_success = await self._send_to_channel(channel, alert)
                if channel_success:
                    success = True
                    logger.info(f"Alert {alert.alert_id} sent via {channel.value}")
            except Exception as e:
                logger.error(
                    f"Failed to send alert {alert.alert_id} " f"via {channel.value}: {str(e)}"
                )

        # 记录通知时间
        if success:
            import time

            self.notified_alerts[alert.alert_id] = time.time()

        return success

    async def _send_to_channel(self, channel: NotificationChannel, alert: "SecurityAlert") -> bool:
        """
        发送到指定渠道

        Args:
            channel: 通知渠道
            alert: 安全告警

        Returns:
            是否发送成功
        """
        if channel == NotificationChannel.EMAIL:
            return await self._send_email(alert)
        elif channel == NotificationChannel.SLACK:
            return await self._send_slack(alert)
        elif channel == NotificationChannel.DINGTALK:
            return await self._send_dingtalk(alert)
        elif channel == NotificationChannel.WEWORK:
            return await self._send_wework(alert)
        elif channel == NotificationChannel.WEBHOOK:
            return await self._send_webhook(alert)
        else:
            logger.warning(f"Unknown channel: {channel.value}")
            return False

    async def _send_email(self, alert: "SecurityAlert") -> bool:
        """发送邮件通知"""
        if not self.config.smtp_host or not self.config.email_recipients:
            logger.warning("Email not configured")
            return False

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.utils import formataddr

            # 创建邮件
            msg = MIMEMultipart("alternative")
            msg["Subject"] = self._get_email_subject(alert)
            msg["From"] = formataddr(("ZBOX Security", self.config.smtp_from))
            msg["To"] = ", ".join(self.config.email_recipients)

            # HTML内容
            html_content = self._get_email_html(alert)
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            # 发送邮件
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.smtp_tls:
                    server.starttls()

                if self.config.smtp_username:
                    server.login(self.config.smtp_username, self.config.smtp_password)

                server.send_message(msg)

            logger.info(f"Email alert sent for {alert.alert_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {str(e)}")
            return False

    async def _send_slack(self, alert: "SecurityAlert") -> bool:
        """发送Slack通知"""
        if not self.config.slack_webhook_url:
            logger.warning("Slack webhook not configured")
            return False

        try:
            payload = {
                "channel": self.config.slack_channel,
                "username": "Security Bot",
                "icon_emoji": self._get_emoji(alert.severity),
                "attachments": [
                    {
                        "color": self._get_color(alert.severity),
                        "title": self._get_slack_title(alert),
                        "text": alert.message,
                        "fields": [
                            {
                                "title": "Alert ID",
                                "value": alert.alert_id,
                                "short": True,
                            },
                            {
                                "title": "Severity",
                                "value": alert.severity.value.upper(),
                                "short": True,
                            },
                            {
                                "title": "Events",
                                "value": str(alert.event_count),
                                "short": True,
                            },
                            {
                                "title": "Triggered At",
                                "value": alert.datetime,
                                "short": True,
                            },
                        ],
                    }
                ],
            }

            response = await self.http_client.post(self.config.slack_webhook_url, json=payload)

            if response.status_code == 200:
                logger.info(f"Slack alert sent for {alert.alert_id}")
                return True
            else:
                logger.warning(f"Slack webhook returned status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {str(e)}")
            return False

    async def _send_dingtalk(self, alert: "SecurityAlert") -> bool:
        """发送钉钉通知"""
        if not self.config.dingtalk_webhook_url:
            logger.warning("Dingtalk webhook not configured")
            return False

        try:
            # 钉钉Markdown格式
            markdown = self._get_dingtalk_markdown(alert)

            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "安全告警",
                    "text": markdown,
                },
            }

            # 签名（如果配置了密钥）
            if self.config.dingtalk_secret:
                import hmac
                import hashlib
                import base64
                import urllib.parse

                timestamp = str(int(time.time() * 1000))
                secret_enc = urllib.parse.quote_plus(self.config.dingtalk_secret)
                string_to_sign = f"{timestamp}\n{secret_enc}"
                hmac_code = hmac.new(
                    self.config.dingtalk_secret.encode("utf-8"),
                    string_to_sign.encode("utf-8"),
                    hashlib.sha256,
                ).digest()
                sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode())

                payload["sign"] = sign
                payload["timestamp"] = timestamp

            response = await self.http_client.post(self.config.dingtalk_webhook_url, json=payload)

            if response.status_code == 200:
                logger.info(f"Dingtalk alert sent for {alert.alert_id}")
                return True
            else:
                logger.warning(f"Dingtalk webhook returned status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Dingtalk alert: {str(e)}")
            return False

    async def _send_wework(self, alert: "SecurityAlert") -> bool:
        """发送企业微信通知"""
        if not self.config.wework_webhook_url:
            logger.warning("WeWork webhook not configured")
            return False

        try:
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": self._get_wework_markdown(alert),
                },
            }

            response = await self.http_client.post(self.config.wework_webhook_url, json=payload)

            if response.status_code == 200:
                logger.info(f"WeWork alert sent for {alert.alert_id}")
                return True
            else:
                logger.warning(f"WeWork webhook returned status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to send WeWork alert: {str(e)}")
            return False

    async def _send_webhook(self, alert: "SecurityAlert") -> bool:
        """发送通用Webhook通知"""
        if not self.config.webhook_url:
            logger.warning("Webhook URL not configured")
            return False

        try:
            headers = self.config.webhook_headers or {"Content-Type": "application/json"}

            payload = {
                "alert_id": alert.alert_id,
                "event_type": alert.event_type.value,
                "severity": alert.severity.value,
                "message": alert.message,
                "events": [e.to_dict() for e in alert.events],
                "triggered_at": alert.triggered_at,
            }

            response = await self.http_client.post(
                self.config.webhook_url, json=payload, headers=headers
            )

            if response.status_code in [200, 201, 202, 204]:
                logger.info(f"Webhook alert sent for {alert.alert_id}")
                return True
            else:
                logger.warning(f"Webhook returned status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to send webhook alert: {str(e)}")
            return False

    def _get_email_subject(self, alert: "SecurityAlert") -> str:
        """获取邮件主题"""
        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
        }
        emoji = severity_emoji.get(alert.severity.value, "⚠️")
        return (
            f"{emoji} [{alert.severity.value.upper()}] {alert.event_type.value} - {alert.alert_id}"
        )

    def _get_email_html(self, alert: "SecurityAlert") -> str:
        """获取邮件HTML内容"""
        color = self._get_color(alert.severity)

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .header {{ background-color: {color}; color: white; padding: 15px; border-radius: 5px; }}
                .content {{ padding: 20px; border: 1px solid #ddd; border-radius: 5px; margin-top: 15px; }}
                .event {{ margin-bottom: 10px; padding: 10px; background-color: #f9f9f9; border-radius: 3px; }}
                .severity {{ font-weight: bold; color: {color}; }}
                .timestamp {{ color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🛡️ 安全告警</h2>
                </div>
                <div class="content">
                    <p class="severity">严重性: {alert.severity.value.upper()}</p>
                    <p><strong>消息:</strong> {alert.message}</p>
                    <p><strong>类型:</strong> {alert.event_type.value}</p>
                    <p><strong>事件数:</strong> {alert.event_count}</p>
                    <p><strong>触发时间:</strong> {alert.datetime}</p>

                    <h3>事件详情:</h3>
        """

        for event in alert.events[:5]:  # 最多显示5个事件
            html += f"""
                    <div class="event">
                        <p><strong>类型:</strong> {event.event_type.value}</p>
                        <p><strong>IP:</strong> {event.ip_address or 'N/A'}</p>
                        <p><strong>用户:</strong> {event.username or 'N/A'}</p>
                        <p><strong>时间:</strong> {event.datetime}</p>
                    </div>
            """

        html += """
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _get_slack_title(self, alert: "SecurityAlert") -> str:
        """获取Slack标题"""
        return f"{self._get_emoji(alert.severity)} {alert.message}"

    def _get_dingtalk_markdown(self, alert: "SecurityAlert") -> str:
        """获取钉钉Markdown内容"""
        self._get_color(alert.severity)
        markdown = f"""### {self._get_emoji(alert.severity)} {alert.severity.value.upper()} 告警

**类型:** {alert.event_type.value}
**消息:** {alert.message}
**事件数:** {alert.event_count}
**时间:** {alert.datetime}

---

**事件详情:**
"""

        for event in alert.events[:5]:
            markdown += f"""
> **类型:** {event.event_type.value}
> **IP:** {event.ip_address or 'N/A'}
> **用户:** {event.username or 'N/A'}
> **时间:** {event.datetime}

---
"""

        return markdown

    def _get_wework_markdown(self, alert: "SecurityAlert") -> str:
        """获取企业微信Markdown内容"""
        return self._get_dingtalk_markdown(alert)

    def _get_color(self, severity: SecurityEventSeverity) -> str:
        """获取颜色"""
        colors = {
            "critical": "#FF0000",  # 红色
            "high": "#FF6600",  # 橙色
            "medium": "#FFCC00",  # 黄色
            "low": "#00CC66",  # 绿色
        }
        return colors.get(severity.value, "#999999")

    def _get_emoji(self, severity: SecurityEventSeverity) -> str:
        """获取表情符号"""
        emojis = {
            "critical": "🚨",
            "high": "⚠️",
            "medium": "⚡",
            "low": "ℹ️",
        }
        return emojis.get(severity.value, "⚠️")

    def _get_available_channels(self) -> List[NotificationChannel]:
        """获取可用的通知渠道"""
        channels = []

        if self.config.smtp_host and self.config.email_recipients:
            channels.append(NotificationChannel.EMAIL)
        if self.config.slack_webhook_url:
            channels.append(NotificationChannel.SLACK)
        if self.config.dingtalk_webhook_url:
            channels.append(NotificationChannel.DINGTALK)
        if self.config.wework_webhook_url:
            channels.append(NotificationChannel.WEWORK)
        if self.config.webhook_url:
            channels.append(NotificationChannel.WEBHOOK)

        return channels

    async def close(self):
        """关闭HTTP客户端"""
        await self.http_client.aclose()


# 全局告警通知器实例
alert_notifier = SecurityAlertNotifier()


def send_security_alert(
    alert: "SecurityAlert", channels: Optional[List[NotificationChannel]] = None
) -> bool:
    """
    发送安全告警的便捷函数

    Args:
        alert: 安全告警
        channels: 通知渠道列表

    Returns:
        是否发送成功

    Example:
    -------
    ```python
    from .security_monitoring import (
        SecurityAlert, SecurityEventType, SecurityEventSeverity,
        create_security_alert
    )

    from .alert_notifier import send_security_alert

    # 创建告警
    alert = SecurityAlert(
        alert_id="alert_123",
        event_type=SecurityEventType.BRUTE_FORCE_DETECTED,
        severity=SecurityEventSeverity.HIGH,
        message="Brute force attack detected",
        events=[...],
    )

    # 发送通知
    await send_security_alert(alert)
    ```
    """
    import asyncio

    return asyncio.run(alert_notifier.send_alert(alert, channels))


__all__ = [
    "NotificationChannel",
    "NotificationConfig",
    "SecurityAlertNotifier",
    "alert_notifier",
    "send_security_alert",
]
