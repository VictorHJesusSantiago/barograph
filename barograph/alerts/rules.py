"""Alert rule definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from barograph.core.models import Variable


class Operator(Enum):
    GREATER_THAN = "gt"
    GREATER_OR_EQUAL = "ge"
    LESS_THAN = "lt"
    LESS_OR_EQUAL = "le"
    BETWEEN = "between"


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    SEVERE = "severe"
    EXTREME = "extreme"


@dataclass
class AlertRule:
    """A threshold-based alert rule."""

    variable: Variable
    threshold: float
    operator: Operator = Operator.GREATER_OR_EQUAL
    severity: Severity = Severity.WARNING
    name: str = ""
    lower_bound: float | None = None
    upper_bound: float | None = None
    region: list[tuple[float, float]] | None = None
    message_template: str = (
        "{variable} at ({lat:.2f}, {lon:.2f}) = {value:.2f} "
        "crossed threshold {threshold:.2f} ({operator})"
    )
    cooldown_minutes: int = 60
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.name:
            self.name = f"{self.variable}_{self.operator.value}_{self.threshold}"

    def evaluate(self, value: float) -> bool:
        """Test whether a single scalar value triggers the rule."""
        if self.operator == Operator.GREATER_THAN:
            return value > self.threshold
        elif self.operator == Operator.GREATER_OR_EQUAL:
            return value >= self.threshold
        elif self.operator == Operator.LESS_THAN:
            return value < self.threshold
        elif self.operator == Operator.LESS_OR_EQUAL:
            return value <= self.threshold
        elif self.operator == Operator.BETWEEN:
            if self.lower_bound is None or self.upper_bound is None:
                raise ValueError("BETWEEN operator requires lower_bound and upper_bound")
            return self.lower_bound <= value <= self.upper_bound
        else:
            raise ValueError(f"Unsupported operator: {self.operator}")

    def format_message(
        self,
        value: float,
        lat: float,
        lon: float,
    ) -> str:
        return self.message_template.format(
            variable=self.variable.value,
            value=value,
            threshold=self.threshold,
            operator=self.operator.value,
            lat=lat,
            lon=lon,
        )

    @classmethod
    def from_dict(cls, data: dict) -> AlertRule:
        """Create a rule from a config dict (YAML/JSON)."""
        variable = data["variable"]
        if isinstance(variable, Variable):
            var = variable
        else:
            var = Variable(variable)

        op = data.get("operator", "ge")
        op_enum = op if isinstance(op, Operator) else Operator(op)

        sev = data.get("severity", "warning")
        sev_enum = sev if isinstance(sev, Severity) else Severity(sev)

        return cls(
            variable=var,
            threshold=float(data["threshold"]),
            operator=op_enum,
            severity=sev_enum,
            name=data.get("name", ""),
            lower_bound=(
                float(data["lower_bound"]) if data.get("lower_bound") is not None else None
            ),
            upper_bound=(
                float(data["upper_bound"]) if data.get("upper_bound") is not None else None
            ),
            region=data.get("region"),
            message_template=data.get(
                "message_template",
                "{variable} at ({lat:.2f}, {lon:.2f}) = {value:.2f} "
                "crossed threshold {threshold:.2f} ({operator})",
            ),
            cooldown_minutes=int(data.get("cooldown_minutes", 60)),
            meta=data.get("meta", {}),
        )
