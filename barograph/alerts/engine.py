"""Alert engine: evaluates rules against forecast grids and fires notifications."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
from loguru import logger

from barograph.alerts.rules import AlertRule
from barograph.core.models import Coordinate, GriddedField, ThresholdAlert, Variable
from barograph.core.temporal import utcnow


class AlertEngine:
    """Evaluate threshold rules against forecast grids and emit alerts."""

    def __init__(
        self,
        cooldown_minutes: int = 60,
        notification_channels: list[str] | None = None,
        webhook_urls: list[str] | None = None,
    ):
        self.cooldown_minutes = cooldown_minutes
        self.notification_channels = notification_channels or ["log"]
        self.webhook_urls = webhook_urls or []
        self.rules: list[AlertRule] = []
        self._last_emitted: dict[str, datetime] = {}
        self._alerts_log: list[ThresholdAlert] = []

    def add_rule(self, rule: AlertRule) -> None:
        self.rules.append(rule)

    def add_rules(self, rules: list[AlertRule]) -> None:
        self.rules.extend(rules)

    def load_rules(self, path: str | Path) -> None:
        """Load rules from a YAML file."""
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f)

        rules = data.get("rules", [])
        loaded = [AlertRule.from_dict(r) for r in rules]
        self.add_rules(loaded)

    def evaluate_field(
        self,
        field: GriddedField,
        lat_range: tuple[float, float] | None = None,
        lon_range: tuple[float, float] | None = None,
    ) -> list[ThresholdAlert]:
        """Evaluate all rules against every cell of a gridded field."""
        alerts = []

        for rule in self.rules:
            if rule.variable != field.variable:
                continue

            data = field.data
            ny, nx = data.shape[-2:]
            for i in range(ny):
                lat = float(field.lats[i])
                if lat_range and not (lat_range[0] <= lat <= lat_range[1]):
                    continue
                for j in range(nx):
                    lon = float(field.lons[j])
                    if lon_range and not (lon_range[0] <= lon <= lon_range[1]):
                        continue

                    value = float(data[..., i, j])
                    if np.isnan(value):
                        continue
                    if rule.region and not self._in_region(lat, lon, rule.region):
                        continue
                    if not rule.evaluate(value):
                        continue

                    alert = ThresholdAlert(
                        variable=field.variable,
                        threshold=rule.threshold,
                        operator=rule.operator.value,
                        location=Coordinate(latitude=lat, longitude=lon),
                        trigger_time=utcnow(),
                        forecast_time=field.valid_time,
                        value=value,
                        severity=rule.severity.value,
                        message=rule.format_message(value, lat, lon),
                        meta={"rule": rule.name, "source": field.source.value},
                    )

                    if self._should_emit(alert):
                        self._emitted(alert)
                        alerts.append(alert)

        return alerts

    def evaluate_point(
        self,
        lat: float,
        lon: float,
        value: float,
        variable: Variable,
        valid_time: datetime,
    ) -> list[ThresholdAlert]:
        """Evaluate rules for a single station point value."""
        alerts = []
        for rule in self.rules:
            if rule.variable != variable:
                continue
            if not rule.evaluate(value):
                continue

            alert = ThresholdAlert(
                variable=variable,
                threshold=rule.threshold,
                operator=rule.operator.value,
                location=Coordinate(latitude=lat, longitude=lon),
                trigger_time=utcnow(),
                forecast_time=valid_time,
                value=float(value),
                severity=rule.severity.value,
                message=rule.format_message(float(value), lat, lon),
                meta={"rule": rule.name},
            )

            if self._should_emit(alert):
                self._emitted(alert)
                alerts.append(alert)

        return alerts

    def evaluate_masked(
        self,
        field: GriddedField,
        mask: np.ndarray,
    ) -> list[ThresholdAlert]:
        """Evaluate rules but only at cells where mask is True."""
        alerts = []
        for rule in self.rules:
            if rule.variable != field.variable:
                continue
            data = field.data
            ny, nx = data.shape[-2:]
            for i in range(ny):
                for j in range(nx):
                    if not mask[..., i, j]:
                        continue
                    value = float(data[..., i, j])
                    if np.isnan(value) or not rule.evaluate(value):
                        continue
                    alert = ThresholdAlert(
                        variable=field.variable,
                        threshold=rule.threshold,
                        operator=rule.operator.value,
                        location=Coordinate(field.lats[i], field.lons[j]),
                        trigger_time=utcnow(),
                        forecast_time=field.valid_time,
                        value=value,
                        severity=rule.severity.value,
                        message=rule.format_message(value, field.lats[i], field.lons[j]),
                        meta={"rule": rule.name},
                    )
                    if self._should_emit(alert):
                        self._emitted(alert)
                        alerts.append(alert)
        return alerts

    def fire_alerts(self, alerts: list[ThresholdAlert]) -> None:
        """Send notifications for the given alerts."""
        for alert in alerts:
            self._notify(alert)

    def _in_region(
        self, lat: float, lon: float, region: list[tuple[float, float]]
    ) -> bool:
        try:
            import matplotlib.path as mpltPath
        except ImportError:
            # fallback: simple bounding box
            lats = [p[0] for p in region]
            lons = [p[1] for p in region]
            return min(lats) <= lat <= max(lats) and min(lons) <= lon <= max(lons)

        polygon = mpltPath.Path(region)
        return bool(polygon.contains_point((lon, lat)))

    def _should_emit(self, alert: ThresholdAlert) -> bool:
        key = f"{alert.variable.value}|{alert.meta.get('rule', '')}|"
        key += f"{alert.location.latitude:.3f}|{alert.location.longitude:.3f}"
        last = self._last_emitted.get(key)
        if last is None:
            return True
        return (alert.trigger_time - last).total_seconds() / 60 >= self.cooldown_minutes

    def _emitted(self, alert: ThresholdAlert) -> None:
        key = f"{alert.variable.value}|{alert.meta.get('rule', '')}|"
        key += f"{alert.location.latitude:.3f}|{alert.location.longitude:.3f}"
        self._last_emitted[key] = alert.trigger_time
        self._alerts_log.append(alert)
        self._notify(alert)

    def _notify(self, alert: ThresholdAlert) -> None:
        if "log" in self.notification_channels:
            logger.warning(f"ALERT[{alert.severity}]: {alert.message}")

        if "stdout" in self.notification_channels:
            print(f"[ALERT {alert.severity}] {alert.message}")

        if self.webhook_urls:
            for url in self.webhook_urls:
                self._send_webhook(url, alert)

    def _send_webhook(self, url: str, alert: ThresholdAlert) -> None:
        try:
            import json
            import urllib.request

            payload = json.dumps({
                "variable": alert.variable.value,
                "threshold": alert.threshold,
                "operator": alert.operator,
                "value": alert.value,
                "lat": alert.location.latitude,
                "lon": alert.location.longitude,
                "severity": alert.severity,
                "message": alert.message,
                "time": alert.trigger_time.isoformat(),
            }).encode("utf-8")

            req = urllib.request.Request(
                url, data=payload, headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send webhook to {url}: {e}")

    @property
    def alert_history(self) -> list[ThresholdAlert]:
        return list(self._alerts_log)

    def save_history(self, path: str | Path) -> None:
        """Persist alert history to a JSON file."""
        import json

        records = [
            {
                "variable": a.variable.value,
                "threshold": a.threshold,
                "operator": a.operator,
                "value": a.value,
                "lat": a.location.latitude,
                "lon": a.location.longitude,
                "severity": a.severity,
                "message": a.message,
                "trigger_time": a.trigger_time.isoformat(),
                "forecast_time": a.forecast_time.isoformat(),
                "meta": a.meta,
            }
            for a in self._alerts_log
        ]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(records, f, indent=2)
