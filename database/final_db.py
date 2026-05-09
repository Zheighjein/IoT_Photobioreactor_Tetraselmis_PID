import sqlite3
import time
import os
from datetime import datetime

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "pbr_sim.db")
)

def connect():
    return sqlite3.connect(DB_PATH)


def init_db():

    conn = connect()
    c = conn.cursor()

    # ========================
    # READINGS TABLE
    # ========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reactor_id INTEGER,
        time REAL,
        ph REAL,
        temp REAL,
        co2 INTEGER,
        mode TEXT,
        light_state INTEGER
    )
    """)

    # ========================
    # PID PARAMETERS
    # ========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS pid_params (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reactor_id INTEGER,
        timestamp REAL,
        kp REAL,
        ki REAL,
        kd REAL
    )
    """)

    # ========================
    # EVENTS TABLE
    # ========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reactor_id INTEGER,
        timestamp REAL,
        parameter TEXT,
        issue TEXT,
        action TEXT,
        status TEXT
    )
    """)

    # ========================
    # PERFORMANCE LOG
    # ========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS performance_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reactor_id INTEGER,
        timestamp REAL,
        timestamp_text TEXT,
        iae REAL,
        ise REAL,
        itae REAL
    )
    """)

    # ========================
    # SUMMARY TABLE
    # ========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reactor_id INTEGER,
        final_iae REAL,
        final_ise REAL,
        final_itae REAL,
        mode TEXT,
        timestamp REAL
    )
    """)

    # ========================
    # SYSTEM STATE
    # ========================
    c.execute("""
    CREATE TABLE IF NOT EXISTS system_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL,
        start_time REAL,

        r1_iae REAL,
        r1_ise REAL,
        r1_itae REAL,
        r1_mode TEXT,

        r2_iae REAL,
        r2_ise REAL,
        r2_itae REAL,
        r2_mode TEXT,

        pid_initialized INTEGER
    )
    """)

    conn.commit()
    conn.close()


# ========================
# INSERT FUNCTIONS
# ========================

def insert_reading(
    rid,
    t,
    ph,
    temp,
    co2,
    mode,
    light_state
):

    conn = connect()
    c = conn.cursor()

    c.execute("""
    INSERT INTO readings
    VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)
    """, (
        rid,
        t,
        ph,
        temp,
        co2,
        mode,
        light_state
    ))

    conn.commit()
    conn.close()


def insert_pid(rid, kp, ki, kd):

    conn = connect()
    c = conn.cursor()

    c.execute("""
    INSERT INTO pid_params
    VALUES (NULL, ?, ?, ?, ?, ?)
    """, (
        rid,
        time.time(),
        kp,
        ki,
        kd
    ))

    conn.commit()
    conn.close()


def insert_event(
    rid,
    param,
    issue,
    action,
    status
):

    conn = connect()
    c = conn.cursor()

    c.execute("""
    INSERT INTO events
    VALUES (NULL, ?, ?, ?, ?, ?, ?)
    """, (
        rid,
        time.time(),
        param,
        issue,
        action,
        status
    ))

    conn.commit()
    conn.close()


def insert_performance(
    rid,
    iae,
    ise,
    itae
):

    conn = connect()
    c = conn.cursor()

    c.execute("""
    INSERT INTO performance_log
    VALUES (NULL, ?, ?, ?, ?, ?, ?)
    """, (
        rid,
        time.time(),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        iae,
        ise,
        itae
    ))

    conn.commit()
    conn.close()


def insert_summary(
    rid,
    iae,
    ise,
    itae,
    mode
):

    conn = connect()
    c = conn.cursor()

    c.execute("""
    INSERT INTO summary
    VALUES (NULL, ?, ?, ?, ?, ?, ?)
    """, (
        rid,
        iae,
        ise,
        itae,
        mode,
        time.time()
    ))

    conn.commit()
    conn.close()


# ========================
# STATE SAVE
# ========================

def save_state(data):

    conn = connect()
    c = conn.cursor()

    c.execute("""
    INSERT INTO system_state (

        timestamp,
        start_time,

        r1_iae,
        r1_ise,
        r1_itae,
        r1_mode,

        r2_iae,
        r2_ise,
        r2_itae,
        r2_mode,

        pid_initialized

    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (

        time.time(),
        data["start_time"],

        data["r1_iae"],
        data["r1_ise"],
        data["r1_itae"],
        data["r1_mode"],

        data["r2_iae"],
        data["r2_ise"],
        data["r2_itae"],
        data["r2_mode"],

        data["pid_initialized"]

    ))

    conn.commit()
    conn.close()


def load_state():

    conn = connect()
    c = conn.cursor()

    c.execute("""
    SELECT *
    FROM system_state
    ORDER BY id DESC
    LIMIT 1
    """)

    row = c.fetchone()

    conn.close()

    if not row:
        return None

    return {

        "start_time": row[2],

        "r1_iae": row[3],
        "r1_ise": row[4],
        "r1_itae": row[5],
        "r1_mode": row[6],

        "r2_iae": row[7],
        "r2_ise": row[8],
        "r2_itae": row[9],
        "r2_mode": row[10],

        "pid_initialized": bool(row[11])
    }