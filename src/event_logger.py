"""
Smart Process Instrumentation & Fault Diagnosis System
Module: event_logger.py

Maintains a robust, in-memory and file-backed audit trail of all instrumentation events,
alarms, fault detections, operator acknowledgements, and configuration changes.
"""

from dataclasses import dataclass
from datetime import datetime
import os
import csv
from typing import Dict, List, Optional


@dataclass
class EventRecord:
    event_id: str
    timestamp: str
    instrument_tag: str
    category: str      # 'SIGNAL', 'PROCESS', 'ALARM', 'OPERATOR', 'SYSTEM'
    severity: str      # 'CRITICAL', 'WARNING', 'ADVISORY', 'INFO'
    event_type: str    # e.g., 'OPEN_CIRCUIT_DETECTED', 'ALARM_ACKNOWLEDGED', etc.
    message: str
    details: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "instrument_tag": self.instrument_tag,
            "category": self.category,
            "severity": self.severity,
            "event_type": self.event_type,
            "message": self.message,
            "details": self.details,
        }


class EventLogger:
    """Audit logging manager with duplicate suppression and CSV export."""
    def __init__(self, log_file_path: Optional[str] = None):
        self.log_file_path = log_file_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "event_history.csv"
        )
        self.events: List[EventRecord] = []
        self._counter: int = 1
        self._last_event_signature: Optional[str] = None

    def log_event(
        self,
        instrument_tag: str,
        category: str,
        severity: str,
        event_type: str,
        message: str,
        details: str = "",
        timestamp_str: Optional[str] = None
    ) -> EventRecord:
        """
        Logs an event with duplicate suppression for rapid UI re-renders.
        """
        ts = timestamp_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Suppress identical event if triggered within the exact same second for the same tag
        sig = f"{instrument_tag}|{event_type}|{severity}|{message}"
        if self.events and self.events[-1].timestamp == ts and self._last_event_signature == sig:
            return self.events[-1]

        event = EventRecord(
            event_id=f"EVT-{self._counter:06d}",
            timestamp=ts,
            instrument_tag=instrument_tag,
            category=category,
            severity=severity,
            event_type=event_type,
            message=message,
            details=details,
        )
        self._counter += 1
        self._last_event_signature = sig
        self.events.append(event)

        # Optional write to disk
        self._append_to_disk(event)
        return event

    def _append_to_disk(self, event: EventRecord):
        try:
            os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
            file_exists = os.path.exists(self.log_file_path) and os.path.getsize(self.log_file_path) > 0
            with open(self.log_file_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "event_id", "timestamp", "instrument_tag", "category",
                    "severity", "event_type", "message", "details"
                ])
                if not file_exists:
                    writer.writeheader()
                writer.writerow(event.to_dict())
        except Exception:
            # Gracefully handle file permissions / access errors without crashing the main application
            pass

    def get_events(self, limit: Optional[int] = None) -> List[EventRecord]:
        """Returns the in-memory event records, optionally limited to the most recent N items."""
        if limit:
            return self.events[-limit:]
        return list(self.events)

    def clear(self):
        """Clears in-memory history and counter."""
        self.events.clear()
        self._counter = 1
        self._last_event_signature = None
