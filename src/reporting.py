"""
Smart Process Instrumentation & Fault Diagnosis System
Module: reporting.py

Generates statistical KPIs, alarm summaries, and formatted CSV export payloads.
"""

import io
import csv
from typing import Any, Dict, List
import pandas as pd
from src.alarm_manager import AlarmItem, AlarmPriority
from src.event_logger import EventRecord


def generate_alarm_history_dataframe(alarm_history: List[AlarmItem]) -> pd.DataFrame:
    """Converts a list of AlarmItem objects into a clean, formatted Pandas DataFrame."""
    if not alarm_history:
        return pd.DataFrame(columns=[
            "Alarm ID", "Instrument Tag", "Alarm Type", "Description",
            "Priority", "State", "Activation Time", "Trigger Value",
            "Threshold Value", "Units", "Acknowledged Time", "Cleared Time"
        ])

    rows = []
    for a in alarm_history:
        d = a.to_dict()
        rows.append({
            "Alarm ID": d["alarm_id"],
            "Instrument Tag": d["instrument_tag"],
            "Alarm Type": d["alarm_type"],
            "Description": d["description"],
            "Priority": d["priority"],
            "State": d["state"],
            "Activation Time": d["activation_time"],
            "Trigger Value": d["trigger_value"],
            "Threshold Value": d["threshold_value"],
            "Units": d["units"],
            "Acknowledged Time": d["acknowledged_time"],
            "Cleared Time": d["cleared_time"]
        })
    return pd.DataFrame(rows)


def generate_event_history_dataframe(event_history: List[EventRecord]) -> pd.DataFrame:
    """Converts a list of EventRecord objects into a clean Pandas DataFrame."""
    if not event_history:
        return pd.DataFrame(columns=[
            "Event ID", "Timestamp", "Instrument Tag", "Category",
            "Severity", "Event Type", "Message", "Details"
        ])

    rows = []
    for e in event_history:
        d = e.to_dict()
        rows.append({
            "Event ID": d["event_id"],
            "Timestamp": d["timestamp"],
            "Instrument Tag": d["instrument_tag"],
            "Category": d["category"],
            "Severity": d["severity"],
            "Event Type": d["event_type"],
            "Message": d["message"],
            "Details": d["details"]
        })
    return pd.DataFrame(rows)


def generate_kpi_summary(
    alarm_history: List[AlarmItem],
    active_alarms: List[AlarmItem],
    history_records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Computes executive operational KPIs for the instrumentation supervisor."""
    total_alarms = len(alarm_history)
    active_count = len(active_alarms)

    priority_counts = {p.value: 0 for p in AlarmPriority}
    for a in active_alarms:
        priority_counts[a.priority.value] = priority_counts.get(a.priority.value, 0) + 1

    total_cleared = sum(1 for a in alarm_history if a.cleared_time is not None)
    total_unack = sum(1 for a in active_alarms if "UNACK" in a.state.value)

    sim_samples = len(history_records)

    return {
        "total_alarm_events_logged": total_alarms,
        "active_alarms_count": active_count,
        "critical_active": priority_counts.get(AlarmPriority.CRITICAL.value, 0),
        "warning_active": priority_counts.get(AlarmPriority.WARNING.value, 0),
        "advisory_active": priority_counts.get(AlarmPriority.ADVISORY.value, 0),
        "total_cleared_alarms": total_cleared,
        "unacknowledged_alarms": total_unack,
        "total_telemetry_ticks": sim_samples,
    }


def export_dataframe_to_csv_string(df: pd.DataFrame) -> str:
    """Serializes DataFrame into a UTF-8 CSV string for Streamlit download buttons."""
    return df.to_csv(index=False)
