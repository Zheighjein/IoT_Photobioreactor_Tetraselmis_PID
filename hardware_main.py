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

# SAFETY / TESTING FLAGS
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"  #ONLY ALTER THIS IN .ENV
USE_AUTOTUNE = os.getenv("USE_AUTOTUNE", "true").lower() == "true" #ONLY ALTER THIS IN .ENV 

print("=== RUNNING IN HARDWARE MODE ===")

if TEST_MODE:
    print("TEST MODE ENABLED (relay will NOT activate)")

print("Initializing sensors...")
time.sleep(2)  # allow I2C + sensors to stabilize

# ========================
# REACTORS (NO SIM)
# ========================
reactors = {
    1: {"co2": 0, "mode": "AUTOTUNE", "iae": 0, "ise": 0, "itae": 0},
    2: {"co2": 0, "mode": "IDLE", "iae": 0, "ise": 0, "itae": 0}
}

# ========================
# AUTOTUNE OR MANUAL PID
# ========================
if USE_AUTOTUNE:
    autotune = RelayAutotune(setpoint=SETPOINT)

    insert_event(1, "SYSTEM", "Starting autotune", "Relay tuning", "adjusting")

    while reactors[1]["mode"] == "AUTOTUNE":
        try:
            ph = read_ph()
            temp = read_temp()
        except Exception as e:
            print(f"[ERROR] Sensor read failed: {e}")
            continue

        output = autotune.step(ph)

        reactors[1]["co2"] = 1 if output < 0 else 0
        set_co2(reactors[1]["co2"])

        autotune.record(ph)

        insert_event(1, "PH", "Autotuning in progress", "Oscillation", "adjusting")

        print(f"[AUTOTUNE] pH={ph:.3f} CO2={reactors[1]['co2']}")

        amp, per = autotune.get_params()

        if amp and per:
            pid_vals = autotune.compute_pid(amp, per)

            if pid_vals:
                Kp, Ki, Kd = pid_vals

                insert_pid(1, Kp, Ki, Kd)

                insert_event(1, "SYSTEM", "Autotune complete", "PID parameters ready", "success")

                reactors[1]["pid"] = PID(Kp, Ki, Kd, setpoint=SETPOINT)

                # RESET METRICS
                for r in reactors.values():
                    r["iae"] = 0
                    r["ise"] = 0
                    r["itae"] = 0

                # START BOTH SYSTEMS
                reactors[1]["mode"] = "PID"
                reactors[2]["mode"] = "ONOFF"

                insert_event(1, "SYSTEM", "Control started", "PID active", "running")
                insert_event(2, "SYSTEM", "Control started", "ON/OFF active", "running")

                break

        time.sleep(DT)

else:
    # BACKUP PID VALUES (USE IF AUTOTUNE OFF)
    print("USING MANUAL PID VALUES")

    Kp, Ki, Kd = 2.0, 0.5, 0.1

    insert_pid(1, Kp, Ki, Kd)

    reactors[1]["pid"] = PID(Kp, Ki, Kd, setpoint=SETPOINT)

    reactors[1]["mode"] = "PID"
    reactors[2]["mode"] = "ONOFF"

    insert_event(1, "SYSTEM", "Control started", "PID active (manual)", "running")
    insert_event(2, "SYSTEM", "Control started", "ON/OFF active", "running")

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
                ph = read_ph()
                temp = read_temp()
            except Exception as e:
                print(f"[ERROR] Sensor read failed: {e}")
                continue

            # SENSOR DEBUG
            print(f"[SENSOR] pH={ph:.3f} Temp={temp:.2f}")

            error = SETPOINT - ph
            abs_error = abs(error)

            # ========================
            # PERFORMANCE METRICS
            # ========================
            r["iae"] += abs_error * DT
            r["ise"] += (error ** 2) * DT
            r["itae"] += t * abs_error * DT

            # ========================
            # CONTROL
            # ========================
            if r["mode"] == "PID":
                output = r["pid"].compute(ph)
                r["co2"] = 1 if output < 0 else 0
                set_co2(r["co2"])

                if ph > SETPOINT:
                    insert_event(rid, "PH", "Above setpoint", "Inject CO2", "adjusting")
                else:
                    insert_event(rid, "PH", "Stable", "No action", "success")

            elif r["mode"] == "ONOFF":
                action = onoff_control(ph, SETPOINT)
                if action is not None:
                    r["co2"] = action
                    set_co2(r["co2"])

            elif r["mode"] == "IDLE":
                continue

            # ========================
            # LOGGING
            # ========================
            insert_reading(rid, now, ph, temp, r["co2"], r["mode"])
            insert_iae(rid, r["iae"])

            print(
                f"[R{rid}] "
                f"pH={ph:.3f} "
                f"Temp={temp:.2f} "
                f"CO2={r['co2']} "
                f"Mode={r['mode']} "
                f"IAE={r['iae']:.3f} "
                f"ISE={r['ise']:.3f} "
                f"ITAE={r['itae']:.3f}"
            )

        time.sleep(DT)

except KeyboardInterrupt:
    print("\nStopping...")

    for rid, r in reactors.items():
        insert_summary(rid, r["iae"], r["ise"], r["itae"], r["mode"])

    print("Saved to database.")

finally:
    GPIO.cleanup()