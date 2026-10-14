"""
Unit tests for alarm_manager.py.
Covers threshold validation, ISA-18.2 state transitions, acknowledgement, and clearing.
"""

import pytest
from src.alarm_manager import (
    AlarmManager,
    AlarmPriority,
    AlarmState,
    AlarmThresholds,
    validate_thresholds
)
from src.fault_detection import DiagnosticRecord, FaultSeverity
from src.signal_processing import SignalConfig, SignalResult, SignalStatus


@pytest.fixture
def manager():
    return AlarmManager()


@pytest.fixture
def config():
    return SignalConfig(
        tag="PT-101",
        description="Pressure Transmitter",
        lrv=0.0,
        urv=10.0,
        units="bar"
    )


@pytest.fixture
def thresholds():
    return AlarmThresholds(low_low=1.0, low=2.0, high=7.5, high_high=9.0)


def test_threshold_validation():
    """Monotonicity must be strictly enforced: LL < L < H < HH within LRV..URV."""
    valid_th = AlarmThresholds(low_low=1.0, low=2.0, high=8.0, high_high=9.5)
    valid, msg = validate_thresholds(valid_th, lrv=0.0, urv=10.0)
    assert valid

    # Inverted order
    invalid_th = AlarmThresholds(low_low=5.0, low=2.0, high=8.0, high_high=9.5)
    valid2, msg2 = validate_thresholds(invalid_th, lrv=0.0, urv=10.0)
    assert not valid2
    assert "Threshold violation" in msg2

    # Out of range limit
    out_of_bound_th = AlarmThresholds(low_low=1.0, low=2.0, high=8.0, high_high=12.0)
    valid3, msg3 = validate_thresholds(out_of_bound_th, lrv=0.0, urv=10.0)
    assert not valid3
    assert "outside instrument calibrated span" in msg3


def test_high_and_high_high_process_alarms(manager, config, thresholds):
    """Verifies triggering of High Warning and High-High Critical alarms."""
    # Test High Warning (e.g. PV = 8.0 bar, > 7.5 bar)
    sig_high = SignalResult(
        tag="PT-101", raw_current_ma=16.8, process_value=8.0,
        status=SignalStatus.NORMAL, health_label="NORMAL", is_valid_pv=True, diagnostic_message=""
    )
    diag = DiagnosticRecord(
        fault_name="Normal", instrument_tag="PT-101", severity=FaultSeverity.NORMAL,
        timestamp="2026-10-14 12:00:00", observed_condition="", possible_causes=[],
        suggested_inspection_steps=[], current_status="NORMAL"
    )

    alarms = manager.evaluate_instrument(sig_high, diag, thresholds, "bar")
    assert len(alarms) == 1
    assert alarms[0].alarm_type == "HIGH"
    assert alarms[0].priority == AlarmPriority.WARNING
    assert alarms[0].state == AlarmState.ACTIVE_UNACK

    # Test High-High Critical (e.g. PV = 9.2 bar, > 9.0 bar)
    sig_hh = SignalResult(
        tag="PT-101", raw_current_ma=18.72, process_value=9.2,
        status=SignalStatus.NORMAL, health_label="NORMAL", is_valid_pv=True, diagnostic_message=""
    )
    alarms_hh = manager.evaluate_instrument(sig_hh, diag, thresholds, "bar")
    assert len(alarms_hh) == 1
    assert alarms_hh[0].alarm_type == "HIGH_HIGH"
    assert alarms_hh[0].priority == AlarmPriority.CRITICAL


def test_alarm_acknowledgement_lifecycle(manager, config, thresholds):
    """Tests the transition: ACTIVE_UNACK -> ACTIVE_ACK -> CLEARED."""
    sig_high = SignalResult(
        tag="PT-101", raw_current_ma=16.8, process_value=8.0,
        status=SignalStatus.NORMAL, health_label="NORMAL", is_valid_pv=True, diagnostic_message=""
    )
    diag = DiagnosticRecord(
        fault_name="Normal", instrument_tag="PT-101", severity=FaultSeverity.NORMAL,
        timestamp="2026-10-14 12:00:00", observed_condition="", possible_causes=[],
        suggested_inspection_steps=[], current_status="NORMAL"
    )

    alarms = manager.evaluate_instrument(sig_high, diag, thresholds, "bar")
    alarm_id = alarms[0].alarm_id
    assert alarms[0].state == AlarmState.ACTIVE_UNACK

    # Operator acknowledges alarm while still physically active
    ack_res = manager.acknowledge_alarm(alarm_id, ack_time_str="2026-10-14 12:01:00")
    assert ack_res is True
    assert alarms[0].state == AlarmState.ACTIVE_ACK

    # Physical variable returns to safe normal condition (e.g. PV = 5.0 bar)
    sig_normal = SignalResult(
        tag="PT-101", raw_current_ma=12.0, process_value=5.0,
        status=SignalStatus.NORMAL, health_label="NORMAL", is_valid_pv=True, diagnostic_message=""
    )
    manager.evaluate_instrument(sig_normal, diag, thresholds, "bar")

    # Alarm should now be cleared from active list
    assert len(manager.get_active_alarms()) == 0
    assert alarms[0].state == AlarmState.CLEARED
    assert alarms[0].cleared_time is not None


def test_separation_of_electrical_fault_and_process_alarm(manager, config, thresholds):
    """
    An electrical wire break (< 3.6 mA) must raise a SIGNAL FAULT alarm,
    and must NOT evaluate process setpoints (e.g. must not trigger Low-Low process alarm).
    """
    sig_open = SignalResult(
        tag="PT-101", raw_current_ma=0.0, process_value=None,
        status=SignalStatus.OPEN_CIRCUIT, health_label="FAULT", is_valid_pv=False,
        diagnostic_message="Wire break"
    )
    diag = DiagnosticRecord(
        fault_name="Transmitter Open Circuit", instrument_tag="PT-101",
        severity=FaultSeverity.CRITICAL, timestamp="2026-10-14 12:00:00",
        observed_condition="Loop current 0 mA", possible_causes=[], suggested_inspection_steps=[],
        current_status="ACTIVE_FAULT"
    )

    alarms = manager.evaluate_instrument(sig_open, diag, thresholds, "bar")
    assert len(alarms) == 1
    assert alarms[0].alarm_type == "OPEN_CIRCUIT"
    assert "SIGNAL FAULT" in alarms[0].description
    # Ensure no process LOW_LOW was generated
    assert all(a.alarm_type != "LOW_LOW" for a in alarms)
