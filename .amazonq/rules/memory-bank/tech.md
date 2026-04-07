# Technology Stack

## Language
- Python 3 (no version pinned; compatible with 3.9+)

## Dependencies (requirements.txt)
| Package | Version | Purpose |
|---|---|---|
| numpy | 1.26.4 | Numerical computation in simulator and autotune |
| matplotlib | 3.8.4 | Post-run plotting in plot_results.py |
| pandas | 2.2.2 | Data loading/analysis in plot_results.py |
| flask | 3.0.3 | Web dashboard REST API server |
| python-dotenv | 1.0.1 | Loading .env config variables |

## Database
- SQLite 3 (stdlib `sqlite3`) — file-based, no server required
- DB file: `database/pbr_sim.db` (path resolved via `os.path.abspath` in `database/db.py`)

## Environment Configuration (.env)
```
SIM_MODE=true
SP=7.5        # pH setpoint
DT=5          # time step in seconds
```
Loaded with `python-dotenv` via `load_dotenv()` at startup.

## Development Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Install dotenv separately if needed
pip install python-dotenv

# Run simulation (Terminal 1)
python main.py

# Run dashboard (Terminal 2)
python dashboard/app.py
```

## Frontend Stack (dashboard)
- Plain HTML/CSS/JS — no frontend framework
- `script.js` handles polling, Chart.js-style rendering, and DOM updates
- Flask serves templates via Jinja2 (`render_template`)

## Key stdlib Modules Used
- `sqlite3` — database access
- `os`, `os.path` — path resolution
- `time` — simulation timing and timestamps
- `sys` — path manipulation in dashboard/app.py

## IDE / Tooling Notes
- `.env` file must be present at project root before running
- Enable `python.terminal.useEnvFile` in VS Code settings to auto-load `.env`
- Both `main.py` and `dashboard/app.py` must run concurrently in separate terminals
- Stop with `Ctrl+C` — triggers graceful summary save in `main.py`
