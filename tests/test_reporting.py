"""
Unit tests for event_logger.py and reporting.py.
"""

import os
import pytest
from src.alarm_manager import AlarmItem, AlarmPriority, AlarmState
from src.event_logger import EventLogger
from src.reporting import (
    export_dataframe_to_csv_string,
    generate_alarm_history_dataframe,
    generate_event_history_dataframe,
    generate_kpi_summary
)


def test_event_logger_lifecycle(tmp_path):
    log_file = tmp_path / "test_events.csv"
    logger = EventLogger(log_file_path=str(log_file))

    evt = logger.log_event(
        instrument_tag="TT-101",
        category="SIGNAL",
        severity="CRITICAL",
        event_type="OPEN_CIRCUIT",
        message="Wire break detected",
        timestamp_str="2026-10-14 12:00:00"
    )

    assert evt.instrument_tag == "TT-101"
    assert evt.event_id.startswith("EVT-")
    assert len(logger.get_events()) == 1

    # Rapid duplicate rerun suppression in same second
    evt2 = logger.log_event(
        instrument_tag="TT-101",
        category="SIGNAL",
        severity="CRITICAL",
        event_type="OPEN_CIRCUIT",
        message="Wire break detected",
        timestamp_str="2026-10-14 12:00:00"
    )
    assert len(logger.get_events()) == 1


def test_empty_dataframe_generation():
    """Empty alarm and event histories must produce valid DataFrames without crashing."""
    df_alarms = generate_alarm_history_dataframe([])
    assert df_alarms.empty
    assert "Alarm ID" in df_alarms.columns

    df_events = generate_event_history_dataframe([])
    assert df_events.empty
    assert "Event ID" in df_events.columns


def test_reporting_kpi_summary():
    dummy_alarm = AlarmItem(
        alarm_id="ALM-00001",
        instrument_tag="TT-101",
        alarm_type="HIGH",
        description="Temp High",
        priority=AlarmPriority.WARNING,
        state=AlarmState.ACTIVE_UNACK,
        activation_time="2026-10-14 12:00:00",
        trigger_value=105.0,
        threshold_value=95.0,
        units="°C"
    )

    kpis = generate_kpi_summary(
        alarm_history=[dummy_alarm],
        active_alarms=[dummy_alarm],
        history_records=[{"dummy": 1}, {"dummy": 2}]
    )

    assert kpis["total_alarm_events_logged"] == 1
    assert kpis["active_alarms_count"] == 1
    assert kpis["warning_active"] == 1
    assert kpis["critical_active"] == 0
    assert kpis["total_telemetry_ticks"] == 2


def test_csv_export_content():
    dummy_alarm = AlarmItem(
        alarm_id="ALM-00001",
        instrument_tag="TT-101",
        alarm_type="HIGH",
        description="Temp High",
        priority=AlarmPriority.WARNING,
        state=AlarmState.ACTIVE_UNACK,
        activation_time="2026-10-14 12:00:00",
        trigger_value=105.0,
        threshold_value=95.0,
        units="°C"
    )
    df = generate_alarm_history_dataframe([dummy_alarm])
    csv_str = export_dataframe_to_csv_string(df)
    assert "Alarm ID,Instrument Tag" in csv_str
    assert "ALM-00001,TT-101" in csv_str
