# Product Overview

## Purpose
IoT simulation platform for a small-scale photobioreactor cultivating *Tetraselmis sp.* microalgae. The system compares two pH control strategies — PID and ON/OFF — to determine which provides more stable and efficient proactive pH regulation. This is the software component of a thesis research project.

## Key Features
- Dual-reactor simulation running simultaneously (Reactor 1 = PID, Reactor 2 = ON/OFF)
- Relay-based autotune phase that automatically computes PID parameters (Kp, Ki, Kd) before control begins
- Real-time pH and temperature simulation using a Tetraselmis-specific biological model
- CO2 injection actuation modeled as binary (0 or 1) control signal
- Performance metrics tracked continuously: IAE, ISE, ITAE
- SQLite database logging for readings, events, PID params, IAE log, and session summaries
- Flask web dashboard with live sensor data, history charts, notifications, and reactor status
- Plot results script for post-run analysis and visualization

## Target Users
- Thesis researchers comparing control algorithms for photobioreactor pH management
- Bioprocess engineering students studying closed-loop control in algae cultivation

## Use Cases
- Run `main.py` to start the dual-reactor simulation (autotune → PID + ON/OFF control loop)
- Run `dashboard/app.py` in a separate terminal to monitor live data via browser
- Run `plot_results.py` after a session to visualize and compare reactor performance
- Evaluate IAE scores to determine which control strategy performs better for *Tetraselmis sp.*

## Setpoint & Configuration
- Default pH setpoint: **7.5** (configurable via `.env` SP variable)
- Default time step: **5 seconds** (configurable via `.env` DT variable)
- Reactor 1 (PID): pH target range 7.5–8.0, temp 25–28°C
- Reactor 2 (ON/OFF): pH target range 8.1–8.7, temp 27–29°C
