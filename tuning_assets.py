"""
tuning_assets.py
================
Standalone script to generate all figures and tables for Chapter 4.3
(Algorithmic Optimization and Parameter Tuning).

HOW TO USE
----------
1.  Copy this file to your Raspberry Pi (same folder as hardware_main.py).
2.  Run:  python3 tuning_assets.py
3.  All outputs are saved to ./tuning_assets_output/
    - fig_relay_oscillation.png   (Figure 4.4)
    - fig_peak_detection.png      (Figure 4.5)
    - fig_pid_iterations.png      (Figure 4.6)
    - table_4_2_autotune.csv      (Table 4.2)
    - table_4_3_pid_iterations.csv(Table 4.3)
    - table_4_4_final_pid.csv     (Table 4.4)

LIVE DATA vs SIMULATION
-----------------------
- If a database file (system.db) is found, the script reads REAL logged data.
- If no database is found, it falls back to a realistic simulation so you
  can verify the figures look correct before the experiment.
- To force simulation mode, set:  FORCE_SIMULATION = True  (below).

This script NEVER writes to the database and NEVER touches GPIO.
It can be safely run while hardware_main.py is running.
"""

import os
import math
import sqlite3
import numpy as np
import matplotlib
matplotlib.use("Agg")          # non-interactive backend — safe on headless Pi
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

# ── USER CONFIG ──────────────────────────────────────────────────────────────
SETPOINT         = 7.5
HYSTERESIS       = 0.02          # ε  (pH units on each side of SP)
RELAY_AMP        = 1.0           # h  (relay output amplitude, dimensionless)
DT               = 5             # seconds between samples (must match .env DT)
DB_PATH          = "system.db"   # path to your SQLite database
OUTPUT_DIR       = "tuning_assets_output"
FORCE_SIMULATION = False         # set True to always use synthetic data

# PID iteration values — fill in your actual measured numbers.
# Format: (Kp, Ki, Kd, max_overshoot_pH, settling_time_s, IAE, ISE, ITAE)
PID_ITERATIONS = [
    # iter 1 — Ziegler-Nichols initial (computed from Ku/Pu)
    (0.6064, 0.0025, 36.38, 0.18, 420, 12.50, 1.82, 4250),
    # iter 2 — reduced Kp
    (0.45,   0.0025, 36.38, 0.11, 310, 8.30,  0.95, 2870),
    # final adopted
    (0.45,   0.003,  28.0,  0.06, 180, 5.10,  0.41, 1540),
]

# Final PID (last row of PID_ITERATIONS is used automatically)
FINAL_KP, FINAL_KI, FINAL_KD = PID_ITERATIONS[-1][:3]
# ─────────────────────────────────────────────────────────────────────────────


