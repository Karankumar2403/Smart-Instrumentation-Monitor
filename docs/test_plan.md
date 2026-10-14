# Test Plan & Verification Matrix: Smart Process Instrumentation & Fault Diagnosis System

This document outlines the automated verification suite, test scenarios, inputs, expected outcomes, and actual verified test results for the project.

**Test Execution Date:** 2026-10-14  
**Test Framework:** `pytest 9.1.1` on Python 3.14.6 (Windows 64-bit)  
**Execution Command:** `python -m pytest -v`  
**Overall Status:** **29 passed in 25.49s (100% Pass Rate)**

---

## 1. Automated Test Verification Matrix

| Test Case ID | Test Category | Scenario / Method | Inputs | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-SIG-01** | Signal Scaling | 4.0 mA Conversion | `current_ma=4.0`, TT `[0, 150]`, PT `[0, 10]` | Returns exact Lower Range Value (0.0 °C, 0.0 bar) | Returned 0.0 °C, 0.0 bar exactly | **PASS** |
| **TC-SIG-02** | Signal Scaling | 12.0 mA Conversion | `current_ma=12.0`, TT `[0, 150]`, PT `[0, 10]` | Returns exact 50% midpoint (75.0 °C, 5.0 bar) | Returned 75.0 °C, 5.0 bar exactly | **PASS** |
| **TC-SIG-03** | Signal Scaling | 20.0 mA Conversion | `current_ma=20.0`, TT `[0, 150]`, PT `[0, 10]` | Returns exact Upper Range Value (150.0 °C, 10.0 bar) | Returned 150.0 °C, 10.0 bar exactly | **PASS** |
| **TC-SIG-04** | Signal Scaling | Inverse Conversion | `pv=75.0 °C` on range `[0, 150]` | Returns 12.0 mA; round-trip PV matches input | Returned 12.0 mA and reconstructed 75.0 °C | **PASS** |
| **TC-SIG-05** | Signal Scaling | Negative Range Span | Range `[-50, +100] °C`, `current=4, 12, 20` | Returns -50.0 °C, 25.0 °C, 100.0 °C | Returned -50.0, 25.0, 100.0 °C | **PASS** |
| **TC-SIG-06** | Validation | Zero Span Detection | `lrv=100.0`, `urv=100.0` | Validation fails; conversion raises `ValueError` | Validation failed with zero span; raised ValueError | **PASS** |
| **TC-SIG-07** | Validation | Non-Finite Span | `urv=inf` and `lrv=nan` | Configuration rejected as invalid | Configuration validation rejected both | **PASS** |
| **TC-SIG-08** | Fault Check | Open-Circuit (<3.6 mA) | `current_ma=0.0` and `3.59` | Status `OPEN_CIRCUIT`, PV marked unreliable | Status `OPEN_CIRCUIT`, PV is `None` | **PASS** |
| **TC-SIG-09** | Fault Check | Under-Range (3.6-3.8 mA) | `current_ma=3.70` | Status `UNDER_RANGE`, Health `WARNING` | Status `UNDER_RANGE`, Health `WARNING` | **PASS** |
| **TC-SIG-10** | Fault Check | Over-Range (20.5-21 mA) | `current_ma=20.75` | Status `OVER_RANGE`, Health `WARNING` | Status `OVER_RANGE`, Health `WARNING` | **PASS** |
| **TC-SIG-11** | Fault Check | Sensor Burnout (>21 mA) | `current_ma=21.8` | Status `SENSOR_FAILURE_HIGH`, PV suppressed | Status `SENSOR_FAILURE_HIGH`, PV suppressed | **PASS** |
| **TC-SIG-12** | Robustness | Null Telemetry Input | `current_ma=None` | Status `INVALID`, handled gracefully without crash | Status `INVALID`, returned clean diagnostic | **PASS** |
| **TC-SIG-13** | Robustness | Non-numeric String | `current_ma='BAD_DATA'` | Status `INVALID`, conversion safely aborted | Handled gracefully without unhandled exception | **PASS** |
| **TC-SIG-14** | Robustness | NaN / Inf Telemetry | `nan`, `+inf`, `-inf` | Status `INVALID`, flagged as corrupted | Handled safely; PV returned `None` | **PASS** |
| **TC-DIAG-01**| Diagnostics | Open Circuit Guidance | Status `OPEN_CIRCUIT` | CRITICAL severity, suggested multimeter checks | Severity CRITICAL; multimeter steps included | **PASS** |
| **TC-DIAG-02**| Diagnostics | Stale Signal Guidance | Static value for >3 iterations | WARNING severity, suggested gateway & LCD check | Severity WARNING; communication checks suggested | **PASS** |
| **TC-DIAG-03**| Diagnostics | Sensor Drift Guidance | Systematic offset >0.05 mA | WARNING severity, suggested calibration checks | Severity WARNING; 5-point calibration advised | **PASS** |
| **TC-DIAG-04**| Diagnostics | High Noise Guidance | Jitter standard deviation >0.5 | ADVISORY severity, suggested shield wire check | Severity ADVISORY; shielding guidance provided | **PASS** |
| **TC-SIM-01** | Simulator | 10 Scenarios & Reset | All 10 scenarios cycled | Correct statuses generated, returns to NORMAL | All 10 scenarios passed; reset restored NORMAL | **PASS** |
| **TC-ALM-01** | Alarm Logic | Monotonicity Check | `LL < L < H < HH` validation | Inverted and out-of-span setpoints rejected | Valid setpoints passed; invalid rejected | **PASS** |
| **TC-ALM-02** | Alarm Logic | High & High-High | `PV = 8.0` and `9.2 bar` | Triggers High (Warning) and High-High (Critical) | High and High-High alarms activated correctly | **PASS** |
| **TC-ALM-03** | Alarm Logic | Ack & Clear Lifecycle | `ACTIVE_UNACK -> ACK -> CLEAR` | Transitions state correctly upon ack and normal return | Alarm cleared from active list upon normalization | **PASS** |
| **TC-ALM-04** | Alarm Logic | Fault Decoupling | `0.0 mA` loop wire break | Raises `SIGNAL FAULT`, bypasses process low alarm | Raised SIGNAL FAULT; no false process LL alarm | **PASS** |
| **TC-LOG-01** | Event Logging | Audit & Deduplication | Rapid duplicate log calls | Suppressed duplicate entries in same timestamp | Duplicate event correctly suppressed | **PASS** |
| **TC-REP-01** | Reporting | Empty DataFrame Safety | Empty list input | Returns empty DataFrame with columns, no crash | Returns valid empty DataFrame | **PASS** |
| **TC-REP-02** | Reporting | KPI Aggregation | Mixed alarm list | Accurately tallies active, critical, and ticks | KPI summary accurately computed metrics | **PASS** |
| **TC-REP-03** | Reporting | CSV Serialization | Populated DataFrame | Exports valid CSV text matching schema | Valid CSV string generated | **PASS** |

