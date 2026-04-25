import os
import sqlite3
import time
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from datetime import datetime

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')

# ── Import the single shared DB path from the simulation layer ─────────────
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import DB_PATH as DATABASE_PATH

# ── Reactor config: R1 = PID  |  R2 = ON/OFF  (matches main.py) ───────────
reactor_config = {
    'PID': {
        'name':      'Photobioreactor 1',
        'reactor_id': 1,
        'phMin':  7.4,
        'phMax':  7.6,
        'tempMin': 25,
        'tempMax': 28
    },
    'ON/OFF': {
        'name':      'Photobioreactor 2',
        'reactor_id': 2,
        'phMin':  7.4,
        'phMax':  7.6,
        'tempMin': 27,
        'tempMax': 29
    }
}


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/notifications')
def notifications_page():
    return render_template('notification.html')


@app.route('/api/data')
def get_sensor_data():
    selected_algo = request.args.get('algorithm', 'ON/OFF')

    if selected_algo not in reactor_config:
        return jsonify({'status': 'error', 'message': 'Invalid algorithm'}), 400

    config     = reactor_config[selected_algo]
    reactor_id = config['reactor_id']

    try:
        conn = get_db_connection()
        row  = conn.execute(
            "SELECT ph, temp, time FROM readings WHERE reactor_id = ? ORDER BY rowid DESC LIMIT 1",
            (reactor_id,)
        ).fetchone()
        conn.close()

        if row is None:
            return jsonify({'status': 'idle', 'message': 'Simulation not running'}), 404

        ph   = row['ph']
        temp = row['temp']

        return jsonify({
            'status':      'success',
            'algorithm':   selected_algo,
            'ph':          ph,
            'temperature': temp,
            'ph_status':   'STABLE' if config['phMin']   <= ph   <= config['phMax']   else 'ADJUSTING',
            'temp_status': 'STABLE' if config['tempMin'] <= temp <= config['tempMax'] else 'ADJUSTING',
            'config': {
                'name':    config['name'],
                'phMin':   config['phMin'],
                'phMax':   config['phMax'],
                'tempMin': config['tempMin'],
                'tempMax': config['tempMax']
            },
            'timestamp': datetime.now().strftime('%I:%M:%S %p')
        })

    except Exception as e:
        print(f"Flask /api/data error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/history')
def get_history():
    try:
        conn         = get_db_connection()
        history_data = {}

        for algo, config in reactor_config.items():
            rows = conn.execute(
                "SELECT ph, temp, time FROM readings WHERE reactor_id = ? ORDER BY rowid DESC LIMIT 8",
                (config['reactor_id'],)
            ).fetchall()
            rows = list(reversed(rows))

            if rows:
                timestamps = [
                    datetime.fromtimestamp(r['time']).strftime('%I:%M:%S %p')
                    for r in rows
                ]
            else:
                timestamps = []

            history_data[algo] = {
                'ph':          [r['ph']   for r in rows],
                'temperature': [r['temp'] for r in rows],
                'timestamps':  timestamps
            }

        conn.close()
        return jsonify({'status': 'success', 'data': history_data})

    except Exception as e:
        print(f"Flask /api/history error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/status')
def get_status():
    try:
        conn     = get_db_connection()
        reactors = {}

        for algo, config in reactor_config.items():
            row = conn.execute(
                "SELECT ph, temp, co2, time FROM readings WHERE reactor_id = ? ORDER BY rowid DESC LIMIT 1",
                (config['reactor_id'],)
            ).fetchone()

            if row:
                if algo == 'PID':
                    pid_row = conn.execute(
                        "SELECT kp, ki, kd FROM pid_params WHERE reactor_id = ? ORDER BY rowid DESC LIMIT 1",
                        (config['reactor_id'],)
                    ).fetchone()
                    algo_params = {
                        'kp': pid_row['kp'] if pid_row else '—',
                        'ki': pid_row['ki'] if pid_row else '—',
                        'kd': pid_row['kd'] if pid_row else '—'
                    }
                else:
                    algo_params = {'hysteresis_band': 0.3, 'switch_state': 'Heating'}

                reactors[algo] = {
                    'online':           True,
                    'ph':               row['ph'],
                    'temperature':      row['temp'],
                    'co2':              row['co2'],
                    'config':           config,
                    'algorithm_params': algo_params,
                    'timestamp':        row['time']
                }
            else:
                reactors[algo] = {'online': False}

        conn.close()
        return jsonify({
            'status':    'success',
            'reactors':  reactors,
            'timestamp': datetime.now().isoformat(),
            'server_time': time.time()
        })

    except Exception as e:
        print(f"Flask /api/status error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/logs')
def get_logs():
    try:
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT ph, temp, co2, reactor_id, time FROM readings ORDER BY time DESC LIMIT 10"
        ).fetchall()
        conn.close()

        logs = []
        for row in rows:
            algo   = 'PID' if row['reactor_id'] == 1 else 'ON/OFF'
            ph, temp = row['ph'], row['temp']

            if row['co2'] == 1:
                param, desc, st = 'pH', f"CO2 injecting — pH: {ph:.2f}", 'Adjusting'
            else:
                param, desc, st = 'Status', f"Valve closed — pH: {ph:.2f}", 'Success'

            logs.append({
                'parameter':   param,
                'reactor':     algo,
                'description': desc,
                'status':      st,
                'timestamp':   row['time']
            })

        return jsonify({'status': 'success', 'logs': logs})

    except Exception as e:
        print(f"Flask /api/logs error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/notifications')
def get_notifications():
    try:
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT ph, temp, co2, reactor_id, time, rowid FROM readings ORDER BY rowid DESC LIMIT 20"
        ).fetchall()
        conn.close()

        grouped = {}
        now = datetime.now()
        date_label = now.strftime('%B %d, %Y')

        rows = list(rows)  # newest first (ORDER BY rowid DESC)

        for row in rows:
            algo = 'PID' if row['reactor_id'] == 1 else 'ON/OFF'
            ph = row['ph']
            temp = row['temp']
            timestamp = datetime.fromtimestamp(row['time']).strftime('%B %d, %Y  %I:%M:%S %p')
            time_only = datetime.fromtimestamp(row['time']).strftime('%I:%M:%S %p')

            if row['co2'] == 1:
                parameter = f"pH: {ph:.2f}"
                issue = "CO2 injecting — valve open"
                status = "ADJUSTING"
            else:
                parameter = f"pH: {ph:.2f}, Temp: {temp:.1f}°C"
                issue = "Valve closed — system stable"
                status = "SUCCESS"

            if date_label not in grouped:
                grouped[date_label] = []

            grouped[date_label].append({
                'reactor': f"{algo} Control Algorithm",
                'parameter': parameter,
                'issue': issue,
                'datetime': timestamp,
                'time_only': time_only,
                'status': status
            })

        return jsonify({
            'status': 'success',
            'notifications': grouped
        })

    except Exception as e:
        print(f"Flask /api/notifications error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/metrics')
def get_metrics():
    try:
        conn = get_db_connection()
        metrics = {}

        for algo, config in reactor_config.items():
            row = conn.execute(
                "SELECT final_iae, final_ise, final_itae FROM summary WHERE reactor_id = ? ORDER BY rowid DESC LIMIT 1",
                (config['reactor_id'],)
            ).fetchone()

            metrics[algo] = {
                'iae':  round(row['final_iae'],  4) if row else None,
                'ise':  round(row['final_ise'],  4) if row else None,
                'itae': round(row['final_itae'], 4) if row else None
            }

        conn.close()
        return jsonify({'status': 'success', 'metrics': metrics})

    except Exception as e:
        print(f"Flask /api/metrics error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == "__main__":
    from database.db import init_db

    # Ensure database + tables exist before Flask starts
    init_db()

    print("✅ Database initialized successfully")

    app.run(host='0.0.0.0', port=5000, debug=True)
