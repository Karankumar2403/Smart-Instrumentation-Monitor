"""
Smart Process Instrumentation & Fault Diagnosis System
Module: signal_processing.py

Handles standard 4-20 mA current loop conversion, live zero validation,
under/over-range detection, open-circuit identification, and input sanitization.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Optional, Tuple


class SignalStatus(str, Enum):
    """Enumeration of electrical signal health states for 4-20 mA loops."""
    NORMAL = "NORMAL"
    UNDER_RANGE = "UNDER_RANGE"
    OVER_RANGE = "OVER_RANGE"
    OPEN_CIRCUIT = "OPEN_CIRCUIT"
    SENSOR_FAILURE_HIGH = "SENSOR_FAILURE_HIGH"
    INVALID = "INVALID"


@dataclass
class SignalConfig:
    """Configuration parameters for a 4-20 mA instrumentation channel."""
    tag: str
    description: str
    lrv: float  # Lower Range Value in Engineering Units
    urv: float  # Upper Range Value in Engineering Units
    units: str  # e.g., '°C', 'bar', 'm³/h'
    open_circuit_threshold_ma: float = 3.6    # Below this indicates open circuit/wire break (NAMUR NE 43)
    under_range_threshold_ma: float = 3.8     # Between 3.6 and 3.8 mA indicates under-range
    over_range_threshold_ma: float = 20.5     # Between 20.5 and 21.0 mA indicates over-range
    sensor_failure_high_ma: float = 21.0      # Above 21.0 mA indicates transmitter failure/short


@dataclass
class SignalResult:
    """Output data structure for a processed analog current signal."""
    tag: str
    raw_current_ma: Optional[float]
    process_value: Optional[float]
    status: SignalStatus
    health_label: str
    is_valid_pv: bool
    diagnostic_message: str


def validate_signal_config(config: SignalConfig) -> Tuple[bool, str]:
    """
    Validates configuration parameters for a transmitter channel.

    Rules:
    - Tag must be a non-empty string.
    - LRV and URV must be finite numbers.
    - URV must not equal LRV (span cannot be zero).
    - Current thresholds must follow logical ordering:
      0 < open_circuit <= under_range < 20.0 <= over_range <= sensor_failure_high
    """
    if not config.tag or not isinstance(config.tag, str) or not config.tag.strip():
        return False, "Instrument tag must be a non-empty string."

    if not (math.isfinite(config.lrv) and math.isfinite(config.urv)):
        return False, "Range limits (LRV, URV) must be finite numeric values."

    if math.isclose(config.lrv, config.urv):
        return False, f"Span cannot be zero (LRV={config.lrv}, URV={config.urv})."

    if not (0.0 < config.open_circuit_threshold_ma <= config.under_range_threshold_ma < 20.0):
        return False, "Invalid lower current thresholds ordering."

    if not (20.0 <= config.over_range_threshold_ma <= config.sensor_failure_high_ma):
        return False, "Invalid upper current thresholds ordering."

    return True, "Configuration is valid."


def current_to_engineering_value(current_ma: float, lrv: float, urv: float) -> float:
    """
    Standard linear scaling equation for 4-20 mA instrumentation loops:

    Engineering Value = LRV + ((Measured Current - 4.0) / 16.0) * (URV - LRV)

    Parameters:
        current_ma: Measured loop current in milliamps (mA).
        lrv: Lower Range Value at 4.0 mA.
        urv: Upper Range Value at 20.0 mA.

    Returns:
        Converted process value in engineering units.
    """
    if not math.isfinite(current_ma):
        raise ValueError(f"Non-finite current value provided: {current_ma}")
    if math.isclose(lrv, urv):
        raise ValueError(f"Span cannot be zero: LRV={lrv}, URV={urv}")

    fraction = (current_ma - 4.0) / 16.0
    return lrv + fraction * (urv - lrv)


def engineering_value_to_current(pv: float, lrv: float, urv: float) -> float:
    """
    Inverse conversion from Engineering Value to current loop (mA):

    Current (mA) = 4.0 + ((PV - LRV) / (URV - LRV)) * 16.0
    """
    if not math.isfinite(pv):
        raise ValueError(f"Non-finite process value provided: {pv}")
    if math.isclose(lrv, urv):
        raise ValueError(f"Span cannot be zero: LRV={lrv}, URV={urv}")

    fraction = (pv - lrv) / (urv - lrv)
    return 4.0 + fraction * 16.0


def evaluate_signal_health(current_ma: Any, config: SignalConfig) -> Tuple[SignalStatus, str]:
    """
    Evaluates the electrical loop health of the 4-20 mA current signal against NAMUR NE 43 bounds.

    Returns:
        (SignalStatus, diagnostic_explanation)
    """
    # 1. Check for missing, None, or non-numeric types
    if current_ma is None:
        return SignalStatus.INVALID, "Telemetry value is missing (None/Null input)."

    try:
        val = float(current_ma)
    except (TypeError, ValueError):
        return SignalStatus.INVALID, f"Signal could not be parsed as a float: {current_ma}"

    if not math.isfinite(val):
        return SignalStatus.INVALID, f"Signal is non-finite (NaN or Inf): {val}"

    # 2. Check for Open-Circuit / Wire Break (< open_circuit_threshold_ma, typically < 3.6 mA)
    if val < config.open_circuit_threshold_ma:
        return (
            SignalStatus.OPEN_CIRCUIT,
            f"Loop current {val:.2f} mA is below {config.open_circuit_threshold_ma:.2f} mA: "
            "possible open circuit, wire break, disconnected loop, or transmitter power loss."
        )

    # 3. Check for Under-Range (3.6 mA <= current < 3.8 mA)
    if val < config.under_range_threshold_ma:
        return (
            SignalStatus.UNDER_RANGE,
            f"Loop current {val:.2f} mA is between {config.open_circuit_threshold_ma:.2f} mA "
            f"and {config.under_range_threshold_ma:.2f} mA: signal under-range (zero drift or negative process excursion)."
        )

    # 4. Check for Sensor Failure High (> sensor_failure_high_ma, typically > 21.0 mA)
    if val > config.sensor_failure_high_ma:
        return (
            SignalStatus.SENSOR_FAILURE_HIGH,
            f"Loop current {val:.2f} mA exceeds failure threshold {config.sensor_failure_high_ma:.2f} mA: "
            "transducer hardware failure, loop short-circuit, or burnout mode active."
        )

    # 5. Check for Over-Range (20.5 mA < current <= 21.0 mA)
    if val > config.over_range_threshold_ma:
        return (
            SignalStatus.OVER_RANGE,
            f"Loop current {val:.2f} mA is between {config.over_range_threshold_ma:.2f} mA "
            f"and {config.sensor_failure_high_ma:.2f} mA: signal over-range (sensor saturated or process above span)."
        )

    # 6. Normal live 4-20 mA band (3.8 mA <= current <= 20.5 mA)
    return (
        SignalStatus.NORMAL,
        f"Loop current {val:.2f} mA is within valid operational envelope (3.80 - 20.50 mA)."
    )


def process_instrument_signal(current_ma: Any, config: SignalConfig) -> SignalResult:
    """
    Complete signal evaluation pipeline:
    - Assesses electrical loop integrity.
    - If valid, calculates engineering value.
    - If invalid, flags process value as unreliable to prevent false control actions.
    """
    valid_cfg, cfg_err = validate_signal_config(config)
    if not valid_cfg:
        return SignalResult(
            tag=getattr(config, "tag", "UNKNOWN"),
            raw_current_ma=None,
            process_value=None,
            status=SignalStatus.INVALID,
            health_label="CONFIG_ERROR",
            is_valid_pv=False,
            diagnostic_message=f"Configuration error: {cfg_err}"
        )

    status, diag = evaluate_signal_health(current_ma, config)

    # If open-circuit or invalid, PV must NOT be considered valid
    if status in (SignalStatus.OPEN_CIRCUIT, SignalStatus.INVALID, SignalStatus.SENSOR_FAILURE_HIGH):
        return SignalResult(
            tag=config.tag,
            raw_current_ma=float(current_ma) if (current_ma is not None and isinstance(current_ma, (int, float)) and math.isfinite(current_ma)) else None,
            process_value=None,
            status=status,
            health_label="FAULT",
            is_valid_pv=False,
            diagnostic_message=diag
        )

    # Under-range and Over-range are still electrically measurable, but flagged as abnormal
    current_val = float(current_ma)
    pv = current_to_engineering_value(current_val, config.lrv, config.urv)

    health_label = "NORMAL" if status == SignalStatus.NORMAL else "WARNING"

    return SignalResult(
        tag=config.tag,
        raw_current_ma=current_val,
        process_value=pv,
        status=status,
        health_label=health_label,
        is_valid_pv=True,
        diagnostic_message=diag
    )
