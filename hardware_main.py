import time
import os
from dotenv import load_dotenv

from controllers.pid import PID
from controllers.onoff import onoff_control
from controllers.autotune import RelayAutotune

from controllers.hardware import read_ph, read_temp, set_co2

from database.db import *

import RPi.GPIO as GPIO

# ========================
# INIT
# ========================
load_dotenv()
init_db()

SETPOINT = float(os.getenv("SP", 7.5))
DT = float(os.getenv("DT", 5))

TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
USE_AUTOTUNE = os.getenv("USE_AUTOTUNE", "true").lower() == "true"

print("=== RUNNING IN HARDWARE MODE ===")

if TEST_MODE:
    print("TEST MODE ENABLED (relay will NOT activate)")

print("Initializing sensors...")
time.sleep(2)

# ========================
# REACTORS
# ========================
reactors = {
    1: {"co2": 0, "mode": "AUTOTUNE", "iae": 0, "ise": 0, "itae": 0},
    2: {"co2": 0, "mode": "IDLE", "iae": 0, "ise": 0, "itae": 0}
}

# ========================
# AUTOTUNE (1 DAY)
# ========================
if USE_AUTOTUNE:
    autotune = RelayAutotune(setpoint=SETPOINT)

    insert_event(1, "SYSTEM", "Starting autotune", "Relay tuning", "adjusting")

    AUTOTUNE_DURATION = 20  # testing #make this into 86400 for a full day
    autotune_start = time.time()

    while time.time() - autotune_start < AUTOTUNE_DURATION:
        try:
            ph = read_ph(1)
            temp = read_temp("28-0000006dc349")
        except Exception as e:
            print(f"[ERROR] Sensor read failed: {e}")
            time.sleep(DT)
            continue

        output = autotune.step(ph)

        reactors[1]["co2"] = 1 if output < 0 else 0

        if not TEST_MODE:
            set_co2(1, reactors[1]["co2"])

        autotune.record(ph)

        elapsed = int(time.time() - autotune_start)

        print(f"[AUTOTUNE] t={elapsed}s pH={ph:.3f} Temp={temp:.2f}")

        time.sleep(DT)

    print(">>> EXITED AUTOTUNE LOOP <<<")

    # ========================
    # AFTER AUTOTUNE → COMPUTE PID
    # ========================
    print("Autotune finished. Computing PID...")

    amp, per = autotune.get_params()
    pid_vals = autotune.compute_pid(amp, per)

    if not pid_vals:
        print("⚠️ Autotune failed → using fallback PID values")
        Kp, Ki, Kd = 2.0, 0.5, 0.1   # If tuning phase fails
    else:
        Kp, Ki, Kd = pid_vals

    insert_pid(1, Kp, Ki, Kd)

    reactors[1]["pid"] = PID(Kp, Ki, Kd, setpoint=SETPOINT)

    # RESET METRICS
    for r in reactors.values():
        r["iae"] = 0
        r["ise"] = 0
        r["itae"] = 0

    # SWITCH MODES
    reactors[1]["mode"] = "PID"
    reactors[2]["mode"] = "ONOFF"

    print(">>> MODE SWITCH SUCCESS <<<")
    print(f"Reactor 1 Mode: {reactors[1]['mode']}")
    print(f"Reactor 2 Mode: {reactors[2]['mode']}")

    insert_event(1, "SYSTEM", "Autotune complete", "PID active", "success")
    insert_event(2, "SYSTEM", "Control started", "ON/OFF active", "running")

else:
    print("USING MANUAL PID VALUES")

    Kp, Ki, Kd = 2.0, 0.5, 0.1

    insert_pid(1, Kp, Ki, Kd)

    reactors[1]["pid"] = PID(Kp, Ki, Kd, setpoint=SETPOINT)

    reactors[1]["mode"] = "PID"
    reactors[2]["mode"] = "ONOFF"

# ========================
# MAIN LOOP
# ========================
start = time.time()

try:
    while True:
        t = time.time() - start
        now = time.time()

        for rid, r in reactors.items():

            try:
                if rid == 1:
                    temp = read_temp("28-0000006dc349")
                else:
                    temp = read_temp("28-000000b2e281")

                ph = read_ph(rid)

            except Exception as e:
                print(f"[ERROR] Sensor read failed for R{rid}: {e}")
                continue

            print(f"[SENSOR] R{rid} pH={ph:.3f} Temp={temp:.2f}")

            error = SETPOINT - ph
            abs_error = abs(error)

            # METRICS
            r["iae"] += abs_error * DT
            r["ise"] += (error ** 2) * DT
            r["itae"] += t * abs_error * DT

            # ========================
            # CONTROL
            # ========================
            if r["mode"] == "PID":
                output = r["pid"].compute(ph)
                r["co2"] = 1 if output < 0 else 0

                if not TEST_MODE:
                    set_co2(rid, r["co2"])

            elif r["mode"] == "ONOFF":
                action = onoff_control(ph, SETPOINT)
                if action is not None:
                    r["co2"] = action
                    if not TEST_MODE:
                        set_co2(rid, r["co2"])

            elif r["mode"] == "IDLE":
                continue

            # ========================
            # LOGGING
            # ========================
            insert_reading(rid, now, ph, temp, r["co2"], r["mode"])
            insert_iae(rid, r["iae"])
            insert_performance(rid, r["iae"], r["ise"], r["itae"])

            print(
                f"[R{rid}] pH={ph:.3f} Temp={temp:.2f} "
                f"CO2={r['co2']} Mode={r['mode']} "
                f"IAE={r['iae']:.3f}"
            )

        time.sleep(DT)

except KeyboardInterrupt:
    print("\nStopping...")

    for rid, r in reactors.items():
        insert_summary(rid, r["iae"], r["ise"], r["itae"], r["mode"])

finally:
    GPIO.cleanup()