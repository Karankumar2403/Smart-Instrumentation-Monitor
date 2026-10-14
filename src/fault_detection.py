"""
Smart Process Instrumentation & Fault Diagnosis System
Module: fault_detection.py

Transparent, rule-based diagnostic engine for industrial instrumentation.
Distinguishes electrical loop issues (wire break, out-of-range mA, stale signal)
from physical process deviations (high temperature, low pressure, noisy dynamics).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from src.signal_processing import SignalConfig, SignalResult, SignalStatus


class FaultSeverity(str, Enum):
    """Severity classification for instrumentation and process faults."""
    CRITICAL = "CRITICAL"    # Immediate loss of measurement or severe safety hazard
    WARNING = "WARNING"      # Abnormal measurement, drift, or threshold excursion
    ADVISORY = "ADVISORY"    # Signal jitter, minor noise, or operational caution
    NORMAL = "NORMAL"        # Healthy signal and process within safe limits


@dataclass
class DiagnosticRecord:
    """Detailed fault diagnosis record providing operator investigation guidance."""
    fault_name: str
    instrument_tag: str
    severity: FaultSeverity
    timestamp: str
    observed_condition: str
    possible_causes: List[str]
    suggested_inspection_steps: List[str]
    current_status: str

    def to_dict(self) -> Dict:
        return {
            "fault_name": self.fault_name,
            "instrument_tag": self.instrument_tag,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "observed_condition": self.observed_condition,
            "possible_causes": "; ".join(self.possible_causes),
            "suggested_inspection_steps": " | ".join(self.suggested_inspection_steps),
            "current_status": self.current_status,
        }


def diagnose_instrument(
    signal_result: SignalResult,
    config: SignalConfig,
    is_stale: bool = False,
    stale_duration_sec: float = 0.0,
    is_noisy: bool = False,
    noise_std: float = 0.0,
    drift_offset: float = 0.0,
    timestamp_str: Optional[str] = None
) -> DiagnosticRecord:
    """
    Evaluates signal result and telemetry metadata to generate transparent,
    rule-based diagnostic guidance for field technicians and operators.

    Note: Recommendations represent investigation guidance and heuristic troubleshooting,
    not definitive proof of physical hardware failure.
    """
    now_str = timestamp_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Check for Missing / Invalid Telemetry
    if signal_result.status == SignalStatus.INVALID:
        return DiagnosticRecord(
            fault_name="Invalid or Missing Measurement",
            instrument_tag=config.tag,
            severity=FaultSeverity.CRITICAL,
            timestamp=now_str,
            observed_condition=f"Input signal is non-numeric, null, or corrupted: {signal_result.diagnostic_message}",
            possible_causes=[
                "Modbus/OPC communication frame corruption",
                "Analog-to-Digital Converter (ADC) driver failure",
                "Uninitialized channel buffer or fieldbus bus fault"
            ],
            suggested_inspection_steps=[
                "Verify communication gateway diagnostics and fieldbus link status.",
                "Inspect I/O card channel diagnostic LEDs on the PLC/DCS rack.",
                "Confirm software polling routine handles null values safely without crashing."
            ],
            current_status="ACTIVE_FAULT"
        )

    # 2. Check for Open-Circuit / Wire Break (< 3.6 mA)
    if signal_result.status == SignalStatus.OPEN_CIRCUIT:
        cur_str = f"{signal_result.raw_current_ma:.2f} mA" if signal_result.raw_current_ma is not None else "Unknown"
        return DiagnosticRecord(
            fault_name="Transmitter Open Circuit (Wire Break)",
            instrument_tag=config.tag,
            severity=FaultSeverity.CRITICAL,
            timestamp=now_str,
            observed_condition=f"Loop current is {cur_str}, below live-zero safety boundary ({config.open_circuit_threshold_ma:.2f} mA).",
            possible_causes=[
                "Physical cable cut, severed core, or loose terminal screw in junction box",
                "Loss of 24 VDC instrument loop power supply",
                "Blown barrier fuse in hazardous area intrinsic safety (IS) isolator",
                "Complete failure of internal transmitter electronics"
            ],
            suggested_inspection_steps=[
                "Inspect field junction box terminals and Marshalling cabinet screw contacts.",
                "Measure DC voltage across transmitter terminals (+ and -); expect > 12-24 VDC.",
                "Verify continuity of 2-wire copper loop with a calibrated multimeter (DMM).",
                "Check 24 VDC distribution fuse in power supply panel."
            ],
            current_status="ACTIVE_FAULT"
        )

    # 3. Check for Sensor Failure High (> 21.0 mA)
    if signal_result.status == SignalStatus.SENSOR_FAILURE_HIGH:
        cur_str = f"{signal_result.raw_current_ma:.2f} mA" if signal_result.raw_current_ma is not None else "Unknown"
        return DiagnosticRecord(
            fault_name="Transmitter Failure High / Burnout",
            instrument_tag=config.tag,
            severity=FaultSeverity.CRITICAL,
            timestamp=now_str,
            observed_condition=f"Loop current {cur_str} exceeds 21.00 mA (NAMUR NE 43 upscale burnout threshold).",
            possible_causes=[
                "Sensing element burnout (e.g. open RTD / thermocouple triggering high burnout)",
                "Transmitter amplifier short-circuit or surge damage",
                "Water ingress into transmitter terminal head or conduit fitting"
            ],
            suggested_inspection_steps=[
                "Check transmitter local display error codes (e.g. NAMUR NE 107 diagnostics).",
                "Test RTD/thermocouple element resistance directly with sensor disconnected.",
                "Inspect housing O-ring seal for moisture, corrosion, or condensation."
            ],
            current_status="ACTIVE_FAULT"
        )

    # 4. Check for Under-Range Current (3.6 mA <= current < 3.8 mA)
    if signal_result.status == SignalStatus.UNDER_RANGE:
        cur_str = f"{signal_result.raw_current_ma:.2f} mA" if signal_result.raw_current_ma is not None else "Unknown"
        return DiagnosticRecord(
            fault_name="Signal Under-Range Fault",
            instrument_tag=config.tag,
            severity=FaultSeverity.WARNING,
            timestamp=now_str,
            observed_condition=f"Current {cur_str} is below 3.80 mA but above wire-break threshold (3.60 mA).",
            possible_causes=[
                "Transmitter zero calibration drift (negative shift in calibration pot / digital DAC)",
                "Impulse line blockage causing reverse siphon or vacuum trap",
                "Process variable physically dipping slightly below calibrated LRV"
            ],
            suggested_inspection_steps=[
                "Perform zero-trim calibration using a handheld HART field communicator.",
                "Inspect impulse line piping, manifold valves, and purge ports for blockage or air pockets.",
                "Confirm if plant operating temperature/pressure truly dropped below range."
            ],
            current_status="ACTIVE_FAULT"
        )

    # 5. Check for Over-Range Current (20.5 mA < current <= 21.0 mA)
    if signal_result.status == SignalStatus.OVER_RANGE:
        cur_str = f"{signal_result.raw_current_ma:.2f} mA" if signal_result.raw_current_ma is not None else "Unknown"
        return DiagnosticRecord(
            fault_name="Signal Over-Range Fault",
            instrument_tag=config.tag,
            severity=FaultSeverity.WARNING,
            timestamp=now_str,
            observed_condition=f"Current {cur_str} is between 20.50 mA and 21.00 mA (transmitter saturation).",
            possible_causes=[
                "Physical process has exceeded calibrated Upper Range Value (URV)",
                "Transmitter span calibration error or positive calibration shift",
                "Diaphragm over-pressure deformation or scale accumulation"
            ],
            suggested_inspection_steps=[
                "Verify actual process conditions via local mechanical dial gauge or alternate instrument.",
                "Re-evaluate whether range configuration (URV) matches maximum operating envelope.",
                "Check transmitter span settings via HART communicator."
            ],
            current_status="ACTIVE_FAULT"
        )

    # 6. Check for Stale Measurement (frozen signal)
    if is_stale:
        return DiagnosticRecord(
            fault_name="Stale Measurement Detected",
            instrument_tag=config.tag,
            severity=FaultSeverity.WARNING,
            timestamp=now_str,
            observed_condition=f"Measurement value has remained completely static without variation for {stale_duration_sec:.1f} s.",
            possible_causes=[
                "Communication polling loop frozen or thread deadlock in telemetry adapter",
                "Smart transmitter frozen in internal watchdog routine",
                "Blocked sensing impulse line or mechanical sensor seizure"
            ],
            suggested_inspection_steps=[
                "Check telemetry gateway timestamps and network communication health.",
                "Verify transmitter local LCD display responds to live process variations.",
                "Blow down / flush impulse lines to clear mechanical debris or viscous plugging."
            ],
            current_status="ACTIVE_FAULT"
        )

    # 7. Check for Gradual Calibration Drift
    if abs(drift_offset) > 0.05:  # e.g., > 0.05 mA or significant deviation
        return DiagnosticRecord(
            fault_name="Gradual Sensor Drift",
            instrument_tag=config.tag,
            severity=FaultSeverity.WARNING,
            timestamp=now_str,
            observed_condition=f"Detected persistent systematic drift offset of {drift_offset:+.2f} mA from nominal baseline.",
            possible_causes=[
                "Aging sensing diaphragm or strain gauge relaxation",
                "Coating, fouling, or sludge buildup on sensor probe surface",
                "Degradation of internal reference resistor or RTD lead resistance change"
            ],
            suggested_inspection_steps=[
                "Schedule benchmark cross-comparison against a certified reference master gauge.",
                "Remove and clean transmitter sensor element / thermowell from deposits.",
                "Perform full 5-point calibration (0%, 25%, 50%, 75%, 100%) in the instrumentation lab."
            ],
            current_status="ACTIVE_FAULT"
        )

    # 8. Check for Excessive Noise / Jitter
    if is_noisy or noise_std > 0.5:
        return DiagnosticRecord(
            fault_name="Noisy Instrumentation Signal",
            instrument_tag=config.tag,
            severity=FaultSeverity.ADVISORY,
            timestamp=now_str,
            observed_condition=f"Signal exhibits elevated high-frequency jitter (std dev = {noise_std:.2f} mA).",
            possible_causes=[
                "Electromagnetic Interference (EMI) from nearby variable frequency drives (VFD) or motors",
                "Shield wire disconnected or improper single-point grounding at cabinet",
                "Flow turbulence, pump cavitation, or mechanical vibration transmitted to instrument"
            ],
            suggested_inspection_steps=[
                "Verify instrument cable shield drain wire is grounded at one end only (cabinet side).",
                "Ensure instrumentation signal cables are segregated from high-voltage motor cables.",
                "Enable internal digital damping (e.g. 1.0 - 2.0 s damping constant) via HART."
            ],
            current_status="ADVISORY"
        )

    # Healthy Normal Condition
    return DiagnosticRecord(
        fault_name="Normal Operation",
        instrument_tag=config.tag,
        severity=FaultSeverity.NORMAL,
        timestamp=now_str,
        observed_condition=f"Electrical signal {signal_result.raw_current_ma:.2f} mA and process measurement are nominal.",
        possible_causes=["None - instrument operating within normal design tolerances."],
        suggested_inspection_steps=["Continue routine scheduled preventive maintenance inspections."],
        current_status="NORMAL"
    )
