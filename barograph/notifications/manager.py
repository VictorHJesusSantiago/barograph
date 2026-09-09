"""Notification delivery: real HTTP webhooks, console/file sinks, retries.

Provides a ``NotificationManager`` that routes a structured message to
multiple channels (console, log file, generic HTTP webhook, and
Slack/Discord/Mattermost/Slack-compatible payloads) with exponential
back-off retries and delivery history.
"""

from __future__ import annotations

import json
import smtplib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class NotifyResult:
    """Outcome of delivering a message to a single channel."""

    channel: str
    delivered: bool
    attempts: int = 0
    error: str | None = None
    timestamp: float = 0.0
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationMessage:
    """A structured, serializable notification payload."""

    title: str
    body: str
    severity: str = "info"
    tags: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "body": self.body,
            "severity": self.severity,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotificationMessage:
        return cls(
            title=str(data.get("title", "")),
            body=str(data.get("body", "")),
            severity=str(data.get("severity", "info")),
            tags=dict(data.get("tags", {})),
        )


class NotificationManager:
    """Deliver notifications across multiple channels with retries.

    Supported channel names: ``"console"``, ``"log"``, ``"file"`` (needs
    ``file_path`` on the channel config), ``"webhook"`` (needs ``url``),
    ``"slack"``, ``"discord"``, ``"mattermost"`` and ``"email"``.
    """

    def __init__(
        self,
        channels: list[str] | None = None,
        webhook_url: str | None = None,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        timeout_seconds: float = 5.0,
        file_path: str | Path | None = None,
        http_transport: Callable[..., bool] | None = None,
    ):
        self.channels = channels or ["console"]
        self.webhook_url = webhook_url
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout_seconds = timeout_seconds
        self.file_path = Path(file_path) if file_path else None
        self._http_transport = http_transport  # injectable for tests
        self._history: list[NotifyResult] = []
        self._email_config: dict[str, Any] = {}

    @property
    def history(self) -> list[NotifyResult]:
        return list(self._history)

    def notify(self, message: NotificationMessage) -> list[NotifyResult]:
        results = []
        payload = message.to_dict()
        for channel in self.channels:
            try:
                result = self._dispatch(channel, payload)
            except Exception as exc:  # noqa: BLE001 - deliver errors are captured
                result = NotifyResult(channel=channel, delivered=False, error=str(exc))
            self._history.append(result)
            results.append(result)
        return results

    def _dispatch(self, channel: str, payload: dict[str, Any]) -> NotifyResult:
        if channel == "console":
            return self._console(payload)
        if channel == "log":
            return self._to_log(payload)
        if channel == "file":
            return self._to_file(payload)
        if channel in ("webhook", "slack", "discord", "mattermost"):
            return self._webhook_with_retry(channel, payload)
        if channel == "email":
            return self._email(payload)
        raise ValueError(f"Unknown notification channel: {channel}")

    def _console(self, payload: dict[str, Any]) -> NotifyResult:
        print(f"[{payload['severity']}] {payload['title']}: {payload['body']}")
        return NotifyResult(channel="console", delivered=True, timestamp=time.time())

    def _to_log(self, payload: dict[str, Any]) -> NotifyResult:
        level = {
            "critical": "ERROR", "warning": "WARNING", "info": "INFO",
        }.get(payload["severity"], "INFO")
        logger.log(level, f"{payload['title']}: {payload['body']}")
        return NotifyResult(channel="log", delivered=True, timestamp=time.time())

    def _to_file(self, payload: dict[str, Any]) -> NotifyResult:
        if self.file_path is None:
            raise ValueError("file channel requires a file_path")
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
        return NotifyResult(channel="file", delivered=True, timestamp=time.time(),
                            detail={"path": str(self.file_path)})

    def _payload_for(self, channel: str, payload: dict[str, Any]) -> dict[str, Any]:
        if channel == "slack":
            return {
                "text": f"*{payload['title']}* ({payload['severity']})\n{payload['body']}",
            }
        if channel == "discord":
            color = {"critical": 15548997, "warning": 16776960, "info": 3447003}.get(
                payload["severity"], 3447003
            )
            return {
                "embeds": [{
                    "title": payload["title"],
                    "description": payload["body"],
                    "color": color,
                    "fields": [{"name": k, "value": str(v), "inline": True}
                               for k, v in payload["tags"].items()],
                }]
            }
        if channel == "mattermost":
            return {"text": f"**{payload['title']}**\n{payload['body']}"}
        return payload

    def _webhook_with_retry(
        self, channel: str, payload: dict[str, Any]
    ) -> NotifyResult:
        url = self.webhook_url
        if channel == "webhook" and url is None:
            raise ValueError("webhook channel requires a webhook_url")
        body = self._payload_for(channel if channel != "webhook" else "generic", payload)

        attempts = 0
        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            attempts += 1
            try:
                self._http_post(url, body)  # type: ignore[arg-type]
                return NotifyResult(
                    channel=channel, delivered=True, attempts=attempts,
                    timestamp=time.time(), detail={"url": url},
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if attempt < self.max_retries:
                    time.sleep(self.backoff_base * (2**attempt))
        return NotifyResult(
            channel=channel, delivered=False, attempts=attempts,
            error=last_error, timestamp=time.time(), detail={"url": url},
        )

    def _http_post(self, url: str, body: dict[str, Any]) -> bool:
        if self._http_transport is not None:
            return self._http_transport(url, body)
        import urllib.request

        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:  # noqa: S310
            if 200 <= resp.status < 300:
                return True
            raise RuntimeError(f"HTTP {resp.status}")
        return False

    def configure_email(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        username: str | None = None,
        password: str | None = None,
        sender: str | None = None,
        use_tls: bool = True,
    ) -> None:
        self._email_config = {
            "smtp_host": smtp_host, "smtp_port": smtp_port, "username": username,
            "password": password, "sender": sender, "use_tls": use_tls,
        }

    def _email(self, payload: dict[str, Any]) -> NotifyResult:
        cfg = self._email_config
        recipients = [r for r in payload.get("tags", {}).get("recipients", [])]
        if not cfg or not recipients:
            raise ValueError("email channel requires configure_email() and recipients")
        msg = EmailMessage()
        msg["From"] = cfg.get("sender") or cfg.get("username")
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = f"[{payload['severity']}] {payload['title']}"
        msg.set_content(payload["body"])

        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
            if cfg.get("use_tls"):
                server.starttls()
            if cfg.get("username"):
                server.login(cfg["username"], cfg["password"] or "")
            server.send_message(msg)
        return NotifyResult(channel="email", delivered=True, timestamp=time.time())

    def delivery_metrics(self) -> dict[str, Any]:
        delivered = sum(1 for r in self._history if r.delivered)
        total = len(self._history)
        return {
            "sent": total,
            "delivered": delivered,
            "failed": total - delivered,
            "success_rate": (delivered / total) if total else 1.0,
        }
