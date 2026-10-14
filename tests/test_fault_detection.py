"""
Unit tests for fault_detection.py and simulator.py fault injection scenarios.
"""

import pytest
from src.fault_detection import FaultSeverity, diagnose_instrument
from src.signal_processing import SignalConfig, SignalResult, SignalStatus
from src.simulator import FaultScenario, ProcessSimulator


@pytest.fixture
def config():
    return SignalConfig(
        tag="TT-101",
        description="Reactor Core Temperature",
        lrv=0.0,
        urv=150.0,
        units="°C"
    )


def test_open_circuit_diagnosis(config):
    res = SignalResult(
        tag=config.tag,
        raw_current_ma=0.0,
        process_value=None,
        status=SignalStatus.OPEN_CIRCUIT,
        health_label="FAULT",
        is_valid_pv=False,
        diagnostic_message="Wire break"
    )
    diag = diagnose_instrument(res, config)
    assert diag.severity == FaultSeverity.CRITICAL
    assert "Open Circuit" in diag.fault_name
    assert any("multimeter" in step.lower() for step in diag.suggested_inspection_steps)


def test_stale_measurement_diagnosis(config):
    res = SignalResult(
        tag=config.tag,
        raw_current_ma=12.0,
        process_value=75.0,
        status=SignalStatus.NORMAL,
        health_label="NORMAL",
        is_valid_pv=True,
        diagnostic_message="Normal"
    )
    diag = diagnose_instrument(res, config, is_stale=True, stale_duration_sec=10.0)
    assert diag.severity == FaultSeverity.WARNING
    assert "Stale" in diag.fault_name
    assert any("gateway" in step.lower() or "lcd" in step.lower() for step in diag.suggested_inspection_steps)


def test_sensor_drift_diagnosis(config):
    res = SignalResult(
        tag=config.tag,
        raw_current_ma=12.8,
        process_value=82.5,
        status=SignalStatus.NORMAL,
        health_label="NORMAL",
        is_valid_pv=True,
        diagnostic_message="Normal"
    )
    diag = diagnose_instrument(res, config, drift_offset=0.8)
    assert diag.severity == FaultSeverity.WARNING
    assert "Drift" in diag.fault_name
    assert any("calibration" in step.lower() for step in diag.suggested_inspection_steps)


def test_noisy_signal_diagnosis(config):
    res = SignalResult(
        tag=config.tag,
        raw_current_ma=12.0,
        process_value=75.0,
        status=SignalStatus.NORMAL,
        health_label="NORMAL",
        is_valid_pv=True,
        diagnostic_message="Normal"
    )
    diag = diagnose_instrument(res, config, is_noisy=True, noise_std=1.2)
    assert diag.severity == FaultSeverity.ADVISORY
    assert "Noisy" in diag.fault_name
    assert any("shield" in step.lower() or "damping" in step.lower() for step in diag.suggested_inspection_steps)


def test_simulator_scenarios_and_recovery():
    """Tests all 10 simulator scenarios and ensures safe return to normal operation."""
    sim = ProcessSimulator(random_seed=123)

    for scenario in FaultScenario:
        sim.set_scenario("TT-101", scenario)
        # Advance 4 steps to allow multi-step behaviors (like drift & stale) to manifest
        for _ in range(4):
            snapshots = sim.step()

        snap = snapshots["TT-101"]
        assert snap.tag == "TT-101"
        assert snap.is_simulated is True

        if scenario == FaultScenario.OPEN_CIRCUIT:
            assert snap.signal_status == SignalStatus.OPEN_CIRCUIT
            assert not snap.is_valid_pv
        elif scenario == FaultScenario.INVALID_MISSING:
            assert snap.signal_status == SignalStatus.INVALID
            assert not snap.is_valid_pv
        elif scenario == FaultScenario.UNDER_RANGE:
            assert snap.signal_status == SignalStatus.UNDER_RANGE
        elif scenario == FaultScenario.OVER_RANGE:
            assert snap.signal_status == SignalStatus.OVER_RANGE

    # Test returning to normal
    sim.reset_instrument("TT-101")
    for _ in range(3):
        snapshots = sim.step()

    snap_normal = snapshots["TT-101"]
    assert snap_normal.signal_status == SignalStatus.NORMAL
    assert snap_normal.is_valid_pv
    assert snap_normal.diagnostic.severity == FaultSeverity.NORMAL
