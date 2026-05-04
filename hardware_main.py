import time
import os
from dotenv import load_dotenv

from controllers.pid import PID
from controllers.onoff import onoff_control
from controllers.autotune import RelayAutotune

from controllers.hardware import read_ph, read_temp, set_co2, set_light

from database.db import *

import RPi.GPIO as GPIO

# ========================
# INIT
# ========================
load_dotenv()
init_db()
insert_event(0, "SYSTEM", "Startup", "Main loop started", "running")

# >>> LOAD ENV FIRST (FIXED ORDER)
SETPOINT = float(os.getenv("SP", 7.5))
DT = float(os.getenv("DT", 5))

TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
USE_AUTOTUNE = os.getenv("USE_AUTOTUNE", "true").lower() == "true"

# ========================
# LOAD STATE (FIXED)
# ========================
state = load_state()

if state:
    print("Restoring previous system state...")

    start = state["start_time"]

    reactors = {
        1: {"co2": 0, "mode": state["r1_mode"], "iae": state["r1_iae"], "ise": state["r1_ise"], "itae": state["r1_itae"]},
        2: {"co2": 0, "mode": state["r2_mode"], "iae": state["r2_iae"], "ise": state["r2_ise"], "itae": state["r2_itae"]}
    }

    if state["autotune_done"]:
        USE_AUTOTUNE = False

else:
    start = time.time()

    reactors = {
        1: {"co2": 0, "mode": "AUTOTUNE", "iae": 0, "ise": 0, "itae": 0},
        2: {"co2": 0, "mode": "IDLE", "iae": 0, "ise": 0, "itae": 0}
    }

print("=== RUNNING IN HARDWARE MODE ===")

if TEST_MODE:
    print("TEST MODE ENABLED (relay will NOT activate)")

print("Initializing sensors...")
time.sleep(2)

# ========================
# LIGHT CONFIG
# ========================
LIGHT_ON_HOURS  = 12
LIGHT_OFF_HOURS = 12
LIGHT_CYCLE = (LIGHT_ON_HOURS + LIGHT_OFF_HOURS) * 3600

last_light = None

# ========================
# AUTOTUNE FLAG
# ========================
autotune_done_flag = False if USE_AUTOTUNE else True

# ========================
# AUTOTUNE (UNCHANGED LOGIC, FIXED LIGHT + FLAG)
# ========================
if USE_AUTOTUNE:
    autotune = RelayAutotune(setpoint=SETPOINT)

    insert_event(1, "SYSTEM", "Starting autotune", "Relay tuning", "adjusting")

    AUTOTUNE_DURATION = int(os.getenv('AUTOTUNE_DURATION', 10800))
    autotune_start = time.time()

    while time.time() - autotune_start < AUTOTUNE_DURATION:
        try:
            ph = read_ph(1)
            temp = read_temp("28-0000006dc349")
        except Exception as e:
            insert_event(1, "SENSOR", "Read Failed", str(e), "error")
            print(f"[ERROR] Sensor read failed: {e}")
            time.sleep(DT)
            continue

        elapsed = int(time.time() - start)
        cycle_time = elapsed % LIGHT_CYCLE

        if cycle_time < (LIGHT_ON_HOURS * 3600):
            light_state = 1
        else:
            light_state = 0

        if light_state != last_light:
            insert_event(0, "LIGHT", "Changed", f"Light={light_state}", "running")
            last_light = light_state

        if not TEST_MODE:
            set_light(light_state)

        output = autotune.step(ph)

        reactors[1]["co2"] = 1 if output < 0 else 0

        if not TEST_MODE:
            set_co2(1, reactors[1]["co2"])

        autotune.record(ph)
        insert_reading(1, time.time(), ph, temp, reactors[1]["co2"], "AUTOTUNE", light_state)

        print(
            f"[AUTOTUNE] t={int(time.time()-autotune_start)}s "
            f"pH={ph:.3f} "
            f"Temp={temp:.2f} "
            f"CO2={reactors[1]['co2']} "
            f"Light={light_state}"
        )

        time.sleep(DT)

    print(">>> EXITED AUTOTUNE LOOP <<<")
    print("Autotune finished. Computing PID...")

    amp, per = autotune.get_params()
    pid_vals = autotune.compute_pid(amp, per)

    if not pid_vals:
        print("⚠️ Autotune failed → using fallback PID values")
        Kp, Ki, Kd = 2.0, 0.5, 0.1
        amp, per, ku = None, None, None
    else:
        Kp, Ki, Kd = pid_vals
        ku = (4 * 1.0) / (3.14159 * amp)

    insert_pid(1, Kp, Ki, Kd, amp, per, ku)

    reactors[1]["pid"] = PID(Kp, Ki, Kd, setpoint=SETPOINT)

    for r in reactors.values():
        r["iae"] = 0
        r["ise"] = 0
        r["itae"] = 0

    reactors[1]["mode"] = "PID"
    reactors[2]["mode"] = "ONOFF"

    insert_event(1, "MODE", "Switched to PID", "Control active", "running")
    insert_event(2, "MODE", "Switched to ONOFF", "Control active", "running")

    autotune_done_flag = True

    print(">>> MODE SWITCH SUCCESS <<<")

    insert_event(1, "SYSTEM", "Autotune complete", "PID active", "success")
    insert_event(2, "SYSTEM", "Control started", "ON/OFF active", "running")

