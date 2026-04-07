# Project Structure

## Directory Layout
```
IoT_Photobioreactor_Tetraselmis_PID/
├── main.py                        # Entry point: autotune → dual-reactor control loop
├── plot_results.py                # Post-run visualization and metric comparison
├── requirements.txt               # Python dependencies
├── .env                           # Runtime config (SP, DT, SIM_MODE)
├── .gitignore
│
├── controllers/                   # Control algorithm implementations
│   ├── __init__.py
│   ├── pid.py                     # PID controller class
│   ├── onoff.py                   # ON/OFF (bang-bang) controller function
│   └── autotune.py                # Relay-based autotune to derive PID params
│
├── simulator/                     # Biological process simulation
│   ├── __init__.py
│   └── tetraselmis_sim.py         # Tetraselmis pH/temp dynamics model
│
├── database/                      # Persistence layer
│   ├── __init__.py
│   ├── db.py                      # DB_PATH, init_db(), and all insert_* functions
│   ├── pbr_sim.db                 # Active SQLite database (gitignored)
│   └── spbr_sim.db                # Secondary/backup DB
│
├── dashboard/                     # Flask web dashboard
│   ├── app.py                     # Flask routes and API endpoints
│   ├── templates/
│   │   ├── index.html             # Main dashboard page
│   │   └── notification.html      # Notifications page
│   └── static/
│       ├── script.js              # Frontend chart/polling logic
│       ├── style.css              # Dashboard styling
│       └── Phyto.jpg              # Static asset
│
└── .amazonq/rules/memory-bank/    # Amazon Q memory bank documentation
```

## Core Components and Relationships

### main.py (Orchestrator)
- Loads `.env`, calls `init_db()`, instantiates two `TetraselmisSim` instances
- Phase 1: Runs `RelayAutotune` on Reactor 1 until oscillation params are found, then calls `autotune.compute_pid()` to get Kp/Ki/Kd
- Phase 2: Enters infinite loop — each tick calls `sim.step()`, computes error, updates IAE/ISE/ITAE, applies PID or ON/OFF control, logs via `insert_reading()` and `insert_iae()`
- On `KeyboardInterrupt`: calls `insert_summary()` for both reactors

### controllers/
- `pid.py`: Stateful PID class with `compute(ph)` method
- `onoff.py`: Stateless function `onoff_control(ph, setpoint)` returning 0/1/None
- `autotune.py`: `RelayAutotune` class — drives relay oscillation, records history, detects amplitude/period, computes Ziegler-Nichols PID values

### simulator/tetraselmis_sim.py
- `TetraselmisSim` class with `step(co2)` method
- Models pH and temperature dynamics specific to *Tetraselmis sp.*
- Returns `(ph, temp)` tuple each step

### database/db.py (Single Source of Truth)
- `DB_PATH` is the canonical database path — imported by both `main.py` and `dashboard/app.py`
- Tables: `readings`, `pid_params`, `events`, `iae_log`, `summary`
- Each insert function opens, writes, commits, and closes its own connection

### dashboard/app.py
- Flask app importing `DB_PATH` from `database.db`
- REST API endpoints: `/api/data`, `/api/history`, `/api/status`, `/api/logs`, `/api/notifications`
- `reactor_config` dict maps algorithm names (`'PID'`, `'ON/OFF'`) to reactor IDs and threshold ranges

## Architectural Patterns
- **Separation of concerns**: simulation, control, persistence, and presentation are fully decoupled modules
- **Single DB path**: `DB_PATH` defined once in `database/db.py`, imported everywhere — no path duplication
- **Reactor ID convention**: Reactor 1 = PID, Reactor 2 = ON/OFF (enforced in both `main.py` and `dashboard/app.py`)
- **Two-process architecture**: `main.py` writes to DB; `dashboard/app.py` reads from DB — no shared memory
- **Sequential phases**: autotune must complete before the main control loop starts