---

## 2. Test Execution Output Log

```text
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\karan\Desktop\Smart-Instrumentation-Monitor
collected 29 items

tests/test_alarm_manager.py::test_threshold_validation PASSED            [  3%]
tests/test_alarm_manager.py::test_high_and_high_high_process_alarms PASSED [  6%]
tests/test_alarm_manager.py::test_alarm_acknowledgement_lifecycle PASSED [ 10%]
tests/test_alarm_manager.py::test_separation_of_electrical_fault_and_process_alarm PASSED [ 13%]
tests/test_fault_detection.py::test_open_circuit_diagnosis PASSED        [ 17%]
tests/test_fault_detection.py::test_stale_measurement_diagnosis PASSED   [ 20%]
tests/test_fault_detection.py::test_sensor_drift_diagnosis PASSED        [ 24%]
tests/test_fault_detection.py::test_noisy_signal_diagnosis PASSED        [ 27%]
tests/test_fault_detection.py::test_simulator_scenarios_and_recovery PASSED [ 31%]
tests/test_reporting.py::test_event_logger_lifecycle PASSED              [ 34%]
tests/test_reporting.py::test_empty_dataframe_generation PASSED          [ 37%]
tests/test_reporting.py::test_reporting_kpi_summary PASSED               [ 41%]
tests/test_reporting.py::test_csv_export_content PASSED                  [ 44%]
tests/test_signal_processing.py::test_conversion_at_4ma PASSED           [ 48%]
tests/test_signal_processing.py::test_conversion_at_12ma PASSED          [ 51%]
tests/test_signal_processing.py::test_conversion_at_20ma PASSED          [ 55%]
tests/test_signal_processing.py::test_inverse_engineering_value_to_current PASSED [ 58%]
tests/test_signal_processing.py::test_negative_range_span PASSED         [ 62%]
tests/test_signal_processing.py::test_invalid_measurement_range_zero_span PASSED [ 65%]
tests/test_signal_processing.py::test_non_finite_range_validation PASSED [ 68%]
tests/test_signal_processing.py::test_open_circuit_detection PASSED      [ 72%]
tests/test_signal_processing.py::test_under_range_detection PASSED       [ 75%]
tests/test_signal_processing.py::test_over_range_detection PASSED        [ 79%]
tests/test_signal_processing.py::test_sensor_failure_high_detection PASSED [ 82%]
tests/test_signal_processing.py::test_invalid_signal_inputs[None] PASSED [ 86%]
tests/test_signal_processing.py::test_invalid_signal_inputs[BAD_DATA] PASSED [ 89%]
tests/test_signal_processing.py::test_invalid_signal_inputs[nan] PASSED  [ 93%]
tests/test_signal_processing.py::test_invalid_signal_inputs[inf] PASSED  [ 96%]
tests/test_signal_processing.py::test_invalid_signal_inputs[-inf] PASSED [100%]

============================= 29 passed in 25.49s =============================
```
