# Smart Process Instrumentation & Fault Diagnosis System

[![Python 3.14](https://img.shields.io/badge/Python-3.14-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.61.0-FF4B4B.svg)](https://streamlit.io/)
[![Pytest Tests](https://img.shields.io/badge/Tests-29%20Passed-brightgreen.svg)](docs/test_plan.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An educational, industrial-grade simulation and supervisory diagnostic application designed for final-year engineering students and Graduate Engineer Trainees (GET) entering instrumentation, process control, operations, and maintenance careers.

> **Disclaimer**: This software is an educational simulation and engineering portfolio project. It uses mathematical models to generate simulated 4–20 mA current signals. It is not certified for plant automation, safety instrumented systems (SIS), or live process control.

---

## 1. Industrial Problem Addressed

In modern process plants (refineries, power stations, chemical processing units, water treatment plants), continuous process monitoring relies heavily on **4–20 mA DC analog current loops**. 

However, real-world operation is fraught with instrumentation anomalies:
- **Loop open circuits / wire breaks**: A severed cable or loose screw terminal drops current to $0.0\text{ mA}$. If a naive control system interprets $0.0\text{ mA}$ as "very low temperature" rather than a sensor failure, automatic heaters may switch on and cause an explosion.
- **Sensor drift & zero shifts**: Chemical fouling, mechanical strain, or thermal aging causes calibration drift, introducing silent errors.
- **Transmitter burnout & saturation**: Transducer internal failures spike the loop above $21.0\text{ mA}$.
- **Stale telemetry**: Communication dropouts or frozen I/O buffers keep values unchanged while physical conditions fluctuate.

This project implements a **transparent, rule-based diagnostic engine** and an **ISA-18.2 compliant alarm management system** that decouples electrical loop health from process variable safety, preventing operator confusion and false control actions.

---

## 2. Key Features

- **Standard 4–20 mA Signal Conversion**: Converts analog current to engineering units using linear span scaling with live zero validation.
- **NAMUR NE 43 Compliance**: Distinguishes normal operation ($3.8 - 20.5\text{ mA}$), under-range ($3.6 - 3.8\text{ mA}$), over-range ($20.5 - 21.0\text{ mA}$), open-circuit ($< 3.6\text{ mA}$), and upscale burnout ($> 21.0\text{ mA}$).
- **Dual Process Instrument Simulation**:
  - `TT-101`: Reactor Core Temperature Transmitter ($0.0$ to $150.0\text{ ^\circ C}$)
  - `PT-101`: Separator Vessel Pressure Transmitter ($0.0$ to $10.0\text{ bar}$)
- **10 Selectable Fault Scenarios**: Normal operation, low process, high process, open circuit, under-range, over-range, stale signal, sensor drift, noisy jitter, and missing telemetry.
- **Rule-Based Diagnostic Guidance**: For every detected abnormality, the system displays observed conditions, probable causes, and practical field inspection checklists (e.g., multimeter checks, terminal inspections, HART communicator trims).
- **ISA-18.2 Alarm Lifecycle**: Supports Low-Low, Low, High, High-High thresholds, alarm priorities, active unacknowledged / acknowledged states, clearing logic, and duplicate suppression.
- **Industrial HMI Dashboard**: A multi-page Streamlit console with dark DCS aesthetics, interactive Plotly trend graphs, and setpoint controls.
- **Audit Logging & Reporting**: In-memory and CSV file-backed event history with instantaneous downloads.
- **29 Automated Tests**: 100% passing pytest suite validating signal math, edge cases, fault classification, and state transitions.

---

## 3. Signal Flow & 4–20 mA Conversion Equation

### The Linear Conversion Equation
Analog transmitters map physical process values linearly onto a $4 - 20\text{ mA}$ current loop. The standard conversion formula is:

$$\text{Engineering Value (PV)} = \text{LRV} + \left(\frac{I_{\text{measured}} - 4.0}{16.0}\right) \times (\text{URV} - \text{LRV})$$

Where:
- $I_{\text{measured}}$: Measured loop current in milliamps ($\text{mA}$).
- $\text{LRV}$: Lower Range Value at $4.0\text{ mA}$ (e.g., $0.0\text{ ^\circ C}$ or $0.0\text{ bar}$).
- $\text{URV}$: Upper Range Value at $20.0\text{ mA}$ (e.g., $150.0\text{ ^\circ C}$ or $10.0\text{ bar}$).
- $\text{Span} = \text{URV} - \text{LRV}$.

### Worked Manual Calculation Example
**Given:**
- Transmitter: `TT-101` (Reactor Temperature)
- $\text{LRV} = 0.0\text{ ^\circ C}$
- $\text{URV} = 150.0\text{ ^\circ C}$
- $\text{Span} = 150.0 - 0.0 = 150.0\text{ ^\circ C}$
- Measured Current: $I = 12.0\text{ mA}$

**Calculation:**
$$\text{Fractional Span} = \frac{12.0 - 4.0}{16.0} = \frac{8.0}{16.0} = 0.50 \text{ (50\%) }$$
$$\text{PV} = 0.0 + (0.50 \times 150.0) = \mathbf{75.0\text{ ^\circ C}}$$

**Under-Range Example ($I = 3.70\text{ mA}$):**
$$\text{Fractional Span} = \frac{3.70 - 4.0}{16.0} = \frac{-0.30}{16.0} = -0.01875$$
$$\text{PV} = 0.0 + (-0.01875 \times 150.0) = \mathbf{-2.81\text{ ^\circ C}}$$
*Result*: While mathematically computable, the system identifies that $3.70\text{ mA}$ is in the NAMUR NE 43 **Under-Range** band ($3.6 - 3.8\text{ mA}$) and raises a maintenance warning for zero calibration drift.

---

## 4. Fault Scenarios and Expected Behaviors

| # | Scenario | Simulated Electrical Signal | Signal Health | Process Value (PV) | Alarm Action | Diagnostic Focus |
|---|---|---|---|---|---|---|
| 1 | **Normal Operation** | $\approx 10.9 - 11.2\text{ mA}$ (nominal $\pm 0.04\text{ mA}$) | Normal | Valid ($65\text{ ^\circ C}$, $4.5\text{ bar}$) | None | Routine preventive maintenance |
| 2 | **Low Process Value** | $\approx 5.6\text{ mA}$ | Normal | Valid ($15\text{ ^\circ C}$ or $0.8\text{ bar}$) | Low / Low-Low Process Alarm | Investigate plant cooling/valves |
| 3 | **High Process Value** | $\approx 18.4\text{ mA}$ | Normal | Valid ($135\text{ ^\circ C}$ or $9.2\text{ bar}$) | High / High-High Process Alarm | Investigate heater/pressure control |
| 4 | **Open Circuit** | $0.0 - 0.5\text{ mA}$ ($< 3.6\text{ mA}$) | Open Circuit | **Unreliable (`None`)** | Critical Signal Alarm | Field terminal check, loop continuity |
| 5 | **Under-Range** | $3.62 - 3.78\text{ mA}$ | Under-Range | Computed ($\text{PV} < \text{LRV}$) | Warning Signal Alarm | Zero-trim calibration with HART |
| 6 | **Over-Range** | $20.55 - 20.95\text{ mA}$ | Over-Range | Computed ($\text{PV} > \text{URV}$) | Warning Signal Alarm | Check process saturation or span |
| 7 | **Stale Measurement** | Current frozen for $\ge 3\text{ steps}$ | Normal loop | Static value | Stale Signal Warning | Communication gateway / LCD check |
| 8 | **Sensor Drift** | Progressive $+0.12\text{ mA}$/step | Normal | Incrementally skewed | Drift Warning | 5-point calibration, check fouling |
| 9 | **Noisy Signal** | High jitter ($\sigma \approx 1.15\text{ mA}$) | Normal | Rapid fluctuation | Advisory Notice | Cable shielding, ground loops, VFDs |
| 10 | **Missing / Invalid** | `None`, `NaN`, string corruption | Invalid | **Unreliable (`None`)** | Critical Telemetry Fault | Modbus frame errors, ADC buffer |

---

## 5. Alarm Prioritization Matrix (ISA-18.2)

1. **CRITICAL Priority (Red / Flashing)**:
   - Wire breaks / open circuit ($< 3.6\text{ mA}$).
   - Upscale sensor failure / short circuit ($> 21.0\text{ mA}$).
   - High-High ($\text{HH}$) and Low-Low ($\text{LL}$) process limits (potential safety interlocks).
   - *Behavior*: Cannot be auto-cleared; requires explicit operator acknowledgement.
2. **WARNING Priority (Amber / Yellow)**:
   - High ($\text{H}$) and Low ($\text{L}$) process warnings.
   - Signal under-range ($3.6 - 3.8\text{ mA}$) and over-range ($20.5 - 21.0\text{ mA}$).
   - Stale telemetry and calibration drift.
3. **ADVISORY Priority (Blue / Gray)**:
   - High signal noise or minor communication packet retries.

---

## 6. Installation & Execution (Windows PowerShell)

### Prerequisites
- Python 3.10+ (Tested and verified on Python 3.14.6)
- Windows PowerShell

### Step-by-Step Setup
1. **Open Windows PowerShell** and navigate to the project directory:
   ```powershell
   cd c:\Users\karan\Desktop\Smart-Instrumentation-Monitor
   ```

2. **Create and Activate an Isolated Virtual Environment (Optional but Recommended)**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install Pinned Dependencies**:
   ```powershell
   python -m pip install -r requirements.txt
   ```

4. **Run the Automated Test Suite**:
   ```powershell
   python -m pytest -v
   ```
   *(Expected output: 29 passed in ~25 seconds)*

5. **Launch the Streamlit HMI Dashboard**:
   ```powershell
   python -m streamlit run app.py
   ```
   The dashboard will automatically open in your default browser at `http://localhost:8501`.

---

## 7. Interactive Demonstration Guide

Follow these steps to demonstrate the major features during an interview or presentation:

1. **Normal Baseline**:
   - Open **A. Overview**. Observe both instruments (`TT-101` and `PT-101`) running healthy with green badges.
   - Click **▶ Step +1s** several times or toggle **Continuous Auto-Tick**.
2. **Demonstrate Open Circuit (Wire Break)**:
   - Navigate to **D. Fault Simulator**.
   - Select `TT-101` and scenario `Open-Circuit Transmitter Signal`. Click **Apply Scenario**.
   - Navigate to **B. Instrument Monitoring**. Observe the current gauge drop below $3.6\text{ mA}$, the red **OPEN_CIRCUIT** status, and the diagnostic card showing field troubleshooting steps (multimeter, junction box terminals).
   - Go to **E. Alarm Management**: Notice a critical `SIGNAL FAULT` alarm is active, while process limits are protected from false firing. Click **Ack** to acknowledge.
3. **Demonstrate High Process Alarm**:
   - Select `PT-101` in the Fault Simulator and inject `High Process Value`.
   - In **C. Trend Analysis**, observe the pressure trace surge past the yellow High limit and red High-High limit.
   - In **E. Alarm Management**, see the process alarm `CRITICAL HIGH PT-101`.
4. **Demonstrate Normal Recovery**:
   - In the sidebar, click **🔄 Reset All**.
   - Observe both instruments return to normal operating setpoints and the alarms transition to cleared.
5. **Download Audit Reports**:
   - Navigate to **F. Reports & Diagnostics**.
   - Click **Download Alarm History (CSV)** to inspect the timestamped audit log.

---

## 8. Graduate Engineer Trainee (GET) Interview Preparation

### Core Concepts & Technical Q&A

#### Q1: Why is 4–20 mA preferred over 0–20 mA or 0–5 V in process industries?
> **Answer**:
> 1. **Live Zero (4 mA)**: Because $4.0\text{ mA}$ corresponds to 0% measurement, any drop to $0.0\text{ mA}$ represents a broken wire, blown fuse, or power outage. A $0 - 20\text{ mA}$ loop cannot distinguish a true zero reading from a dead wire.
> 2. **Immunity to Voltage Drop**: Current in a closed series loop is constant regardless of lead wire resistance over long distances (hundreds of meters).
> 3. **Noise Immunity**: Current signals are far less susceptible to induced electromagnetic interference (EMI) than high-impedance voltage signals.
> 4. **Loop Powering**: Modern 2-wire transmitters consume $< 3.6\text{ mA}$ of quiescent current, allowing transmitter electronics to be powered over the exact same two wires that carry the measurement signal.

#### Q2: What is NAMUR NE 43?
> **Answer**: It is an international standard defining signal levels for failure information of analog transmitters:
> - Normal: $3.8 - 20.5\text{ mA}$
> - Under-range: $3.6 - 3.8\text{ mA}$
> - Over-range: $20.5 - 21.0\text{ mA}$
> - Fault / Wire break: $< 3.6\text{ mA}$
> - Upscale Burnout / Hardware fault: $> 21.0\text{ mA}$

#### Q3: Why should electrical loop faults be decoupled from process alarms?
> **Answer**: If an open circuit occurs on a boiler temperature transmitter ($0.0\text{ mA}$), an un-decoupled control system would interpret this as freezing cold ($< 0\text{ ^\circ C}$) and potentially drive fuel valves to maximum fire. Separating signal health ensures that when a loop fails, the process value is flagged as untrusted, safety interlocks lock in safe state, and the operator receives an instrument maintenance alarm rather than a process temperature alarm.

#### Q4: What is the difference between an unacknowledged alarm and a cleared alarm in ISA-18.2?
> **Answer**: An alarm alerts an operator to an abnormal condition requiring action. If a transient surge causes an alarm that returns to normal before the operator sees it, the alarm transitions to `CLEARED_UNACK` (Cleared Unacknowledged). It remains visible until the operator acknowledges that an excursion occurred.

---

## 9. Simulated vs. Real Industrial Implementation

| Aspect | In this Simulation Project | In a Real Industrial Plant |
|---|---|---|
| **Signal Source** | Python mathematical generator with Gaussian noise and scenario states | Physical RTD, Thermocouple, Piezoresistive diaphragm transducer |
| **Current Loop** | Virtual float numbers in software | 24 VDC loop power supply, 2-wire shielded twisted pair cable (STP) |
| **Digitization** | Direct Python variable assignment | Analog Input (AI) module with 16-bit Sigma-Delta ADC and HART modem |
| **Diagnosis** | Rule-based Python engine | Combination of DCS logic (IEC 61131-3), HART/Fieldbus diagnostic frames, and Asset Management Software (AMS) |
| **Hardware Tools** | Simulated inspection checklists | Fluke 789 ProcessMeter, Beamex Calibrator, Emerson 475/AMS Trex Field Communicator |

---

## 10. Limitations & Future Enhancements

### Limitations
- Uses simulated telemetry rather than physical Modbus TCP/RTU or OPC UA live streams.
- Simplified single-stage Gaussian noise without multi-order plant thermal lag transfer functions.

### Future Enhancements
- Integration of a software Modbus TCP slave server to allow external PLC polling.
- Addition of 3-wire and 4-wire RTD resistance-temperature table lookups (PT100 DIN 43760).
- Automatic generation of instrument calibration certificates in PDF format.