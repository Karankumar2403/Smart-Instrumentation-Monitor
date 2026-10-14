# System Architecture: Smart Process Instrumentation & Fault Diagnosis System

This document outlines the architectural blueprint, data flow, diagnostic decision model, and alarm state machine implemented in the **Smart Process Instrumentation & Fault Diagnosis System**.

---

## 1. High-Level System Architecture

The architecture separates physical process modeling, 4–20 mA current loop conversion, signal health evaluation, rule-based diagnostics, ISA-18.2 alarm management, and the user-facing Streamlit Industrial HMI.

```mermaid
flowchart TD
    subgraph SENSORS ["Simulated Instrumentation Layer"]
        TT["TT-101: Reactor Core Temp (0-150 °C)"]
        PT["PT-101: Separator Pressure (0-10 bar)"]
        INJECTOR["Fault Injection Engine (10 Scenarios)"]
        INJECTOR --> TT
        INJECTOR --> PT
    end

    subgraph SIGNAL_PROC ["Signal Conditioning Layer (NAMUR NE 43)"]
        RAW_I["Analog Loop Current: 4-20 mA"]
        HEALTH_CHECK{"Electrical Health Validation"}
        CONV["Linear Engineering Value Conversion"]
        RAW_I --> HEALTH_CHECK
        HEALTH_CHECK -->|"Valid (3.8-20.5 mA)"| CONV
        HEALTH_CHECK -->|"Fault (<3.6, >21.0, Null)"| FAULT_FLAG["Flag Signal Fault & Suppress PV"]
    end

    subgraph DIAGNOSTICS ["Transparent Rule-Based Diagnostic Engine"]
        RULES["Root Cause Rule Evaluator"]
        RECOMMEND["Investigation & Troubleshooting Guidance"]
        RULES --> RECOMMEND
    end

    subgraph ALARM_SYS ["Alarm Management Layer (ISA-18.2)"]
        LL_HH{"Threshold Bounds (LL, L, H, HH)"}
        STATE_MACHINE["Alarm State Machine (UNACK / ACK / CLEARED)"]
        DEDUP["Chattering & Duplicate Suppression"]
        LL_HH --> STATE_MACHINE
        STATE_MACHINE --> DEDUP
    end

    subgraph PRESENTATION ["Industrial DCS / HMI (Streamlit)"]
        HMI_DASH["Interactive Plant HMI Dashboard"]
        TRENDS["Plotly Real-time Dynamic Trends"]
        CONSOLE["Operator Alarm Console"]
        EXPORTS["CSV Audit & Compliance Reports"]
    end

    TT --> RAW_I
    PT --> RAW_I
    CONV --> LL_HH
    FAULT_FLAG --> RULES
    CONV --> RULES
    STATE_MACHINE --> HMI_DASH
    STATE_MACHINE --> CONSOLE
    RECOMMEND --> HMI_DASH
    DEDUP --> EXPORTS
    CONV --> TRENDS
```

---

## 2. 4–20 mA Signal Flow & NAMUR NE 43 Partitioning

Industrial analog current loops represent process parameters between $4.0\text{ mA}$ (0% of span) and $20.0\text{ mA}$ (100% of span). The system implements standard NAMUR NE 43 boundary thresholds to distinguish normal process excursions from electrical failures.

```mermaid
stateDiagram-v2
    [*] --> EvaluatingLoopCurrent

    EvaluatingLoopCurrent --> OpenCircuit : Current < 3.60 mA
    EvaluatingLoopCurrent --> UnderRange : 3.60 mA <= Current < 3.80 mA
    EvaluatingLoopCurrent --> NormalLoop : 3.80 mA <= Current <= 20.50 mA
    EvaluatingLoopCurrent --> OverRange : 20.50 mA < Current <= 21.00 mA
    EvaluatingLoopCurrent --> BurnoutHigh : Current > 21.00 mA
    EvaluatingLoopCurrent --> CorruptedTelemetry : Non-numeric / NaN / Null

    OpenCircuit --> SuppressProcessAlarms : Wire break / 24V DC loss
    BurnoutHigh --> SuppressProcessAlarms : Hardware short / upscale burnout
    CorruptedTelemetry --> SuppressProcessAlarms : Communication parity failure

    NormalLoop --> CalculatePV : PV = LRV + ((I-4)/16)*(URV-LRV)
    UnderRange --> CalculatePV : Flag Under-Range Warning
    OverRange --> CalculatePV : Flag Over-Range Warning
```

---

## 3. Alarm State Machine (ISA-18.2 Compliant)

Process alarms follow a standardized lifecycle that prevents alarm flooding, requires explicit operator acknowledgement, and tracks resolution:

```mermaid
stateDiagram-v2
    [*] --> NormalCondition

    NormalCondition --> ACTIVE_UNACK : Threshold Exceeded (LL, L, H, HH)
    ACTIVE_UNACK --> ACTIVE_ACK : Operator Acknowledges
    ACTIVE_ACK --> CLEARED : Condition Returns to Normal
    ACTIVE_UNACK --> CLEARED_UNACK : Condition Returns to Normal (Unacknowledged)
    CLEARED_UNACK --> CLEARED : Operator Acknowledges Past Event
    CLEARED --> [*]
```

### Key Principles Enforced:
1. **Critical Alarms Never Auto-Hide**: Active critical process and electrical faults remain visible in the operator queue until acknowledged.
2. **Duplicate Suppression**: Re-evaluating an active threshold during recurring UI renders updates the current value without spamming the audit log with redundant alarms.
3. **Decoupled Electrical vs. Process Alarms**: If a loop fails (e.g., open circuit at $0.0\text{ mA}$), a **SIGNAL FAULT** alarm is raised, while the process value is marked untrusted, preventing false low-temperature or low-pressure alarms.
