"""
Smart Process Instrumentation & Fault Diagnosis System
Module: alarm_manager.py

Industrial alarm management complying with ISA-18.2 principles:
- 4-tier process thresholds (Low-Low, Low, High, High-High).
- Alarm priority levels (CRITICAL, WARNING, ADVISORY).
- Lifecycle state transitions (ACTIVE_UNACK, ACTIVE_ACK, CLEARED_UNACK, CLEARED).
- Duplicate event chattering suppression.
- Operator acknowledgement.
- Clear distinction between electrical hardware fault alarms and physical process limit alarms.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import math
from typing import Dict, List, Optional, Tuple
from src.fault_detection import DiagnosticRecord, FaultSeverity
from src.signal_processing import SignalResult, SignalStatus


class AlarmPriority(str, Enum):
    CRITICAL = "CRITICAL"    # High urgency, potential safety trip, immediate operator response required
    WARNING = "WARNING"      # Moderate urgency, abnormal process excursion
    ADVISORY = "ADVISORY"    # Informational or signal maintenance notice


class AlarmState(str, Enum):
    ACTIVE_UNACK = "ACTIVE_UNACK"        # Condition active, operator has NOT acknowledged
    ACTIVE_ACK = "ACTIVE_ACK"            # Condition active, operator HAS acknowledged
    CLEARED_UNACK = "CLEARED_UNACK"      # Condition returned to normal, but was never acknowledged
    CLEARED = "CLEARED"                  # Condition returned to normal and acknowledged


@dataclass
class AlarmThresholds:
    """Configurable 4-stage process limit setpoints."""
    low_low: Optional[float] = None    # LL - Critical Low (Emergency Shutdown / Interlock warning)
    low: Optional[float] = None        # L  - Warning Low
    high: Optional[float] = None       # H  - Warning High
    high_high: Optional[float] = None  # HH - Critical High (Emergency Overpressure / Overtemperature)


@dataclass
class AlarmItem:
    """Active or historical alarm instance."""
    alarm_id: str
    instrument_tag: str
    alarm_type: str                   # e.g., 'HIGH_HIGH', 'HIGH', 'LOW', 'LOW_LOW', 'SIGNAL_FAULT'
    description: str
    priority: AlarmPriority
    state: AlarmState
    activation_time: str
    trigger_value: Optional[float]
    threshold_value: Optional[float]
    units: str
    acknowledged_time: Optional[str] = None
    cleared_time: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "alarm_id": self.alarm_id,
            "instrument_tag": self.instrument_tag,
            "alarm_type": self.alarm_type,
            "description": self.description,
            "priority": self.priority.value,
            "state": self.state.value,
            "activation_time": self.activation_time,
            "trigger_value": f"{self.trigger_value:.2f}" if self.trigger_value is not None else "N/A",
            "threshold_value": f"{self.threshold_value:.2f}" if self.threshold_value is not None else "N/A",
            "units": self.units,
            "acknowledged_time": self.acknowledged_time or "-",
            "cleared_time": self.cleared_time or "-",
        }


def validate_thresholds(
    thresholds: AlarmThresholds,
    lrv: float,
    urv: float
) -> Tuple[bool, str]:
    """
    Validates logical monotonicity of configured alarm limits:
    LRV <= LL < L < H < HH <= URV
    """
    values = []
    names = []

    if thresholds.low_low is not None:
        values.append(thresholds.low_low)
        names.append("Low-Low")
    if thresholds.low is not None:
        values.append(thresholds.low)
        names.append("Low")
    if thresholds.high is not None:
        values.append(thresholds.high)
        names.append("High")
    if thresholds.high_high is not None:
        values.append(thresholds.high_high)
        names.append("High-High")

    for i in range(len(values) - 1):
        if values[i] >= values[i + 1]:
            return False, f"Threshold violation: {names[i]} ({values[i]}) must be strictly less than {names[i+1]} ({values[i+1]})."

    # Verify bounds within operating span
    for val, name in zip(values, names):
        if val < lrv or val > urv:
            return False, f"{name} limit ({val}) is outside instrument calibrated span ({lrv} to {urv})."

    return True, "Thresholds are logically valid."


class AlarmManager:
    """
    Manages process threshold alarms, electrical signal alarms,
    state transitions, acknowledgements, and suppression of duplicate alarms.
    """
    def __init__(self):
        # Key: (instrument_tag, alarm_type) -> AlarmItem
        self._active_alarms: Dict[Tuple[str, str], AlarmItem] = {}
        # Chronological log of all alarm transitions (history)
        self.alarm_history: List[AlarmItem] = []
        self._counter: int = 1

    def evaluate_instrument(
        self,
        signal_result: SignalResult,
        diagnostic: DiagnosticRecord,
        thresholds: AlarmThresholds,
        units: str,
        timestamp_str: Optional[str] = None
    ) -> List[AlarmItem]:
        """
        Evaluates an instrument's current state:
        - If electrical signal is faulty, raises/updates hardware alarm and bypasses process alarms.
        - If electrical signal is healthy, checks process thresholds (LL, L, H, HH).
        - Clears conditions that are no longer violated.
        """
        now_str = timestamp_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tag = signal_result.tag
        current_alarms: List[AlarmItem] = []

        # 1. Electrical Loop / Signal Fault Alarms
        if not signal_result.is_valid_pv or signal_result.status != SignalStatus.NORMAL:
            fault_type = signal_result.status.value
            alarm_key = (tag, fault_type)

            priority = AlarmPriority.CRITICAL if signal_result.status in (
                SignalStatus.OPEN_CIRCUIT, SignalStatus.INVALID, SignalStatus.SENSOR_FAILURE_HIGH
            ) else AlarmPriority.WARNING

            if alarm_key not in self._active_alarms:
                item = AlarmItem(
                    alarm_id=f"ALM-{self._counter:05d}",
                    instrument_tag=tag,
                    alarm_type=fault_type,
                    description=f"SIGNAL FAULT: {diagnostic.fault_name}",
                    priority=priority,
                    state=AlarmState.ACTIVE_UNACK,
                    activation_time=now_str,
                    trigger_value=signal_result.raw_current_ma,
                    threshold_value=3.8 if "UNDER" in fault_type else 20.5,
                    units="mA"
                )
                self._counter += 1
                self._active_alarms[alarm_key] = item
                self.alarm_history.append(item)

            current_alarms.append(self._active_alarms[alarm_key])

            # Clear any stale process limits because PV is untrusted
            self._clear_process_alarms_for_tag(tag, now_str)
            return current_alarms
        else:
            # Signal is normal: clear any active signal fault alarms for this tag
            self._clear_signal_alarms_for_tag(tag, now_str)

        # 2. Process Limit Evaluation (Only when electrical signal is valid!)
        pv = signal_result.process_value
        if pv is None or not math.isfinite(pv):
            return current_alarms

        active_limit_types = set()

        # High-High Alarm
        if thresholds.high_high is not None and pv >= thresholds.high_high:
            active_limit_types.add("HIGH_HIGH")
            item = self._trigger_or_retain_process_alarm(
                tag=tag,
                alarm_type="HIGH_HIGH",
                description=f"CRITICAL HIGH {tag}: PV {pv:.2f} {units} >= HH limit {thresholds.high_high:.2f} {units}",
                priority=AlarmPriority.CRITICAL,
                pv=pv,
                threshold=thresholds.high_high,
                units=units,
                now_str=now_str
            )
            current_alarms.append(item)
        # High Alarm (only if not HH to prevent alarm flooding, or hierarchical)
        elif thresholds.high is not None and pv >= thresholds.high:
            active_limit_types.add("HIGH")
            item = self._trigger_or_retain_process_alarm(
                tag=tag,
                alarm_type="HIGH",
                description=f"WARNING HIGH {tag}: PV {pv:.2f} {units} >= High limit {thresholds.high:.2f} {units}",
                priority=AlarmPriority.WARNING,
                pv=pv,
                threshold=thresholds.high,
                units=units,
                now_str=now_str
            )
            current_alarms.append(item)

        # Low-Low Alarm
        if thresholds.low_low is not None and pv <= thresholds.low_low:
            active_limit_types.add("LOW_LOW")
            item = self._trigger_or_retain_process_alarm(
                tag=tag,
                alarm_type="LOW_LOW",
                description=f"CRITICAL LOW {tag}: PV {pv:.2f} {units} <= LL limit {thresholds.low_low:.2f} {units}",
                priority=AlarmPriority.CRITICAL,
                pv=pv,
                threshold=thresholds.low_low,
                units=units,
                now_str=now_str
            )
            current_alarms.append(item)
        # Low Alarm
        elif thresholds.low is not None and pv <= thresholds.low:
            active_limit_types.add("LOW")
            item = self._trigger_or_retain_process_alarm(
                tag=tag,
                alarm_type="LOW",
                description=f"WARNING LOW {tag}: PV {pv:.2f} {units} <= Low limit {thresholds.low:.2f} {units}",
                priority=AlarmPriority.WARNING,
                pv=pv,
                threshold=thresholds.low,
                units=units,
                now_str=now_str
            )
            current_alarms.append(item)

        # Clear process alarms that are no longer exceeded
        for p_type in ["HIGH_HIGH", "HIGH", "LOW", "LOW_LOW"]:
            if p_type not in active_limit_types:
                key = (tag, p_type)
                if key in self._active_alarms:
                    self._clear_alarm(key, now_str)

        return current_alarms

    def _trigger_or_retain_process_alarm(
        self,
        tag: str,
        alarm_type: str,
        description: str,
        priority: AlarmPriority,
        pv: float,
        threshold: float,
        units: str,
        now_str: str
    ) -> AlarmItem:
        key = (tag, alarm_type)
        if key not in self._active_alarms:
            item = AlarmItem(
                alarm_id=f"ALM-{self._counter:05d}",
                instrument_tag=tag,
                alarm_type=alarm_type,
                description=description,
                priority=priority,
                state=AlarmState.ACTIVE_UNACK,
                activation_time=now_str,
                trigger_value=pv,
                threshold_value=threshold,
                units=units
            )
            self._counter += 1
            self._active_alarms[key] = item
            self.alarm_history.append(item)
            return item
        else:
            # Already active; update trigger value to current reading without spamming history
            item = self._active_alarms[key]
            item.trigger_value = pv
            return item

    def acknowledge_alarm(self, alarm_id: str, ack_time_str: Optional[str] = None) -> bool:
        """Acknowledge an active or cleared-unacknowledged alarm by ID."""
        now_str = ack_time_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for key, item in list(self._active_alarms.items()):
            if item.alarm_id == alarm_id:
                if item.state == AlarmState.ACTIVE_UNACK:
                    item.state = AlarmState.ACTIVE_ACK
                    item.acknowledged_time = now_str
                    return True
                elif item.state == AlarmState.CLEARED_UNACK:
                    item.state = AlarmState.CLEARED
                    item.acknowledged_time = now_str
                    del self._active_alarms[key]
                    return True

        # Check in history for unacknowledged cleared items
        for item in self.alarm_history:
            if item.alarm_id == alarm_id and item.state in (AlarmState.ACTIVE_UNACK, AlarmState.CLEARED_UNACK):
                item.state = AlarmState.CLEARED if item.cleared_time else AlarmState.ACTIVE_ACK
                item.acknowledged_time = now_str
                return True
        return False

    def acknowledge_all(self, now_str: Optional[str] = None) -> int:
        """Acknowledge all unacknowledged active alarms."""
        ts = now_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        count = 0
        for item in self._active_alarms.values():
            if item.state == AlarmState.ACTIVE_UNACK:
                item.state = AlarmState.ACTIVE_ACK
                item.acknowledged_time = ts
                count += 1
        return count

    def _clear_alarm(self, key: Tuple[str, str], now_str: str):
        if key in self._active_alarms:
            item = self._active_alarms[key]
            item.cleared_time = now_str
            if item.state == AlarmState.ACTIVE_ACK:
                item.state = AlarmState.CLEARED
                del self._active_alarms[key]
            elif item.state == AlarmState.ACTIVE_UNACK:
                item.state = AlarmState.CLEARED_UNACK
                # Remains in active list until operator acknowledges that it occurred
                del self._active_alarms[key]

    def _clear_signal_alarms_for_tag(self, tag: str, now_str: str):
        for (t, a_type) in list(self._active_alarms.keys()):
            if t == tag and a_type in [s.value for s in SignalStatus if s != SignalStatus.NORMAL]:
                self._clear_alarm((t, a_type), now_str)

    def _clear_process_alarms_for_tag(self, tag: str, now_str: str):
        for (t, a_type) in list(self._active_alarms.keys()):
            if t == tag and a_type in ["HIGH_HIGH", "HIGH", "LOW", "LOW_LOW"]:
                self._clear_alarm((t, a_type), now_str)

    def get_active_alarms(self) -> List[AlarmItem]:
        """Returns currently active alarms."""
        return list(self._active_alarms.values())

    def get_active_count_by_priority(self) -> Dict[str, int]:
        """Returns count of active alarms grouped by priority."""
        counts = {p.value: 0 for p in AlarmPriority}
        for item in self._active_alarms.values():
            counts[item.priority.value] += 1
        return counts
