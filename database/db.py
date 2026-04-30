import sqlite3
import time
import os
from datetime import datetime

# ── Database path (DO NOT CHANGE) ──────────────────────────
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "pbr_sim.db"))


def connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = connect()
    c = conn.cursor()

    # ========================
    # MAIN READINGS TABLE
    # ========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS readings (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        reactor_id INTEGER,
        time       REAL,
        ph         REAL,
        temp       REAL,
        co2        INTEGER,
        mode       TEXT
    )
    """)

    # ========================
    # PID PARAMETERS
    # ========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS pid_params (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        reactor_id INTEGER,
        timestamp  REAL,
        kp         REAL,
        ki         REAL,
        kd         REAL,
        amplitude  REAL,
        period     REAL,
        ku         REAL
    )
    """)

    # ========================
    # EVENTS
    # ========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        reactor_id INTEGER,
        timestamp  REAL,
        parameter  TEXT,
        issue      TEXT,
        action     TEXT,
        status     TEXT
    )
    """)

    # ========================
    # PERFORMANCE LOG (FOR THESIS)
    # ========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS performance_log (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        reactor_id INTEGER,
        timestamp  REAL,
        timestamp_text TEXT,
        iae        REAL,
        ise        REAL,
        itae       REAL
    )
    """)

    # ========================
    # SUMMARY TABLE
    # ========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS summary (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        reactor_id INTEGER,
        final_iae REAL,
        final_ise REAL,
        final_itae REAL,
        mode       TEXT,
        timestamp  REAL
    )
    """)

    conn.commit()
    conn.close()


# ========================
# INSERT FUNCTIONS
# ========================

def insert_reading(rid, t, ph, temp, co2, mode):
    conn = connect()
    c = conn.cursor()

    c.execute(
        "INSERT INTO readings (reactor_id, time, ph, temp, co2, mode) VALUES (?, ?, ?, ?, ?, ?)",
        (rid, t, ph, temp, co2, mode)
    )

    conn.commit()
    conn.close()


def insert_pid(rid, kp, ki, kd, amplitude, period, ku):
    conn = connect()
    c = conn.cursor()

    c.execute(
        "INSERT INTO pid_params (reactor_id, timestamp, kp, ki, kd, amplitude, period, ku) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (rid, time.time(), kp, ki, kd, amplitude, period, ku)
    )

    conn.commit()
    conn.close()


def insert_event(rid, param, issue, action, status):
    conn = connect()
    c = conn.cursor()

    c.execute(
        "INSERT INTO events (reactor_id, timestamp, parameter, issue, action, status) VALUES (?, ?, ?, ?, ?, ?)",
        (rid, time.time(), param, issue, action, status)
    )

    conn.commit()
    conn.close()


def insert_performance(rid, iae, ise, itae):
    conn = connect()
    c = conn.cursor()
    timestamp = time.time()
    timestamp_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "INSERT INTO performance_log (reactor_id, timestamp, timestamp_text, iae, ise, itae) VALUES (?, ?, ?, ?, ?, ?)",
        (rid, timestamp, timestamp_text, iae, ise, itae)
    )
    conn.commit()
    conn.close()


def insert_summary(rid, iae, ise, itae, mode):
    conn = connect()
    c = conn.cursor()

    c.execute("""
    INSERT INTO summary (reactor_id, final_iae, final_ise, final_itae, mode, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (rid, iae, ise, itae, mode, time.time()))

    conn.commit()
    conn.close()