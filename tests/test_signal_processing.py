"""
Unit and boundary tests for signal_processing.py.
Covers 4-20 mA conversion, span validation, boundary limits, and NAMUR NE 43 bounds.
"""

import math
import pytest
from src.signal_processing import (
    SignalConfig,
    SignalStatus,
    current_to_engineering_value,
    engineering_value_to_current,
    evaluate_signal_health,
    process_instrument_signal,
    validate_signal_config
)


@pytest.fixture
def temp_config() -> SignalConfig:
    return SignalConfig(
        tag="TT-101",
        description="Temperature Transmitter",
        lrv=0.0,
        urv=150.0,
        units="°C"
    )


@pytest.fixture
def press_config() -> SignalConfig:
    return SignalConfig(
        tag="PT-101",
        description="Pressure Transmitter",
        lrv=0.0,
        urv=10.0,
        units="bar"
    )


def test_conversion_at_4ma(temp_config, press_config):
    """4 mA must correspond exactly to Lower Range Value (LRV)."""
    assert math.isclose(current_to_engineering_value(4.0, temp_config.lrv, temp_config.urv), 0.0)
    assert math.isclose(current_to_engineering_value(4.0, press_config.lrv, press_config.urv), 0.0)


def test_conversion_at_12ma(temp_config, press_config):
    """12 mA must correspond exactly to 50% midpoint of span."""
    assert math.isclose(current_to_engineering_value(12.0, temp_config.lrv, temp_config.urv), 75.0)
    assert math.isclose(current_to_engineering_value(12.0, press_config.lrv, press_config.urv), 5.0)


def test_conversion_at_20ma(temp_config, press_config):
    """20 mA must correspond exactly to Upper Range Value (URV)."""
    assert math.isclose(current_to_engineering_value(20.0, temp_config.lrv, temp_config.urv), 150.0)
    assert math.isclose(current_to_engineering_value(20.0, press_config.lrv, press_config.urv), 10.0)


def test_inverse_engineering_value_to_current(temp_config):
    """Verifies round-trip fidelity between PV and mA."""
    pv = 75.0
    current = engineering_value_to_current(pv, temp_config.lrv, temp_config.urv)
    assert math.isclose(current, 12.0)

    calculated_pv = current_to_engineering_value(current, temp_config.lrv, temp_config.urv)
    assert math.isclose(calculated_pv, pv)


def test_negative_range_span():
    """Verifies support for negative temperatures (e.g., -50 to +100 °C)."""
    lrv, urv = -50.0, 100.0
    assert math.isclose(current_to_engineering_value(4.0, lrv, urv), -50.0)
    assert math.isclose(current_to_engineering_value(12.0, lrv, urv), 25.0)
    assert math.isclose(current_to_engineering_value(20.0, lrv, urv), 100.0)


def test_invalid_measurement_range_zero_span():
    """Zero span (LRV == URV) must fail configuration validation and raise ValueError on conversion."""
    cfg = SignalConfig(tag="ERR-01", description="Zero Span", lrv=100.0, urv=100.0, units="bar")
    valid, msg = validate_signal_config(cfg)
    assert not valid
    assert "Span cannot be zero" in msg

    with pytest.raises(ValueError):
        current_to_engineering_value(12.0, 100.0, 100.0)


def test_non_finite_range_validation():
    """Infinite or NaN range limits must be rejected."""
    cfg = SignalConfig(tag="ERR-02", description="Inf Range", lrv=0.0, urv=float("inf"), units="°C")
    valid, msg = validate_signal_config(cfg)
    assert not valid

    cfg2 = SignalConfig(tag="ERR-03", description="NaN Range", lrv=float("nan"), urv=100.0, units="°C")
    valid2, msg2 = validate_signal_config(cfg2)
    assert not valid2


def test_open_circuit_detection(temp_config):
    """Current below 3.6 mA indicates open circuit / broken wire."""
    status, msg = evaluate_signal_health(0.0, temp_config)
    assert status == SignalStatus.OPEN_CIRCUIT
    assert "open circuit" in msg.lower()

    status_boundary, _ = evaluate_signal_health(3.59, temp_config)
    assert status_boundary == SignalStatus.OPEN_CIRCUIT

    result = process_instrument_signal(0.5, temp_config)
    assert result.status == SignalStatus.OPEN_CIRCUIT
    assert not result.is_valid_pv
    assert result.process_value is None


def test_under_range_detection(temp_config):
    """Current between 3.6 mA and 3.8 mA indicates under-range."""
    status, msg = evaluate_signal_health(3.70, temp_config)
    assert status == SignalStatus.UNDER_RANGE
    assert "under-range" in msg.lower()

    result = process_instrument_signal(3.70, temp_config)
    assert result.status == SignalStatus.UNDER_RANGE
    assert result.is_valid_pv
    assert result.health_label == "WARNING"


def test_over_range_detection(temp_config):
    """Current between 20.5 mA and 21.0 mA indicates over-range."""
    status, msg = evaluate_signal_health(20.75, temp_config)
    assert status == SignalStatus.OVER_RANGE
    assert "over-range" in msg.lower()

    result = process_instrument_signal(20.75, temp_config)
    assert result.status == SignalStatus.OVER_RANGE
    assert result.is_valid_pv
    assert result.health_label == "WARNING"


def test_sensor_failure_high_detection(temp_config):
    """Current exceeding 21.0 mA indicates upscale burnout / severe sensor fault."""
    status, msg = evaluate_signal_health(21.8, temp_config)
    assert status == SignalStatus.SENSOR_FAILURE_HIGH
    assert "burnout" in msg.lower() or "failure" in msg.lower()

    result = process_instrument_signal(21.8, temp_config)
    assert result.status == SignalStatus.SENSOR_FAILURE_HIGH
    assert not result.is_valid_pv
    assert result.process_value is None


@pytest.mark.parametrize("invalid_val", [None, "BAD_DATA", float("nan"), float("inf"), float("-inf")])
def test_invalid_signal_inputs(temp_config, invalid_val):
    """Non-numeric, None, or non-finite inputs must be safely handled without unhandled exceptions."""
    status, msg = evaluate_signal_health(invalid_val, temp_config)
    assert status == SignalStatus.INVALID

    result = process_instrument_signal(invalid_val, temp_config)
    assert result.status == SignalStatus.INVALID
    assert not result.is_valid_pv
    assert result.process_value is None
