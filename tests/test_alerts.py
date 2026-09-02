"""Unit tests for alert engine."""

from datetime import datetime

import numpy as np

from barograph.alerts import AlertEngine
from barograph.alerts.rules import AlertRule, Operator, Severity
from barograph.core.models import GriddedField, ModelSource, Variable


def make_field(
    values: np.ndarray,
    variable: Variable = Variable.PRECIPITATION,
) -> GriddedField:
    lats = np.linspace(-25, -20, values.shape[0])
    lons = np.linspace(-50, -45, values.shape[1])
    t = datetime(2026, 1, 1, 12)
    return GriddedField(
        data=values,
        lats=lats,
        lons=lons,
        variable=variable,
        source=ModelSource.GFS,
        valid_time=t,
        init_time=t,
    )


def test_alert_rule_evaluate():
    rule = AlertRule(
        variable=Variable.PRECIPITATION,
        threshold=50.0,
        operator=Operator.GREATER_OR_EQUAL,
    )
    assert rule.evaluate(60.0)
    assert rule.evaluate(50.0)
    assert not rule.evaluate(49.9)


def test_alert_engine_triggers():
    field = make_field(np.array([
        [10.0, 20.0, 30.0],
        [40.0, 60.0, 90.0],
    ]))

    engine = AlertEngine(cooldown_minutes=0, notification_channels=[])
    rule = AlertRule(
        variable=Variable.PRECIPITATION,
        threshold=50.0,
        operator=Operator.GREATER_OR_EQUAL,
    )
    engine.add_rule(rule)
    alerts = engine.evaluate_field(field)
    assert len(alerts) == 2


def test_alert_engine_no_trigger():
    field = make_field(np.array([
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
    ]))

    engine = AlertEngine(notification_channels=[])
    rule = AlertRule(
        variable=Variable.PRECIPITATION,
        threshold=50.0,
        operator=Operator.GREATER_OR_EQUAL,
    )
    engine.add_rule(rule)
    alerts = engine.evaluate_field(field)
    assert len(alerts) == 0


def test_alert_engine_variable_filter():
    field = make_field(np.array([[100.0]]), variable=Variable.TEMPERATURE)
    engine = AlertEngine(notification_channels=[])
    rule = AlertRule(
        variable=Variable.PRECIPITATION,
        threshold=50.0,
        operator=Operator.GREATER_OR_EQUAL,
    )
    engine.add_rule(rule)
    alerts = engine.evaluate_field(field)
    assert len(alerts) == 0


def test_alert_cooldown():
    field = make_field(np.array([[500.0]]))
    engine = AlertEngine(cooldown_minutes=60, notification_channels=[])
    rule = AlertRule(
        variable=Variable.PRECIPITATION,
        threshold=50.0,
        operator=Operator.GREATER_OR_EQUAL,
    )
    engine.add_rule(rule)

    a1 = engine.evaluate_field(field)
    a2 = engine.evaluate_field(field)
    assert len(a1) == 1
    assert len(a2) == 0


def test_alert_from_dict():
    data = {
        "variable": "precipitation",
        "threshold": 25.0,
        "operator": "gt",
        "severity": "warning",
    }
    rule = AlertRule.from_dict(data)
    assert rule.variable == Variable.PRECIPITATION
    assert rule.threshold == 25.0
    assert rule.operator == Operator.GREATER_THAN
    assert rule.severity == Severity.WARNING
