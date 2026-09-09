"""Verification dashboard: aggregate metrics and export to HTML/JSON."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class VerificationDashboard:
    """Aggregate a set of metric results and render a report.

    ``metric_samples`` maps a label (e.g. "temperature_lead12h") to a dict of
    metric name -> value, and optionally a series of per-event scores.
    """

    title: str = "Barograph Verification Dashboard"
    generated_at: datetime = field(default_factory=lambda: datetime.now())
    metric_samples: dict[str, dict[str, float]] = field(default_factory=dict)
    series: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def add_metrics(self, label: str, metrics: dict[str, float]) -> None:
        self.metric_samples[label] = dict(metrics)

    def add_series(self, label: str, series: dict[str, list[float]]) -> None:
        self.series[label] = {k: list(v) for k, v in series.items()}

    def combined(self) -> dict[str, dict[str, float]]:
        """Average duplicate metric labels across samples."""
        from collections import defaultdict

        sums: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for label, metrics in self.metric_samples.items():
            for metric, value in metrics.items():
                if value is None or (isinstance(value, float) and np.isnan(value)):
                    continue
                sums[label][metric] += float(value)
                counts[label][metric] += 1
        out: dict[str, dict[str, float]] = {}
        for label, metric_map in sums.items():
            out[label] = {
                m: sums[label][m] / counts[label][m] for m in metric_map
            }
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "generated_at": self.generated_at.isoformat(),
            "meta": self.meta,
            "metrics": self.metric_samples,
            "combined": self.combined(),
            "series": self.series,
        }

    def to_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    def to_html(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        combined = self.combined()
        for label in combined:
            metrics = combined[label]
            cells = "".join(
                f"<td>{html.escape(label)}</td>"
                f"<td>{html.escape(m)}</td><td>{v:.4f}</td>"
                for m, v in metrics.items()
            )
            if not metrics:
                cells = f"<td>{html.escape(label)}</td><td colspan='2'>-</td>"
            rows.append(f"<tr>{cells}</tr>")

        series_html = ""
        for label, series in self.series.items():
            for metric, values in series.items():
                values_str = ", ".join(f"{v:.2f}" for v in values)
                series_html += (
                    f"<h3>{html.escape(label)} :: {html.escape(metric)}</h3>"
                    f"<code>{html.escape(values_str)}</code>"
                )

        doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(self.title)}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem;
         color: #222; background: #fafafa; }}
  h1 {{ border-bottom: 2px solid #1976d2; padding-bottom: .5rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; background:#fff; }}
  th, td {{ border: 1px solid #ddd; padding: .5rem; text-align: left; }}
  th {{ background: #1976d2; color: #fff; }}
  tr:nth-child(even) {{ background: #f2f2f2; }}
  .badge {{ display: inline-block; padding: .25rem .75rem; border-radius: 4px;
           color:#fff; background:#1976d2; }}
  code {{ background: #eee; padding: .25rem .5rem; border-radius: 3px; }}
</style>
</head>
<body>
<h1>{html.escape(self.title)}</h1>
<p class="badge">Generated {html.escape(self.generated_at.isoformat())}</p>
<h2>Aggregate metrics</h2>
<table>
<tr><th>Case</th><th>Metric</th><th>Value</th></tr>
{''.join(rows) if rows else '<tr><td colspan="3">No metrics recorded.</td></tr>'}
</table>
<h2>Time series</h2>
{series_html if series_html else '<p>No series recorded.</p>'}
<footer><p>Barograph verification dashboard ({len(combined)} case(s)).</p></footer>
</body>
</html>"""
        path.write_text(doc, encoding="utf-8")
        return path

    @staticmethod
    def load_json(path: str | Path) -> VerificationDashboard:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return VerificationDashboard(
            title=data.get("title", "Verification Dashboard"),
            generated_at=datetime.fromisoformat(data.get("generated_at", "1970-01-01")),
            metric_samples=data.get("metrics", {}),
            series=data.get("series", {}),
            meta=data.get("meta", {}),
        )
