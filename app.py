"""
Smart Process Instrumentation & Fault Diagnosis System
Main Application: app.py

Industrial HMI & Supervisory Control Dashboard for Process Instrumentation:
- Real-time 4-20 mA loop monitoring (TT-101, PT-101)
- NAMUR NE 43 electrical health detection
- 10 interactive fault injection scenarios
- ISA-18.2 compliant alarm management & operator acknowledgement
- Interactive Plotly dynamic trends with threshold bands
- Audit trail event logging & CSV reporting
"""

import os
import sys
import time
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.alarm_manager import AlarmPriority, AlarmState, AlarmThresholds, validate_thresholds
from src.event_logger import EventLogger
from src.fault_detection import FaultSeverity
from src.reporting import (
    export_dataframe_to_csv_string,
    generate_alarm_history_dataframe,
    generate_event_history_dataframe,
    generate_kpi_summary,
)
from src.signal_processing import SignalStatus
from src.simulator import FaultScenario, ProcessSimulator

# --- Page Configuration ---
st.set_page_config(
    page_title="Smart Process Instrumentation & Fault Diagnosis System",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom Industrial HMI CSS Styling ---
st.markdown("""
<style>
    /* Dark Industrial DCS Palette */
    .main {
        background-color: #0e1726;
        color: #e2e8f0;
    }
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        margin-bottom: 12px;
    }
    .metric-title {
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f8fafc;
        font-family: 'Courier New', monospace;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #64748b;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
    }
    .badge-normal { background-color: #065f46; color: #34d399; border: 1px solid #059669; }
    .badge-warning { background-color: #78350f; color: #fbbf24; border: 1px solid #d97706; }
    .badge-critical { background-color: #7f1d1d; color: #f87171; border: 1px solid #dc2626; animation: blinker 1.5s linear infinite; }
    .badge-advisory { background-color: #1e3a8a; color: #60a5fa; border: 1px solid #2563eb; }
    
    @keyframes blinker {
        50% { opacity: 0.4; }
    }
    .disclaimer-banner {
        background-color: #1e293b;
        border-left: 4px solid #38bdf8;
        padding: 10px 14px;
        font-size: 0.85rem;
        color: #cbd5e1;
        margin-bottom: 16px;
        border-radius: 0 6px 6px 0;
    }
</style>
""", unsafe_allow_html=True)


# --- State Initialization ---
def get_simulator() -> ProcessSimulator:
    if "simulator" not in st.session_state:
        sim = ProcessSimulator(random_seed=42)
        # Prime the simulation with initial normal steps
        for _ in range(15):
            sim.step()
        st.session_state.simulator = sim
    return st.session_state.simulator


def get_logger() -> EventLogger:
    if "logger" not in st.session_state:
        st.session_state.logger = EventLogger()
    return st.session_state.logger


simulator = get_simulator()
logger = get_logger()

if "auto_advance" not in st.session_state:
    st.session_state.auto_advance = False

# --- Top Industrial Header Banner ---
st.markdown("""
<div class="disclaimer-banner">
    <strong>INDUSTRIAL DEMONSTRATOR / EDUCATIONAL SIMULATION:</strong>
    All measurements (TT-101, PT-101) are mathematically simulated 4–20 mA loops for technician training,
    fault diagnosis, and alarm analysis. Not certified for plant control or safety instrumented systems.
</div>
""", unsafe_allow_html=True)

# --- Sidebar Controls ---
st.sidebar.title("🏭 Plant DCS Console")
st.sidebar.markdown("**Smart Process Instrumentation**")

page_selection = st.sidebar.radio(
    "Navigation Menu",
    [
        "A. Overview",
        "B. Instrument Monitoring",
        "C. Trend Analysis",
        "D. Fault Simulator",
        "E. Alarm Management",
        "F. Reports & Diagnostics"
    ]
)

st.sidebar.markdown("---")
st.sidebar.subheader("⚡ Simulation Control")

col_s1, col_s2 = st.sidebar.columns(2)
with col_s1:
    if st.button("▶ Step +1s", use_container_width=True):
        snaps = simulator.step()
        # Log active faults or alarms
        for tag, s in snaps.items():
            if s.signal_status != SignalStatus.NORMAL:
                logger.log_event(
                    instrument_tag=tag,
                    category="SIGNAL",
                    severity=s.diagnostic.severity.value,
                    event_type=s.signal_status.value,
                    message=s.diagnostic.fault_name,
                    details=s.diagnostic.observed_condition
                )
            for alm in s.active_alarms:
                logger.log_event(
                    instrument_tag=tag,
                    category="ALARM",
                    severity="WARNING" if "HIGH" in alm or "LOW" in alm else "CRITICAL",
                    event_type="ALARM_ACTIVE",
                    message=alm
                )
        st.rerun()

with col_s2:
    if st.button("🔄 Reset All", use_container_width=True):
        simulator.reset_all()
        logger.log_event(
            instrument_tag="ALL",
            category="OPERATOR",
            severity="INFO",
            event_type="SYSTEM_RESET",
            message="Operator reset all instruments to Normal Operation."
        )
        st.rerun()

auto_run = st.sidebar.checkbox("🔁 Continuous Auto-Tick (2s)", value=st.session_state.auto_advance)
if auto_run != st.session_state.auto_advance:
    st.session_state.auto_advance = auto_run
    st.rerun()

st.sidebar.markdown(f"**Simulation Time:** `{simulator.current_sim_time.strftime('%H:%M:%S')}`")
st.sidebar.markdown(f"**Total Buffer Samples:** `{len(simulator.history)}`")

# Auto-advance execution hook
if st.session_state.auto_advance:
    time.sleep(2.0)
    snaps = simulator.step()
    st.rerun()

# Fetch latest snapshot by running a step if empty
if not simulator.history:
    simulator.step()

latest_snaps = {}
for tag in simulator.configs:
    last_hist = simulator.history[-1]
    cfg = simulator.configs[tag]
    # Re-evaluate snapshot attributes
    diag = simulator.alarm_manager
    pv_key = f"{tag.replace('-', '_')}_pv"
    ma_key = f"{tag.replace('-', '_')}_ma"
    status_key = f"{tag.replace('-', '_')}_status"

    cur_ma = last_hist.get(ma_key)
    pv_val = last_hist.get(pv_key)
    stat_val = SignalStatus(last_hist.get(status_key, "NORMAL"))

    latest_snaps[tag] = {
        "tag": tag,
        "description": cfg.description,
        "ma": cur_ma,
        "pv": pv_val,
        "units": cfg.units,
        "status": stat_val,
        "lrv": cfg.lrv,
        "urv": cfg.urv,
        "scenario": simulator.active_scenarios[tag]
    }


# ==========================================
# PAGE A: OVERVIEW
# ==========================================
if page_selection == "A. Overview":
    st.header("📊 Instrumentation Overview & Plant Status")

    active_alarms = simulator.alarm_manager.get_active_alarms()
    p_counts = simulator.alarm_manager.get_active_count_by_priority()

    # KPI Top Bar
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Critical Alarms</div>
            <div class="metric-value" style="color: {'#f87171' if p_counts['CRITICAL'] > 0 else '#34d399'};">
                {p_counts['CRITICAL']}
            </div>
            <div class="metric-sub">Immediate action required</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Warning Alarms</div>
            <div class="metric-value" style="color: {'#fbbf24' if p_counts['WARNING'] > 0 else '#94a3b8'};">
                {p_counts['WARNING']}
            </div>
            <div class="metric-sub">Process / Loop deviations</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">TT-101 Temperature</div>
            <div class="metric-value">
                {f"{latest_snaps['TT-101']['pv']:.1f} °C" if latest_snaps['TT-101']['pv'] is not None else "FAULT"}
            </div>
            <div class="metric-sub">Loop: {f"{latest_snaps['TT-101']['ma']:.2f} mA" if latest_snaps['TT-101']['ma'] is not None else "N/A"}</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">PT-101 Pressure</div>
            <div class="metric-value">
                {f"{latest_snaps['PT-101']['pv']:.2f} bar" if latest_snaps['PT-101']['pv'] is not None else "FAULT"}
            </div>
            <div class="metric-sub">Loop: {f"{latest_snaps['PT-101']['ma']:.2f} mA" if latest_snaps['PT-101']['ma'] is not None else "N/A"}</div>
        </div>
        """, unsafe_allow_html=True)

    st.subheader("📡 Instrument Live Health Summary")
    inst_cols = st.columns(2)
    for idx, (tag, snap) in enumerate(latest_snaps.items()):
        with inst_cols[idx]:
            badge_class = "badge-normal"
            if snap["status"] in (SignalStatus.OPEN_CIRCUIT, SignalStatus.SENSOR_FAILURE_HIGH, SignalStatus.INVALID):
                badge_class = "badge-critical"
            elif snap["status"] in (SignalStatus.UNDER_RANGE, SignalStatus.OVER_RANGE):
                badge_class = "badge-warning"

            st.markdown(f"""
            <div class="metric-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 700; font-size: 1.1rem; color: #38bdf8;">{tag} - {snap['description']}</span>
                    <span class="status-badge {badge_class}">{snap['status'].value}</span>
                </div>
                <hr style="border-color: #334155; margin: 8px 0;"/>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.9rem;">
                    <div><strong>Calibrated Span:</strong> {snap['lrv']} to {snap['urv']} {snap['units']}</div>
                    <div><strong>Active Scenario:</strong> <code>{snap['scenario'].value}</code></div>
                    <div><strong>Loop Current:</strong> {f"{snap['ma']:.2f} mA" if snap['ma'] is not None else "INVALID"}</div>
                    <div><strong>Process Value:</strong> {f"{snap['pv']:.2f} {snap['units']}" if snap['pv'] is not None else "UNRELIABLE"}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.subheader("🕒 Recent Event Audit Trail")
    events = logger.get_events(limit=8)
    df_events = generate_event_history_dataframe(events)
    if not df_events.empty:
        st.dataframe(df_events, use_container_width=True, hide_index=True)
    else:
        st.info("No events logged yet. Advance the simulation or trigger a scenario to log events.")


# ==========================================
# PAGE B: INSTRUMENT MONITORING
# ==========================================
elif page_selection == "B. Instrument Monitoring":
    st.header("🔍 Transmitter Signal & Diagnostic Inspector")

    selected_tag = st.selectbox("Select Transmitter Channel", list(simulator.configs.keys()))
    cfg = simulator.configs[selected_tag]
    snap = latest_snaps[selected_tag]
    th = simulator.thresholds[selected_tag]

    col_m1, col_m2 = st.columns([1, 1])

    with col_m1:
        st.markdown(f"### ⚡ Electrical Loop Integrity ({selected_tag})")
        st.markdown(f"**Measurement Principle:** 4–20 mA DC Analog Current Loop (Linear)")
        st.markdown(f"**Lower Range Value (4.0 mA):** `{cfg.lrv} {cfg.units}`")
        st.markdown(f"**Upper Range Value (20.0 mA):** `{cfg.urv} {cfg.units}`")
        st.markdown(f"**Calibrated Span:** `{cfg.urv - cfg.lrv} {cfg.units}`")

        # Gauge chart using Plotly
        cur_val = snap["ma"] if snap["ma"] is not None else 0.0
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=cur_val,
            title={'text': f"{selected_tag} Loop Current (mA)", 'font': {'size': 18, 'color': '#f8fafc'}},
            number={'suffix': " mA", 'font': {'color': '#38bdf8'}},
            gauge={
                'axis': {'range': [0, 24], 'tickwidth': 1, 'tickcolor': "#94a3b8"},
                'bar': {'color': "#38bdf8"},
                'bgcolor': "#1e293b",
                'borderwidth': 2,
                'bordercolor': "#334155",
                'steps': [
                    {'range': [0, 3.6], 'color': 'rgba(239, 68, 68, 0.4)'},     # Open circuit
                    {'range': [3.6, 3.8], 'color': 'rgba(245, 158, 11, 0.4)'},  # Under range
                    {'range': [3.8, 20.5], 'color': 'rgba(16, 185, 129, 0.2)'}, # Normal operating band
                    {'range': [20.5, 21.0], 'color': 'rgba(245, 158, 11, 0.4)'}, # Over range
                    {'range': [21.0, 24.0], 'color': 'rgba(239, 68, 68, 0.4)'}, # Burnout / Short
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 21.0
                }
            }
        ))
        fig_gauge.update_layout(paper_bgcolor="#0e1726", font={'color': "#f8fafc"}, height=280, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col_m2:
        st.markdown(f"### 🌡️ Process Variable Status")
        if snap["pv"] is not None:
            st.metric(
                label=f"Current Process Reading ({cfg.description})",
                value=f"{snap['pv']:.2f} {cfg.units}",
                delta=f"{(snap['pv'] - simulator.nominal_pvs[selected_tag]):+.2f} {cfg.units} from nominal"
            )
        else:
            st.error("PROCESS VALUE INVALID: Electrical signal integrity failure. Loop current untrusted.")

        st.markdown("#### Configured Alarm Limit Setpoints")
        st.markdown(f"- **Low-Low (Critical):** `{th.low_low} {cfg.units}`")
        st.markdown(f"- **Low (Warning):** `{th.low} {cfg.units}`")
        st.markdown(f"- **High (Warning):** `{th.high} {cfg.units}`")
        st.markdown(f"- **High-High (Critical):** `{th.high_high} {cfg.units}`")

    # Diagnostic Recommendation Panel
    st.markdown("### 📋 Rule-Based Fault Diagnosis & Troubleshooting Guide")
    sim_snaps = simulator.step()
    cur_diag = sim_snaps[selected_tag].diagnostic

    diag_color = "#34d399" if cur_diag.severity == FaultSeverity.NORMAL else (
        "#f87171" if cur_diag.severity == FaultSeverity.CRITICAL else "#fbbf24"
    )

    st.markdown(f"""
    <div style="border-left: 5px solid {diag_color}; background-color: #1e293b; padding: 14px 18px; border-radius: 4px; margin-top: 10px;">
        <h4 style="margin: 0 0 6px 0; color: {diag_color};">{cur_diag.fault_name} [{cur_diag.severity.value}]</h4>
        <p><strong>Observed Symptom:</strong> {cur_diag.observed_condition}</p>
        <p><strong>Heuristic Potential Causes:</strong></p>
        <ul>
            {"".join(f"<li>{c}</li>" for c in cur_diag.possible_causes)}
        </ul>
        <p><strong>Suggested Field Inspection Routine:</strong></p>
        <ol>
            {"".join(f"<li>{step}</li>" for step in cur_diag.suggested_inspection_steps)}
        </ol>
        <p style="font-size: 0.8rem; color: #94a3b8; font-style: italic; margin-top: 8px;">
            ⚠️ Notice: Troubleshooting suggestions represent heuristic engineering guidance, not definitive proof of hardware component failure.
        </p>
    </div>
    """, unsafe_allow_html=True)


# ==========================================
# PAGE C: TREND ANALYSIS
# ==========================================
elif page_selection == "C. Trend Analysis":
    st.header("📈 Dynamic Process History & Threshold Analysis")
    st.markdown("Interactive historical trend inspection with ISA-18.2 threshold limits.")

    history_df = pd.DataFrame(simulator.history)

    if not history_df.empty and "timestamp" in history_df.columns:
        window_size = st.slider("Historical View Window (Samples)", min_value=10, max_value=300, value=60)
        plot_df = history_df.tail(window_size)

        tab_tt, tab_pt = st.tabs(["TT-101 (Temperature)", "PT-101 (Pressure)"])

        with tab_tt:
            fig_tt = go.Figure()
            th_tt = simulator.thresholds["TT-101"]

            # Process Value Line
            fig_tt.add_trace(go.Scatter(
                x=plot_df["timestamp"], y=plot_df["TT_101_pv"],
                mode="lines+markers", name="TT-101 PV (°C)",
                line=dict(color="#38bdf8", width=2.5)
            ))

            # Threshold Limit Lines
            if th_tt.high_high:
                fig_tt.add_hline(y=th_tt.high_high, line_dash="dash", line_color="#ef4444", annotation_text="High-High Limit")
            if th_tt.high:
                fig_tt.add_hline(y=th_tt.high, line_dash="dot", line_color="#f59e0b", annotation_text="High Warning")
            if th_tt.low:
                fig_tt.add_hline(y=th_tt.low, line_dash="dot", line_color="#f59e0b", annotation_text="Low Warning")
            if th_tt.low_low:
                fig_tt.add_hline(y=th_tt.low_low, line_dash="dash", line_color="#ef4444", annotation_text="Low-Low Limit")

            fig_tt.update_layout(
                title="TT-101 Reactor Temperature Trend (°C)",
                xaxis_title="Simulation Time", yaxis_title="Temperature (°C)",
                template="plotly_dark", height=420,
                paper_bgcolor="#0e1726", plot_bgcolor="#1e293b"
            )
            st.plotly_chart(fig_tt, use_container_width=True)

        with tab_pt:
            fig_pt = go.Figure()
            th_pt = simulator.thresholds["PT-101"]

            fig_pt.add_trace(go.Scatter(
                x=plot_df["timestamp"], y=plot_df["PT_101_pv"],
                mode="lines+markers", name="PT-101 PV (bar)",
                line=dict(color="#34d399", width=2.5)
            ))

            if th_pt.high_high:
                fig_pt.add_hline(y=th_pt.high_high, line_dash="dash", line_color="#ef4444", annotation_text="High-High Limit")
            if th_pt.high:
                fig_pt.add_hline(y=th_pt.high, line_dash="dot", line_color="#f59e0b", annotation_text="High Warning")
            if th_pt.low:
                fig_pt.add_hline(y=th_pt.low, line_dash="dot", line_color="#f59e0b", annotation_text="Low Warning")
            if th_pt.low_low:
                fig_pt.add_hline(y=th_pt.low_low, line_dash="dash", line_color="#ef4444", annotation_text="Low-Low Limit")

            fig_pt.update_layout(
                title="PT-101 Separator Pressure Trend (bar)",
                xaxis_title="Simulation Time", yaxis_title="Pressure (bar)",
                template="plotly_dark", height=420,
                paper_bgcolor="#0e1726", plot_bgcolor="#1e293b"
            )
            st.plotly_chart(fig_pt, use_container_width=True)
    else:
        st.warning("Insufficient historical data. Advance simulation steps to populate trend graphs.")


# ==========================================
# PAGE D: FAULT SIMULATOR
# ==========================================
elif page_selection == "D. Fault Simulator":
    st.header("🧪 Industrial Fault Injection Studio")
    st.markdown("Inject realistic field defects and observe NAMUR NE 43 loop behavior and alarm dynamics.")

    col_f1, col_f2 = st.columns([1, 1])

    with col_f1:
        st.subheader("1. Target Transmitter & Fault Selection")
        target_inst = st.selectbox("Select Target Instrument", ["TT-101", "PT-101"])
        scenario_names = [s.value for s in FaultScenario]
        cur_scenario = simulator.active_scenarios[target_inst]
        selected_scenario_name = st.selectbox(
            "Select Fault Injection Scenario",
            scenario_names,
            index=scenario_names.index(cur_scenario.value)
        )
        selected_scenario = FaultScenario(selected_scenario_name)

        if st.button("🚨 Apply Scenario to Instrument", use_container_width=True):
            simulator.set_scenario(target_inst, selected_scenario)
            logger.log_event(
                instrument_tag=target_inst,
                category="OPERATOR",
                severity="WARNING" if selected_scenario != FaultScenario.NORMAL_OPERATION else "INFO",
                event_type="SCENARIO_INJECTED",
                message=f"Operator activated scenario: {selected_scenario.value}"
            )
            st.success(f"Scenario '{selected_scenario.value}' applied to {target_inst}!")
            st.rerun()

    with col_f2:
        st.subheader("2. Scenario Description & Technical Physics")
        descriptions = {
            FaultScenario.NORMAL_OPERATION: "Healthy 4-20 mA loop operating near nominal setpoint with standard white noise.",
            FaultScenario.LOW_PROCESS_VALUE: "Physical variable dips below Low process threshold, while transmitter loop is healthy (> 3.8 mA).",
            FaultScenario.HIGH_PROCESS_VALUE: "Physical variable surges above High-High threshold, while transmitter loop is healthy (< 20.5 mA).",
            FaultScenario.OPEN_CIRCUIT: "Loop cable break, loose terminal, or loss of 24 VDC. Measured current collapses to ~0.0 mA (< 3.6 mA).",
            FaultScenario.UNDER_RANGE: "Zero calibration drift or negative process depression. Current is between 3.60 mA and 3.80 mA.",
            FaultScenario.OVER_RANGE: "Sensor saturation or positive span calibration error. Current is between 20.50 mA and 21.00 mA.",
            FaultScenario.STALE_MEASUREMENT: "Sensor or communication gateway frozen. Signal does not change across consecutive time steps.",
            FaultScenario.GRADUAL_SENSOR_DRIFT: "Aging diaphragm or fouled thermowell causing cumulative +0.12 mA drift per time step.",
            FaultScenario.NOISY_SIGNAL: "Electromagnetic interference (EMI) or pump cavitation creating excessive high-frequency jitter.",
            FaultScenario.INVALID_MISSING: "Modbus/OPC communication frame dropped, corrupted, or transmitting null/NaN packets."
        }
        st.info(descriptions[selected_scenario])

    st.markdown("---")
    st.subheader("3. Interactive Setpoint & Threshold Reconfiguration")
    col_th1, col_th2 = st.columns(2)

    with col_th1:
        st.markdown(f"**Configure {target_inst} Alarm Setpoints**")
        cur_th = simulator.thresholds[target_inst]
        cfg = simulator.configs[target_inst]

        new_ll = st.number_input(f"Low-Low Limit ({cfg.units})", value=float(cur_th.low_low or cfg.lrv))
        new_l = st.number_input(f"Low Limit ({cfg.units})", value=float(cur_th.low or cfg.lrv + 10))
        new_h = st.number_input(f"High Limit ({cfg.units})", value=float(cur_th.high or cfg.urv - 15))
        new_hh = st.number_input(f"High-High Limit ({cfg.units})", value=float(cur_th.high_high or cfg.urv))

        if st.button("💾 Save Threshold Configuration"):
            candidate_th = AlarmThresholds(low_low=new_ll, low=new_l, high=new_h, high_high=new_hh)
            valid, msg = validate_thresholds(candidate_th, cfg.lrv, cfg.urv)
            if valid:
                simulator.thresholds[target_inst] = candidate_th
                logger.log_event(
                    instrument_tag=target_inst,
                    category="OPERATOR",
                    severity="INFO",
                    event_type="CONFIG_UPDATE",
                    message=f"Alarm thresholds updated for {target_inst}."
                )
                st.success("Thresholds saved successfully!")
            else:
                st.error(f"Configuration Rejected: {msg}")

    with col_th2:
        st.markdown(f"**Configure Nominal Baseline Value**")
        cur_nom = simulator.nominal_pvs[target_inst]
        new_nom = st.number_input(f"Baseline Normal PV ({cfg.units})", value=float(cur_nom), min_value=float(cfg.lrv), max_value=float(cfg.urv))
        if st.button("💾 Update Nominal Setpoint"):
            simulator.nominal_pvs[target_inst] = new_nom
            st.success(f"Nominal operating point for {target_inst} set to {new_nom} {cfg.units}!")


# ==========================================
# PAGE E: ALARM MANAGEMENT
# ==========================================
elif page_selection == "E. Alarm Management":
    st.header("🚨 ISA-18.2 Alarm Summary & Operator Console")

    active_alarms = simulator.alarm_manager.get_active_alarms()
    history_alarms = simulator.alarm_manager.alarm_history

    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        if st.button("🔔 Acknowledge All", use_container_width=True):
            ack_count = simulator.alarm_manager.acknowledge_all()
            logger.log_event(
                instrument_tag="ALL",
                category="OPERATOR",
                severity="INFO",
                event_type="ALARMS_ACKNOWLEDGED",
                message=f"Operator acknowledged {ack_count} active alarm(s)."
            )
            st.success(f"Acknowledged {ack_count} alarm(s).")
            st.rerun()

    st.subheader(f"Active Alarms ({len(active_alarms)})")
    if active_alarms:
        for alm in active_alarms:
            col_a1, col_a2, col_a3 = st.columns([2, 5, 2])
            with col_a1:
                badge = "badge-critical" if alm.priority == AlarmPriority.CRITICAL else "badge-warning"
                st.markdown(f"<span class='status-badge {badge}'>{alm.priority.value}</span> **{alm.alarm_id}**", unsafe_allow_html=True)
                st.caption(f"Tag: {alm.instrument_tag} | State: `{alm.state.value}`")
            with col_a2:
                st.markdown(f"**{alm.description}**")
                st.caption(f"Triggered: {alm.activation_time} | Value: {alm.trigger_value} {alm.units}")
            with col_a3:
                if alm.state == AlarmState.ACTIVE_UNACK:
                    if st.button(f"Ack {alm.alarm_id}", key=f"ack_{alm.alarm_id}"):
                        simulator.alarm_manager.acknowledge_alarm(alm.alarm_id)
                        logger.log_event(
                            instrument_tag=alm.instrument_tag,
                            category="OPERATOR",
                            severity="INFO",
                            event_type="ALARM_ACK",
                            message=f"Acknowledged alarm {alm.alarm_id}"
                        )
                        st.rerun()
                else:
                    st.markdown("✅ *Acknowledged*")
            st.divider()
    else:
        st.success("✅ Clean Panel: No active unacknowledged or critical alarms.")

    st.subheader("📜 Historical Alarm Log")
    df_all_alarms = generate_alarm_history_dataframe(history_alarms)
    if not df_all_alarms.empty:
        # Filter options
        filter_tag = st.selectbox("Filter by Tag", ["ALL"] + list(simulator.configs.keys()))
        if filter_tag != "ALL":
            df_all_alarms = df_all_alarms[df_all_alarms["Instrument Tag"] == filter_tag]
        st.dataframe(df_all_alarms, use_container_width=True, hide_index=True)
    else:
        st.info("No alarm history recorded yet.")


# ==========================================
# PAGE F: REPORTS & DIAGNOSTICS
# ==========================================
elif page_selection == "F. Reports & Diagnostics":
    st.header("📑 Operations & Maintenance Reporting Center")

    kpis = generate_kpi_summary(
        alarm_history=simulator.alarm_manager.alarm_history,
        active_alarms=simulator.alarm_manager.get_active_alarms(),
        history_records=simulator.history
    )

    st.subheader("📈 Plant Telemetry KPIs")
    kp1, kp2, kp3, kp4 = st.columns(4)
    kp1.metric("Total Alarms Logged", kpis["total_alarm_events_logged"])
    kp2.metric("Active Alarms", kpis["active_alarms_count"])
    kp3.metric("Critical Active", kpis["critical_active"])
    kp4.metric("Total Telemetry Ticks", kpis["total_telemetry_ticks"])

    st.markdown("---")
    st.subheader("📥 Data Export Center (CSV)")
    c_exp1, c_exp2 = st.columns(2)

    with c_exp1:
        st.markdown("#### Alarm Audit Trail")
        df_alarms = generate_alarm_history_dataframe(simulator.alarm_manager.alarm_history)
        csv_alarms = export_dataframe_to_csv_string(df_alarms)
        st.download_button(
            label="⬇️ Download Alarm History (CSV)",
            data=csv_alarms,
            file_name=f"alarm_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with c_exp2:
        st.markdown("#### System Event History")
        df_events = generate_event_history_dataframe(logger.get_events())
        csv_events = export_dataframe_to_csv_string(df_events)
        st.download_button(
            label="⬇️ Download Event Audit Log (CSV)",
            data=csv_events,
            file_name=f"event_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    st.markdown("---")
    st.subheader("🧪 Run Automated Diagnostic Test Suite")
    if st.button("🚀 Execute Pytest Suite from Web UI"):
        with st.spinner("Running automated test suite..."):
            import subprocess
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-v", "--tb=short"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                st.success("All automated test cases passed successfully!")
            else:
                st.error("Some automated tests failed.")
            st.code(result.stdout if result.stdout else result.stderr)
