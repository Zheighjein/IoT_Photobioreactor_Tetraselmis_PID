# Development Guidelines

## Code Quality Standards

### Naming Conventions
- Classes: PascalCase — `PID`, `RelayAutotune`, `TetraselmisSim`
- Functions/methods: snake_case — `onoff_control`, `insert_reading`, `compute_pid`
- Variables: snake_case — `reactor_id`, `relay_amplitude`, `prev_error`
- Constants/config keys: UPPER_SNAKE_CASE — `SETPOINT`, `DT`, `DB_PATH`
- Reactor IDs: integer literals `1` and `2` (never strings)
- Algorithm labels: string literals `'PID'` and `'ON/OFF'` (used as dict keys in dashboard)

### File and Module Structure
- All `__init__.py` files are intentionally empty — packages use explicit imports only
- Each module has a single clear responsibility (no mixing of control logic and DB logic)
- `DB_PATH` is defined once in `database/db.py` and imported everywhere — never redefined
- `from database.db import *` is acceptable in `main.py` for convenience (all functions are insert_*)

### Section Comments
- Use `# ========================` banner comments to separate logical sections within a file
- Section labels are ALL CAPS: `# INIT`, `# AUTOTUNE PHASE`, `# MAIN LOOP`, `# LOAD DATA`
- Inline comments use `#` with a space, placed on the same line for short clarifications
- Inline section dividers in `dashboard/app.py` use `# ──` style with trailing description

### Docstrings
- No docstrings used anywhere in the codebase — code is kept self-documenting through clear naming
- Do not add docstrings unless explicitly requested

---

## Architectural Patterns

### Controller Pattern
- Stateful controllers are classes with a `compute(value)` method (PID)
- Stateless controllers are plain functions returning a control signal (onoff_control)
- Control output is always binary CO2: `1` = inject, `0` = off
- `None` return from `onoff_control` means "no change" — caller must handle this

```python
# Stateful (PID)
pid = PID(Kp, Ki, Kd, setpoint=SETPOINT)
output = pid.compute(ph)
co2 = 1 if output < 0 else 0

# Stateless (ON/OFF)
action = onoff_control(ph, SETPOINT)
if action is not None:
    r["co2"] = action
```

### Simulator Pattern
- Simulators are classes with a `step(co2)` method returning `(ph, temp)`
- State is maintained internally (`self.ph`, `self.temp`)
- Noise is added via `random.uniform` — no seeding (intentionally stochastic)

```python
sim = TetraselmisSim()
ph, temp = sim.step(co2)
```

### Database Pattern
- Every insert function opens its own connection, commits, and closes — no persistent connections
- All functions follow the same pattern: `connect()` → `cursor()` → `execute()` → `commit()` → `close()`
- `DB_PATH` is always imported from `database.db`, never hardcoded elsewhere

```python
def insert_reading(rid, t, ph, temp, co2, mode):
    conn = connect()
    c = conn.cursor()
    c.execute("INSERT INTO readings ...", (rid, t, ph, temp, co2, mode))
    conn.commit()
    conn.close()
```

### Reactor State Dict Pattern
- Reactor state is stored in a flat dict keyed by reactor ID (integer)
- Keys: `"sim"`, `"co2"`, `"mode"`, `"iae"`, `"ise"`, `"itae"`, `"pid"` (added after autotune)
- Mode strings: `"AUTOTUNE"`, `"PID"`, `"ONOFF"`, `"IDLE"`

```python
reactors = {
    1: {"sim": TetraselmisSim(), "co2": 0, "mode": "AUTOTUNE", "iae": 0, "ise": 0, "itae": 0},
    2: {"sim": TetraselmisSim(), "co2": 0, "mode": "IDLE",     "iae": 0, "ise": 0, "itae": 0}
}
```

### Performance Metrics Pattern
- IAE, ISE, ITAE are accumulated each tick using the DT time step
- Error is always `SETPOINT - ph` (signed); `abs_error` used for IAE/ITAE

```python
error = SETPOINT - ph
abs_error = abs(error)
r["iae"]  += abs_error * DT
r["ise"]  += (error ** 2) * DT
r["itae"] += t * abs_error * DT
```

---

## Flask API Patterns

### Endpoint Structure
- All data endpoints are under `/api/` prefix
- Always return `{'status': 'success', ...}` on success
- Always return `{'status': 'error', 'message': str(e)}` with appropriate HTTP status on failure
- Use `try/except Exception as e` with `print(f"Flask /api/route error: {e}")` for all DB calls

### reactor_config Usage
- Dashboard maps algorithm names to reactor IDs and threshold ranges via `reactor_config` dict
- Always use `reactor_config[algo]['reactor_id']` to get the DB reactor_id — never hardcode

```python
reactor_config = {
    'PID':   {'reactor_id': 1, 'phMin': 7.5, 'phMax': 8.0, ...},
    'ON/OFF':{'reactor_id': 2, 'phMin': 8.1, 'phMax': 8.7, ...}
}
```

### Status Strings
- pH/temp status: `'STABLE'` when within range, `'ADJUSTING'` when outside
- Event status strings: `'adjusting'`, `'success'`, `'running'` (lowercase in DB events)
- Dashboard display status: `'STABLE'`, `'ADJUSTING'`, `'SUCCESS'` (uppercase in API responses)

---

## Plot Results Pattern
- `plot_results.py` is a standalone script — not imported by anything
- Uses `plt.savefig()` instead of `plt.show()` — always save to file, never display interactively
- Prints confirmation after each save: `print("Saved: filename.png")`
- IAE is computed from CSV error column sum: `df["error"].sum()`

---

## Environment and Config
- All runtime config comes from `.env` via `python-dotenv`
- Use `os.getenv("KEY", default)` with explicit defaults for all env vars
- `load_dotenv()` is called once at the top of each entry point (`main.py`, `app.py`)
- Never hardcode setpoint or DT values outside of `.env` defaults

---

## What NOT to Do
- Do not add docstrings — the codebase intentionally avoids them
- Do not use persistent DB connections — always open/close per operation
- Do not redefine `DB_PATH` — always import from `database.db`
- Do not use `plt.show()` in plot scripts — always use `plt.savefig()`
- Do not add a reactor mode outside of `"AUTOTUNE"`, `"PID"`, `"ONOFF"`, `"IDLE"`
- Do not seed `random` in the simulator — stochastic behavior is intentional
