"""
Smart Process Instrumentation & Fault Diagnosis System
Module: simulator.py

Generates realistic simulated 4-20 mA instrumentation loops for:
- Temperature Transmitter TT-101 (0 - 150 °C)
- Pressure Transmitter PT-101 (0 - 10.0 bar)

Implements 10 industrial fault injection scenarios, state tracking, and reproducible seeds.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import math
import random
from typing import Any, Dict, List, Optional
from src.alarm_manager import AlarmManager, AlarmThresholds
from src.fault_detection import DiagnosticRecord, diagnose_instrument
from src.signal_processing import (
    SignalConfig,
    SignalResult,
    SignalStatus,
    current_to_engineering_value,
    engineering_value_to_current,
    process_instrument_signal
)


class FaultScenario(str, Enum):
    NORMAL_OPERATION = "Normal Operation"
    LOW_PROCESS_VALUE = "Low Process Value"
    HIGH_PROCESS_VALUE = "High Process Value"
    OPEN_CIRCUIT = "Open-Circuit Transmitter Signal"
    UNDER_RANGE = "Under-Range Current Signal"
    OVER_RANGE = "Over-Range Current Signal"
    STALE_MEASUREMENT = "Stale Measurement"
    GRADUAL_SENSOR_DRIFT = "Gradual Sensor Drift"
    NOISY_SIGNAL = "Noisy Signal"
    INVALID_MISSING = "Invalid or Missing Measurement"


@dataclass
class InstrumentSnapshot:
    """Complete runtime state of a single instrument at a specific instant."""
    tag: str
    description: str
    timestamp: str
    raw_current_ma: Optional[float]
    process_value: Optional[float]
    units: str
    lrv: float
    urv: float
    signal_status: SignalStatus
    health_label: str
    is_valid_pv: bool
    diagnostic: DiagnosticRecord
    active_alarms: List[str]
    active_scenario: FaultScenario
    is_simulated: bool = True  # Explicit educational labeling


class ProcessSimulator:
    """
    Simulates industrial process instruments with realistic physical dynamics,
    sensor noise, and selectable fault injection modes.
    """
    def __init__(self, random_seed: Optional[int] = 42):
        if random_seed is not None:
            self._rng = random.Random(random_seed)
        else:
            self._rng = random.Random()

        # Default instrument definitions
        self.configs: Dict[str, SignalConfig] = {
            "TT-101": SignalConfig(
                tag="TT-101",
                description="Reactor Core Temperature Transmitter",
                lrv=0.0,
                urv=150.0,
                units="°C"
            ),
            "PT-101": SignalConfig(
                tag="PT-101",
                description="Separator Vessel Pressure Transmitter",
                lrv=0.0,
                urv=10.0,
                units="bar"
            )
        }

        # Default normal operating setpoints
        self.nominal_pvs: Dict[str, float] = {
            "TT-101": 65.0,   # Nominal 65.0 °C (equivalent to ~10.93 mA)
            "PT-101": 4.5     # Nominal 4.5 bar (equivalent to ~11.20 mA)
        }

        # Configurable process alarm limits (ISA-18.2 compliant)
        self.thresholds: Dict[str, AlarmThresholds] = {
            "TT-101": AlarmThresholds(low_low=20.0, low=35.0, high=95.0, high_high=120.0),
            "PT-101": AlarmThresholds(low_low=1.0, low=2.0, high=7.5, high_high=8.8)
        }

        # Simulation runtime state per instrument
        self.active_scenarios: Dict[str, FaultScenario] = {
            "TT-101": FaultScenario.NORMAL_OPERATION,
            "PT-101": FaultScenario.NORMAL_OPERATION
        }

        # Tracking state variables
        self._drift_accumulator: Dict[str, float] = {"TT-101": 0.0, "PT-101": 0.0}
        self._stale_counter: Dict[str, int] = {"TT-101": 0, "PT-101": 0}
        self._last_raw_current: Dict[str, Optional[float]] = {"TT-101": None, "PT-101": None}
        self._last_update_time: Dict[str, datetime] = {
            "TT-101": datetime.now(),
            "PT-101": datetime.now()
        }

        # Historical trend buffers (in-memory ring buffer)
        self.history: List[Dict[str, Any]] = []
        self.alarm_manager = AlarmManager()
        self.time_step_sec: float = 1.0
        self.current_sim_time: datetime = datetime.now()

    def set_scenario(self, tag: str, scenario: FaultScenario):
        """Switches the active fault scenario for an instrument."""
        if tag in self.active_scenarios:
            self.active_scenarios[tag] = scenario
            if scenario != FaultScenario.GRADUAL_SENSOR_DRIFT:
                self._drift_accumulator[tag] = 0.0
            if scenario != FaultScenario.STALE_MEASUREMENT:
                self._stale_counter[tag] = 0

    def reset_instrument(self, tag: str):
        """Restores an instrument to normal operating conditions."""
        self.set_scenario(tag, FaultScenario.NORMAL_OPERATION)
        self._drift_accumulator[tag] = 0.0
        self._stale_counter[tag] = 0

    def reset_all(self):
        """Restores all instruments to normal baseline state."""
        for tag in self.configs:
            self.reset_instrument(tag)

    def step(self) -> Dict[str, InstrumentSnapshot]:
        """
        Advances the simulation by one time step, computes transmitter current loop
        values under current scenario rules, checks electrical health, updates alarms,
        and logs snapshots.
        """
        self.current_sim_time += timedelta(seconds=self.time_step_sec)
        time_str = self.current_sim_time.strftime("%Y-%m-%d %H:%M:%S")
        snapshots: Dict[str, InstrumentSnapshot] = {}

        for tag, config in self.configs.items():
            scenario = self.active_scenarios[tag]
            nominal_pv = self.nominal_pvs[tag]
            nominal_current = engineering_value_to_current(nominal_pv, config.lrv, config.urv)

            is_stale = False
            stale_duration = 0.0
            is_noisy = False
            noise_std = 0.0
            current_input: Any = None

            # --- Generate Raw Signal based on Active Scenario ---
            if scenario == FaultScenario.NORMAL_OPERATION:
                # Small realistic process jitter (±0.04 mA)
                jitter = self._rng.gauss(0.0, 0.03)
                current_input = round(nominal_current + jitter, 3)
                self._drift_accumulator[tag] = 0.0
                self._stale_counter[tag] = 0

            elif scenario == FaultScenario.LOW_PROCESS_VALUE:
                # Physical process dips below Low threshold, but electrical loop is healthy!
                low_limit = self.thresholds[tag].low_low or (config.lrv + 0.1 * (config.urv - config.lrv))
                target_pv = low_limit * 0.8
                base_ma = engineering_value_to_current(target_pv, config.lrv, config.urv)
                jitter = self._rng.gauss(0.0, 0.02)
                current_input = round(max(3.85, base_ma + jitter), 3)

            elif scenario == FaultScenario.HIGH_PROCESS_VALUE:
                # Physical process surges above High-High threshold, but electrical loop is healthy!
                high_limit = self.thresholds[tag].high_high or (config.urv - 0.1 * (config.urv - config.lrv))
                target_pv = min(config.urv, high_limit * 1.05)
                base_ma = engineering_value_to_current(target_pv, config.lrv, config.urv)
                jitter = self._rng.gauss(0.0, 0.02)
                current_input = round(min(20.4, base_ma + jitter), 3)

            elif scenario == FaultScenario.OPEN_CIRCUIT:
                # Wire break: current collapses below live zero (< 3.6 mA, nominally ~0.0 mA)
                current_input = round(max(0.0, self._rng.uniform(0.0, 0.5)), 3)

            elif scenario == FaultScenario.UNDER_RANGE:
                # Zero drift: current hovers in under-range zone (3.60 to 3.79 mA)
                current_input = round(self._rng.uniform(3.62, 3.78), 3)

            elif scenario == FaultScenario.OVER_RANGE:
                # Sensor saturation: current hovers in over-range zone (20.51 to 20.95 mA)
                current_input = round(self._rng.uniform(20.55, 20.95), 3)

            elif scenario == FaultScenario.STALE_MEASUREMENT:
                # Signal freezes exactly; counter increments
                self._stale_counter[tag] += 1
                if self._last_raw_current[tag] is not None:
                    current_input = self._last_raw_current[tag]
                else:
                    current_input = round(nominal_current, 3)

                is_stale = self._stale_counter[tag] >= 3
                stale_duration = self._stale_counter[tag] * self.time_step_sec

            elif scenario == FaultScenario.GRADUAL_SENSOR_DRIFT:
                # Progressive positive drift accumulating +0.12 mA per time step
                self._drift_accumulator[tag] += 0.12
                drift = self._drift_accumulator[tag]
                jitter = self._rng.gauss(0.0, 0.02)
                current_input = round(nominal_current + drift + jitter, 3)

            elif scenario == FaultScenario.NOISY_SIGNAL:
                # Electromagnetic interference / high frequency ripple
                is_noisy = True
                noise_std = 1.15
                jitter = self._rng.gauss(0.0, noise_std)
                current_input = round(nominal_current + jitter, 3)

            elif scenario == FaultScenario.INVALID_MISSING:
                # Modbus corruption / packet drop / NaN
                choice = self._rng.choice(["NONE", "NAN", "CORRUPT_STR"])
                if choice == "NONE":
                    current_input = None
                elif choice == "NAN":
                    current_input = float("nan")
                else:
                    current_input = "ERR_PARITY_FAIL"

            # --- Signal Processing Pipeline ---
            sig_result = process_instrument_signal(current_input, config)
            self._last_raw_current[tag] = sig_result.raw_current_ma if sig_result.raw_current_ma is not None else None

            # --- Diagnostic Engine ---
            diag = diagnose_instrument(
                signal_result=sig_result,
                config=config,
                is_stale=is_stale,
                stale_duration_sec=stale_duration,
                is_noisy=is_noisy,
                noise_std=noise_std,
                drift_offset=self._drift_accumulator[tag],
                timestamp_str=time_str
            )

            # --- Alarm Management ---
            active_alarms = self.alarm_manager.evaluate_instrument(
                signal_result=sig_result,
                diagnostic=diag,
                thresholds=self.thresholds[tag],
                units=config.units,
                timestamp_str=time_str
            )

            alarm_names = [a.description for a in active_alarms]

            snapshot = InstrumentSnapshot(
                tag=tag,
                description=config.description,
                timestamp=time_str,
                raw_current_ma=sig_result.raw_current_ma,
                process_value=sig_result.process_value,
                units=config.units,
                lrv=config.lrv,
                urv=config.urv,
                signal_status=sig_result.status,
                health_label=sig_result.health_label,
                is_valid_pv=sig_result.is_valid_pv,
                diagnostic=diag,
                active_alarms=alarm_names,
                active_scenario=scenario,
                is_simulated=True
            )
            snapshots[tag] = snapshot

        # Record snapshot in history
        history_entry = {
            "timestamp": time_str,
            "TT_101_ma": snapshots["TT-101"].raw_current_ma,
            "TT_101_pv": snapshots["TT-101"].process_value,
            "TT_101_status": snapshots["TT-101"].signal_status.value,
            "PT_101_ma": snapshots["PT-101"].raw_current_ma,
            "PT_101_pv": snapshots["PT-101"].process_value,
            "PT_101_status": snapshots["PT-101"].signal_status.value,
            "active_alarm_count": len(self.alarm_manager.get_active_alarms()),
        }
        self.history.append(history_entry)
        if len(self.history) > 500:
            self.history.pop(0)

        return snapshots