else:
    print("USING MANUAL PID VALUES")

    Kp, Ki, Kd = 2.0, 0.5, 0.1

    insert_pid(1, Kp, Ki, Kd, None, None, None)

    reactors[1]["pid"] = PID(Kp, Ki, Kd, setpoint=SETPOINT)

    reactors[1]["mode"] = "PID"
    reactors[2]["mode"] = "ONOFF"

# ========================
# MAIN LOOP 
# ========================
try:
    while True:
        t = time.time() - start
        now = time.time()

        elapsed = int(now - start)
        cycle_time = elapsed % LIGHT_CYCLE

        if cycle_time < (LIGHT_ON_HOURS * 3600):
            light_state = 1
        else:
            light_state = 0

        if light_state != last_light:
            insert_event(0, "LIGHT", "Changed", f"Light={light_state}", "running")
            last_light = light_state

        if not TEST_MODE:
            set_light(light_state)
            print(f"Light State: {light_state}")

        for rid, r in reactors.items():

            try:
                if rid == 1:
                    temp = read_temp("28-0000006dc349")
                else:
                    temp = read_temp("28-000000b2e281")

                ph = read_ph(rid)

            except Exception as e:
                insert_event(rid, "SENSOR", "Read Failed", str(e), "error")
                print(f"[ERROR] Sensor read failed for R{rid}: {e}")
                continue

            error = SETPOINT - ph
            abs_error = abs(error)

            r["iae"] += abs_error * DT
            r["ise"] += (error ** 2) * DT
            r["itae"] += t * abs_error * DT

            LOW_BOUND = 7.4
            HIGH_BOUND = 7.52

            if r["mode"] == "PID":
                output = r["pid"].compute(ph)

                #FIXED: throttled PID logging
                if int(t) % 30 == 0 and int((t - DT)) % 30 != 0:
                    insert_event(rid, "PID", "Compute", f"Output={output:.3f}, pH={ph:.3f}", "running")

                print(f"[PID DEBUG] pH={ph:.3f} Output={output:.3f}")

                if ph >= HIGH_BOUND:
                    on_time = max(2.0, output * DT)
                    off_time = DT - on_time

                    if on_time > 0:
                        r["co2"] = 1
                        if not TEST_MODE:
                            set_co2(rid, 1)

                        insert_event(rid, "CO2", "Activated", f"ON for {on_time:.2f}s", "running")
                        insert_reading(rid, now, ph, temp, 1, r["mode"], light_state)

                        time.sleep(on_time)

                    r["co2"] = 0
                    if not TEST_MODE:
                        set_co2(rid, 0)

                    insert_event(rid, "CO2", "Deactivated", "Injection stopped", "stopped")
                    insert_reading(rid, now, ph, temp, 0, r["mode"], light_state)

                    if off_time > 0:
                        time.sleep(off_time)

                else:
                    if r["co2"] != 0:
                        insert_event(rid, "CO2", "Deactivated", "Below threshold", "idle")

                    r["co2"] = 0
                    if not TEST_MODE:
                        set_co2(rid, 0)

            elif r["mode"] == "ONOFF":
                action = onoff_control(ph, SETPOINT)

                if action is not None:

                    # LOG ONLY WHEN STATE CHANGES
                    if action != r["co2"]:
                        state = "Activated" if action == 1 else "Deactivated"
                        insert_event(rid, "CO2", state, "ON/OFF control", "running")

                    r["co2"] = action

                    if not TEST_MODE:
                        set_co2(rid, r["co2"])

            elif r["mode"] == "IDLE":
                continue

            #Prevent duplicate readings during PID ON/OFF cycle
            if r["mode"] != "PID" or ph < HIGH_BOUND:
                insert_reading(rid, now, ph, temp, r["co2"], r["mode"], light_state)

            insert_performance(rid, r["iae"], r["ise"], r["itae"])

            print(
                f"R{rid} ----------\n"
                f"pH: {ph:.3f}\n"
                f"Temp: {temp:.2f}\n"
                f"CO2: {r['co2']}\n"
                f"Light: {light_state}\n"
                f"Mode: {r['mode']}\n"
                f"IAE: {r['iae']:.3f}\n"
                f"ISE: {r['ise']:.3f}\n"
                f"ITAE: {r['itae']:.3f}\n"
            )

        save_state({
            "start_time": start,
            "r1_iae": reactors[1]["iae"],
            "r1_ise": reactors[1]["ise"],
            "r1_itae": reactors[1]["itae"],
            "r1_mode": reactors[1]["mode"],
            "r2_iae": reactors[2]["iae"],
            "r2_ise": reactors[2]["ise"],
            "r2_itae": reactors[2]["itae"],
            "r2_mode": reactors[2]["mode"],
            "autotune_done": autotune_done_flag
        })

        time.sleep(DT)

except KeyboardInterrupt:
    print("\nStopping...")
    for rid, r in reactors.items():
        insert_summary(rid, r["iae"], r["ise"], r["itae"], r["mode"])

except Exception as e:
    print(f"\n[FATAL ERROR] {e}")
    for rid, r in reactors.items():
        insert_summary(rid, r["iae"], r["ise"], r["itae"], r["mode"])

finally:
    if not TEST_MODE:
        for rid in reactors:
            set_co2(rid, 0)
        set_light(0)
        GPIO.cleanup()