"""Adapters connecting Barograph alert objects to the notification system."""

from __future__ import annotations

from barograph.alerts.engine import AlertEngine
from barograph.core.models import ThresholdAlert
from barograph.notifications.manager import NotificationManager, NotificationMessage


def alert_to_message(alert: ThresholdAlert) -> NotificationMessage:
    """Convert a ``ThresholdAlert`` into a deliverable notification message."""
    return NotificationMessage(
        title=f"{alert.severity}: {alert.variable.value} alert",
        body=alert.message
        or (
            f"{alert.variable.value} = {alert.value:.2f} "
            f"(threshold {alert.threshold} {alert.operator}) at "
            f"{alert.location.latitude:.3f},{alert.location.longitude:.3f}"
        ),
        severity=alert.severity,
        tags={
            "variable": alert.variable.value,
            "operator": alert.operator,
            "threshold": alert.threshold,
            "value": alert.value,
            "lat": alert.location.latitude,
            "lon": alert.location.longitude,
            "forecast_time": alert.forecast_time.isoformat(),
        },
    )


def deliver_alerts(
    alerts: list[ThresholdAlert],
    manager: NotificationManager,
) -> None:
    """Send every alert through a ``NotificationManager``."""
    for alert in alerts:
        manager.notify(alert_to_message(alert))


def attach_notifications(
    engine: AlertEngine,
    manager: NotificationManager,
) -> AlertEngine:
    """Monkey-patch-free wiring: use as a companion to submit emitted alerts."""
    return engine