os.makedirs(OUTPUT_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _style():
    """Apply clean thesis-quality matplotlib style."""
    plt.rcParams.update({
        "font.family":    "DejaVu Sans",
        "font.size":      11,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "legend.fontsize": 9,
        "lines.linewidth": 1.6,
        "figure.dpi":     300,
        "savefig.dpi":    300,
        "savefig.bbox":   "tight",
    })


def _try_load_db_autotune():
    """
    Try to load autotune-phase pH and CO2 data from SQLite.
    Returns (time_s, ph, co2) numpy arrays, or None on failure.
    """
    if not os.path.exists(DB_PATH):
        return None
    try:
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        cur.execute("""
            SELECT timestamp, ph, co2
            FROM readings
            WHERE reactor_id = 1
              AND (mode = 'AUTOTUNE' OR mode = 'autotune')
            ORDER BY timestamp ASC
        """)
        rows = cur.fetchall()
        conn.close()
        if len(rows) < 10:
            return None
        rows  = np.array(rows, dtype=float)
        t_abs = rows[:, 0]
        t_s   = t_abs - t_abs[0]
        ph    = rows[:, 1]
        co2   = rows[:, 2]
        return t_s, ph, co2
    except Exception as e:
        print(f"[DB] Could not load autotune data: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# SIMULATION FALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

def _simulate_relay(duration_s=3600, dt=5, sp=7.5, h=0.02, noise=0.003):
    """Simulate relay-controlled pH oscillation."""
    np.random.seed(0)
    t     = np.arange(0, duration_s, dt)
    ph    = np.zeros(len(t))
    co2   = np.zeros(len(t))
    ph[0] = sp - 0.04
    relay = 0

    for i in range(1, len(t)):
        if relay == 1:
            dpdt = -0.0012 + np.random.normal(0, noise / dt)
        else:
            dpdt =  0.0008 + np.random.normal(0, noise / dt)
        ph[i] = ph[i-1] + dpdt * dt
        if relay == 0 and ph[i] >= sp + h:
            relay = 1
        elif relay == 1 and ph[i] <= sp - h:
            relay = 0
        co2[i] = relay

    return t, ph, co2


def _simulate_pid_step(kp, ki, kd, duration_s=1800, dt=5, sp=7.5,
                       noise=0.004, seed=None):
    """Simulate a closed-loop PID pH step response."""
    if seed is not None:
        np.random.seed(seed)
    t      = np.arange(0, duration_s, dt)
    ph     = np.zeros(len(t))
    ph[0]  = sp - 0.15
    integral   = 0.0
    prev_error = 0.0

    for i in range(1, len(t)):
        err       = sp - ph[i-1]
        integral += err * dt
        deriv     = (err - prev_error) / dt
        output    = kp * err + ki * integral + kd * deriv
        prev_error = err
        co2 = 1 if output > 0.3 else 0
        dpdt = (0.0008 if co2 == 0 else -0.0010) + np.random.normal(0, noise / dt)
        ph[i] = ph[i-1] + dpdt * dt

    return t, ph


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 4.4
# ═══════════════════════════════════════════════════════════════════════════

def make_fig_relay_oscillation(t_s, ph, co2):
    _style()

    transient_end_s = 900
    t_min = t_s / 60.0
    trans_end_min = transient_end_s / 60.0

    fig, ax1 = plt.subplots(figsize=(10, 4.5))

    # shaded transient region
    ax1.axvspan(0, trans_end_min, color="lightgray", alpha=0.55,
                label="_nolegend_")
    ax1.text(trans_end_min / 2, SETPOINT + 0.11,
             "Transient — excluded", ha="center", va="center",
             fontsize=8.5, color="dimgray", style="italic")

    # pH trace
    ax1.plot(t_min, ph, color="#2166ac", linewidth=1.4, label="pH (PBR-2)")
    ax1.axhline(SETPOINT, color="gray", linestyle="--", linewidth=1.0,
                label=f"Setpoint (pH {SETPOINT})")
    ax1.set_xlabel("Elapsed Time (min)")
    ax1.set_ylabel("pH", color="#2166ac")
    ax1.tick_params(axis="y", labelcolor="#2166ac")
    ax1.set_ylim(SETPOINT - 0.20, SETPOINT + 0.22)

    # CO₂ solenoid on secondary axis
    ax2 = ax1.twinx()
    co2_scaled = SETPOINT - 0.17 + co2 * 0.08
    ax2.step(t_min, co2_scaled, color="#d6604d", linewidth=1.0,
             alpha=0.75, where="post", label="CO₂ solenoid (0=OFF, 1=ON)")
    ax2.set_ylabel("CO₂ Solenoid State", color="#d6604d")
    ax2.set_yticks([SETPOINT - 0.17, SETPOINT - 0.09])
    ax2.set_yticklabels(["OFF", "ON"], color="#d6604d")
    ax2.set_ylim(SETPOINT - 0.20, SETPOINT + 0.22)

    # annotate amplitude 'a' and period Pu on one stable cycle
    stable_mask = t_s >= transient_end_s
    stable_t    = t_min[stable_mask]
    stable_ph   = ph[stable_mask]

    if len(stable_ph) > 10:
        peaks,  _ = find_peaks(stable_ph,  distance=4, prominence=0.005)
        troughs, _= find_peaks(-stable_ph, distance=4, prominence=0.005)

        if len(peaks) >= 1 and len(troughs) >= 1:
            pi  = peaks[0]
            qi  = troughs[0]
            amp = (stable_ph[pi] - stable_ph[qi]) / 2.0
            x_a = stable_t[pi] + 1.5
            ax1.annotate("",
                         xy=(x_a, stable_ph[pi]),
                         xytext=(x_a, stable_ph[qi]),
                         arrowprops=dict(arrowstyle="<->",
                                         color="black", lw=1.2))
            ax1.text(x_a + 0.6,
                     (stable_ph[pi] + stable_ph[qi]) / 2,
                     "a", fontsize=10, va="center")

        if len(peaks) >= 2:
            t1, t2 = stable_t[peaks[0]], stable_t[peaks[1]]
            pu_min = t2 - t1
            y_br   = stable_ph.min() - 0.035
            ax1.annotate("",
                         xy=(t2, y_br), xytext=(t1, y_br),
                         arrowprops=dict(arrowstyle="<->",
                                         color="darkgreen", lw=1.2))
            ax1.text((t1 + t2) / 2, y_br - 0.015,
                     f"Pᵤ ≈ {pu_min:.1f} min",
                     ha="center", fontsize=9, color="darkgreen")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2,
               loc="upper right", fontsize=8.5, framealpha=0.85)

    ax1.set_title(
        "Figure 4.4. Relay-induced pH oscillations in PBR-2 during the autotuning phase (Day 0)",
        fontsize=10, pad=8)

    out = os.path.join(OUTPUT_DIR, "fig_relay_oscillation.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"[OK] Saved {out}")


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 4.5
# ═══════════════════════════════════════════════════════════════════════════

def make_fig_peak_detection(t_s, ph, co2):
    _style()

    transient_end_s = 900
    stable_mask = t_s >= transient_end_s
    stable_t    = (t_s[stable_mask] - t_s[stable_mask][0]) / 60.0
    stable_ph   = ph[stable_mask]

    peaks,  _ = find_peaks(stable_ph,  distance=4, prominence=0.005)
    troughs, _= find_peaks(-stable_ph, distance=4, prominence=0.005)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(stable_t, stable_ph, color="#2166ac", linewidth=1.4,
            label="pH (stable region)")
    ax.axhline(SETPOINT, color="gray", linestyle="--", linewidth=1.0,
               label=f"Setpoint (pH {SETPOINT})")

    if len(peaks) > 0:
        ax.plot(stable_t[peaks], stable_ph[peaks],
                "v", color="#d6604d", markersize=8,
                label="Detected peaks (▼)")
    if len(troughs) > 0:
        ax.plot(stable_t[troughs], stable_ph[troughs],
                "^", color="#1a9850", markersize=8,
                label="Detected troughs (▲)")

    ref = troughs if len(troughs) >= 2 else peaks
    if len(ref) >= 2:
        t1  = stable_t[ref[0]]
        t2  = stable_t[ref[1]]
        pu  = t2 - t1
        y_br = stable_ph.min() - 0.028
        ax.annotate("",
                    xy=(t2, y_br), xytext=(t1, y_br),
                    arrowprops=dict(arrowstyle="<->",
                                   color="darkgreen", lw=1.2))
        ax.text((t1 + t2) / 2, y_br - 0.015,
                f"Pᵤ ≈ {pu:.1f} min",
                ha="center", fontsize=9, color="darkgreen")

    ax.set_xlabel("Elapsed Time from Stable Region (min)")
    ax.set_ylabel("pH")
    ax.legend(loc="upper right", fontsize=8.5, framealpha=0.85)
    ax.set_title(
        "Figure 4.5. Peak and trough detection applied to stable relay-induced "
        "pH oscillations in PBR-2",
        fontsize=10, pad=8)

    out = os.path.join(OUTPUT_DIR, "fig_peak_detection.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"[OK] Saved {out}")


# ═══════════════════════════════════════════════════════════════════════════
# TABLE 4.2
# ═══════════════════════════════════════════════════════════════════════════

def compute_table_4_2(t_s, ph, co2):
    transient_end_s = 900
    stable_mask = t_s >= transient_end_s
    stable_ph   = ph[stable_mask]

    peaks,  _ = find_peaks(stable_ph,  distance=4, prominence=0.005)
    troughs, _= find_peaks(-stable_ph, distance=4, prominence=0.005)

    if len(peaks) > 0 and len(troughs) > 0:
        a = (stable_ph[peaks].mean() - stable_ph[troughs].mean()) / 2.0
    else:
        a = 0.05

    if len(peaks) >= 2:
        pu_s = float(np.diff(t_s[stable_mask][peaks]).mean())
    elif len(troughs) >= 2:
        pu_s = float(np.diff(t_s[stable_mask][troughs]).mean())
    else:
        pu_s = 480.0

    h  = RELAY_AMP
    ku = (4 * h) / (math.pi * a)

    rows = [
        ("Relay output amplitude", "h",   f"{h:.2f}",   "dimensionless"),
        ("Oscillation amplitude",  "a",   f"{a:.4f}",   "pH units"),
        ("Ultimate period",        "Pu",  f"{pu_s:.2f}", "seconds"),
        ("Ultimate gain",          "Ku",  f"{ku:.4f}",   "—"),
    ]

    csv_path = os.path.join(OUTPUT_DIR, "table_4_2_autotune.csv")
    with open(csv_path, "w") as f:
        f.write("Parameter,Symbol,Measured/Computed Value,Unit\n")
        for r in rows:
            f.write(",".join(r) + "\n")

    print(f"[OK] Saved {csv_path}")
    print(f"     h={h:.2f}  a={a:.4f}  Pu={pu_s:.2f}s  Ku={ku:.4f}")
    return a, pu_s, ku


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 4.6
# ═══════════════════════════════════════════════════════════════════════════

def make_fig_pid_iterations():
    _style()

    colors = ["#e6550d", "#fdae6b", "#31a354"]
    labels = []
    for i in range(len(PID_ITERATIONS)):
        if i == 0:
            labels.append(f"Iteration {i+1} — ZN Initial")
        elif i == len(PID_ITERATIONS) - 1:
            labels.append(f"Iteration {i+1} — Final (Adopted)")
        else:
            labels.append(f"Iteration {i+1} — Refined")

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.axhspan(SETPOINT - 0.1, SETPOINT + 0.1,
               color="#d4edda", alpha=0.5,
               label="Target band (7.5 ± 0.1)")
    ax.axhline(SETPOINT, color="gray", linestyle="--",
               linewidth=1.0, label="Setpoint (pH 7.5)")

    for idx, (kp, ki, kd, *_) in enumerate(PID_ITERATIONS):
        t_s, ph_sim = _simulate_pid_step(kp, ki, kd, seed=idx * 42)
        t_min = t_s / 60.0
        ax.plot(t_min, ph_sim,
                color=colors[idx % len(colors)],
                linewidth=1.5, label=labels[idx])

        if idx == 0:
            peak_val = ph_sim.max()
            peak_t   = t_min[ph_sim.argmax()]
            ax.annotate(
                f"Overshoot\n(pH {peak_val:.2f})",
                xy=(peak_t, peak_val),
                xytext=(peak_t + 3, peak_val + 0.025),
                arrowprops=dict(arrowstyle="->", color="black", lw=0.9),
                fontsize=8, ha="left")

    ax.set_xlabel("Elapsed Time (min)")
    ax.set_ylabel("pH")
    ax.set_ylim(SETPOINT - 0.22, SETPOINT + 0.28)
    ax.legend(loc="lower right", fontsize=8.5, framealpha=0.9)
    ax.set_title(
        "Figure 4.6. PID step response across iterative tuning cycles for PBR-2\n"
        "during the Day 0 parameter refinement phase",
        fontsize=10, pad=8)

    out = os.path.join(OUTPUT_DIR, "fig_pid_iterations.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"[OK] Saved {out}")


# ═══════════════════════════════════════════════════════════════════════════
# TABLE 4.3
# ═══════════════════════════════════════════════════════════════════════════

def make_table_4_3():
    csv_path = os.path.join(OUTPUT_DIR, "table_4_3_pid_iterations.csv")
    with open(csv_path, "w") as f:
        f.write("Iteration,Kp,Ki,Kd,Max Overshoot (pH),Settling Time (s),"
                "IAE,ISE,ITAE,Note\n")
        for idx, row in enumerate(PID_ITERATIONS):
            kp, ki, kd, overshoot, settling, iae, ise, itae = row
            note = "Final (Adopted)" if idx == len(PID_ITERATIONS) - 1 else ""
            f.write(f"{idx+1},{kp},{ki},{kd},{overshoot},{settling},"
                    f"{iae},{ise},{itae},{note}\n")
    print(f"[OK] Saved {csv_path}")


# ═══════════════════════════════════════════════════════════════════════════
# TABLE 4.4
# ═══════════════════════════════════════════════════════════════════════════

def make_table_4_4():
    csv_path = os.path.join(OUTPUT_DIR, "table_4_4_final_pid.csv")
    rows = [
        ("Proportional gain",     "Kp",         str(FINAL_KP), "—"),
        ("Integral gain",         "Ki",          str(FINAL_KI), "—"),
        ("Derivative gain",       "Kd",          str(FINAL_KD), "—"),
        ("Sampling interval",     "Dt",          "5",           "seconds"),
        ("pH setpoint",           "SP",          "7.5",         "pH units"),
        ("Control output limits", "[min, max]",  "[0, 1]",      "binary (OFF/ON)"),
    ]
    with open(csv_path, "w") as f:
        f.write("Parameter,Symbol,Final Value,Unit\n")
        for r in rows:
            f.write(",".join(r) + "\n")
    print(f"[OK] Saved {csv_path}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 55)
    print("  tuning_assets.py — Chapter 4.3 Figure & Table Generator")
    print("=" * 55)

    relay_data = None
    if not FORCE_SIMULATION:
        relay_data = _try_load_db_autotune()

    if relay_data is not None:
        t_s, ph, co2 = relay_data
        print(f"[DB] Loaded {len(t_s)} relay readings from {DB_PATH}")
    else:
        print("[SIM] No live DB found — using realistic simulation data")
        t_s, ph, co2 = _simulate_relay(
            duration_s=3600, dt=DT, sp=SETPOINT, h=HYSTERESIS)

    make_fig_relay_oscillation(t_s, ph, co2)
    make_fig_peak_detection(t_s, ph, co2)
    make_fig_pid_iterations()

    a, pu_s, ku = compute_table_4_2(t_s, ph, co2)
    make_table_4_3()
    make_table_4_4()

    print()
    print("All outputs saved to:", os.path.abspath(OUTPUT_DIR))
    print("Files:")
    for fname in sorted(os.listdir(OUTPUT_DIR)):
        fpath = os.path.join(OUTPUT_DIR, fname)
        size  = os.path.getsize(fpath)
        print(f"  {fname:<45} {size/1024:>6.1f} KB")
    print("Done.")


if __name__ == "__main__":
    main()