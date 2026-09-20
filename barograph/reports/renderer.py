"""Report renderer: convert alerts, fields and metric summaries to text formats."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from barograph.core.models import GriddedField, ThresholdAlert
from barograph.raster.layer import RasterLayer


class ReportRenderer:
    """Serialize Barograph objects (fields, alerts, rasters) to plain formats."""

    @staticmethod
    def alerts_to_dicts(alerts: Iterable[ThresholdAlert]) -> list[dict[str, Any]]:
        return [
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
            for a in alerts
        ]

    @staticmethod
    def alerts_to_json(alerts: Iterable[ThresholdAlert], path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(ReportRenderer.alerts_to_dicts(alerts), indent=2),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def alerts_to_csv(alerts: Iterable[ThresholdAlert], path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "variable",
            "threshold",
            "operator",
            "value",
            "lat",
            "lon",
            "severity",
            "message",
            "trigger_time",
            "forecast_time",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in ReportRenderer.alerts_to_dicts(alerts):
                writer.writerow({k: row.get(k, "") for k in fields})
        return path

    @staticmethod
    def alerts_to_markdown(alerts: Iterable[ThresholdAlert]) -> str:
        lines = [
            "# Alerts",
            "",
            "| Severity | Variable | Value | Location | Message |",
            "|---|---|---|---|---|",
        ]
        for a in alerts:
            lines.append(
                f"| {a.severity} | {a.variable.value} | {a.value:.2f} | "
                f"{a.location.latitude:.2f},{a.location.longitude:.2f} | "
                f"{a.message} |"
            )
        return "\n".join(lines)

    @staticmethod
    def field_summary(field: GriddedField) -> str:
        data = field.data
        valid = data[np.isfinite(data)]
        return (
            f"{field.variable.value} ({field.source.value}) "
            f"shape={field.shape} mean={float(valid.mean()):.2f} "
            f"min={float(valid.min()):.2f} max={float(valid.max()):.2f} "
            f"valid={field.valid_time.isoformat()}"
        )

    @staticmethod
    def raster_to_geotiff_metadata(layer: RasterLayer) -> dict[str, Any]:
        """Return metadata useful for describing a raster in reports."""
        return {
            "name": layer.name,
            "shape": list(layer.shape),
            "nbands": layer.nbands,
            "crs": layer.crs.epsg,
            "extent": list(layer.extent),
            "units": layer.units,
            "summary": layer.summary(),
        }
