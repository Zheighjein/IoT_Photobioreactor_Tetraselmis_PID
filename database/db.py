import sqlite3
import time
import os

# ── Single source of truth for the database location ──────────────────────────
# Always resolves to the same file regardless of where Python is launched from.
# Both main.py and app.py must import DB_PATH from here instead of defining it
# themselves.
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "pbr_sim.db"))


def connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = connect()
    c = conn.cursor()

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

    c.execute("""
    CREATE TABLE IF NOT EXISTS pid_params (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        reactor_id INTEGER,
        timestamp  REAL,
        kp         REAL,
        ki         REAL,
        kd         REAL
    )
    """)

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

    c.execute("""
    CREATE TABLE IF NOT EXISTS iae_log (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        reactor_id INTEGER,
        timestamp  REAL,
        iae        REAL
    )
    """)

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


def insert_reading(rid, t, ph, temp, co2, mode):
    conn = connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO readings (reactor_id, time, ph, temp, co2, mode) VALUES (?, ?, ?, ?, ?, ?)",
        (rid, t, ph, temp, co2, mode)
    )
    conn.commit()
    conn.close()


def insert_pid(rid, kp, ki, kd):
    conn = connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO pid_params (reactor_id, timestamp, kp, ki, kd) VALUES (?, ?, ?, ?, ?)",
        (rid, time.time(), kp, ki, kd)
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


def insert_iae(rid, iae):
    conn = connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO iae_log (reactor_id, timestamp, iae) VALUES (?, ?, ?)",
        (rid, time.time(), iae)
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