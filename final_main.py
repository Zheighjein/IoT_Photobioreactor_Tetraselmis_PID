import time
import os

from dotenv import load_dotenv

from controllers.pid import PID
from controllers.onoff import onoff_control
from controllers.heuristic import get_pid_values

from controllers.hardware import (
    read_ph,
    read_temp,
    set_co2,
    set_light
)

from database.final_db import *

import RPi.GPIO as GPIO

# ========================
# LOAD ENV
# ========================
load_dotenv()

# ========================
# INIT DB
# ========================
init_db()

# ========================
# CONFIG
# ========================
SETPOINT = float(os.getenv("SP", 7.5))
DT = float(os.getenv("DT", 5))

TEST_MODE = (
    os.getenv("TEST_MODE", "true")
    .lower() == "true"
)

# ========================
# PID VALUES
# ========================
pid_values = get_pid_values()

Kp = pid_values["kp"]
Ki = pid_values["ki"]
Kd = pid_values["kd"]

# ========================
# START EVENT
# ========================
insert_event(
    0,
    "SYSTEM",
    "Startup",
    "final_main.py started",
    "running"
)

print("===================================")
print("HEURISTIC PID CONTROLLER ACTIVE")
print("===================================")

print(f"Kp = {Kp}")
print(f"Ki = {Ki}")
print(f"Kd = {Kd}")

# ========================
# LOAD STATE
# ========================
state = load_state()

if state:

    print("Restoring previous state...")

    start = state["start_time"]

    reactors = {

        1: {
            "co2": 0,
            "mode": "PID",

            "iae": state["r1_iae"],
            "ise": state["r1_ise"],
            "itae": state["r1_itae"]
        },

        2: {
            "co2": 0,
            "mode": "ONOFF",

            "iae": state["r2_iae"],
            "ise": state["r2_ise"],
            "itae": state["r2_itae"]
        }
    }

else:

    start = time.time()

    reactors = {

        1: {
            "co2": 0,
            "mode": "PID",

            "iae": 0,
            "ise": 0,
            "itae": 0
        },

        2: {
            "co2": 0,
            "mode": "ONOFF",

            "iae": 0,
            "ise": 0,
            "itae": 0
        }
    }

# ========================
# SAVE PID VALUES
# ========================
insert_pid(
    1,
    Kp,
    Ki,
    Kd
)

# ========================
# INIT PID
# ========================
reactors[1]["pid"] = PID(
    Kp,
    Ki,
    Kd,
    setpoint=SETPOINT
)

# ========================
# MODE EVENTS
# ========================
insert_event(
    1,
    "MODE",
    "PID Enabled",
    "Heuristic PID controller active",
    "running"
)

insert_event(
    2,
    "MODE",
    "ONOFF Enabled",
    "Baseline controller active",
    "running"
)

# ========================
# LIGHT CYCLE
# ========================
LIGHT_ON_HOURS = 12
LIGHT_OFF_HOURS = 12

LIGHT_CYCLE = (
    LIGHT_ON_HOURS +
    LIGHT_OFF_HOURS
) * 3600

last_light = None

# ========================
# MAIN LOOP
# ========================
try:

    while True:

        now = time.time()

        t = now - start

        elapsed = int(now - start)

        cycle_time = elapsed % LIGHT_CYCLE

        # ========================
        # LIGHT CONTROL
        # ========================
        if cycle_time < (LIGHT_ON_HOURS * 3600):
            light_state = 1
        else:
            light_state = 0

        if light_state != last_light:

            insert_event(
                0,
                "LIGHT",
                "Changed",
                f"Light={light_state}",
                "running"
            )

            last_light = light_state

        if not TEST_MODE:
            set_light(light_state)

        # ========================
        # REACTORS
        # ========================
        for rid, r in reactors.items():

            try:

                if rid == 1:
                    temp = read_temp(
                        "28-0000006dc349"
                    )
                else:
                    temp = read_temp(
                        "28-000000b2e281"
                    )

                ph = read_ph(rid)

            except Exception as e:

                insert_event(
                    rid,
                    "SENSOR",
                    "Read Failed",
                    str(e),
                    "error"
                )

                print(
                    f"[ERROR] "
                    f"Sensor failure R{rid}: {e}"
                )

                continue

            # ========================
            # ERROR METRICS
            # ========================
            error = SETPOINT - ph
            abs_error = abs(error)

            r["iae"] += abs_error * DT
            r["ise"] += (error ** 2) * DT
            r["itae"] += t * abs_error * DT

            # ========================
            # PID CONTROL
            # ========================
            if r["mode"] == "PID":

                output = r["pid"].compute(ph)

                HIGH_BOUND = 7.52

                print(
                    f"[PID] "
                    f"pH={ph:.3f} "
                    f"Output={output:.3f}"
                )

                if ph >= HIGH_BOUND:

                    on_time = max(
                        2.0,
                        output * DT
                    )

                    off_time = DT - on_time

                    # CO2 ON
                    if on_time > 0:

                        r["co2"] = 1

                        if not TEST_MODE:
                            set_co2(rid, 1)

                        insert_event(
                            rid,
                            "CO2",
                            "Activated",
                            f"ON for {on_time:.2f}s",
                            "running"
                        )

                        insert_reading(
                            rid,
                            now,
                            ph,
                            temp,
                            1,
                            r["mode"],
                            light_state
                        )

                        time.sleep(on_time)

                    # CO2 OFF
                    r["co2"] = 0

                    if not TEST_MODE:
                        set_co2(rid, 0)

                    insert_event(
                        rid,
                        "CO2",
                        "Deactivated",
                        "Injection stopped",
                        "idle"
                    )

                    insert_reading(
                        rid,
                        now,
                        ph,
                        temp,
                        0,
                        r["mode"],
                        light_state
                    )

                    if off_time > 0:
                        time.sleep(off_time)

                else:

                    r["co2"] = 0

                    if not TEST_MODE:
                        set_co2(rid, 0)

            # ========================
            # ON/OFF CONTROL
            # ========================
            elif r["mode"] == "ONOFF":

                action = onoff_control(
                    ph,
                    SETPOINT
                )

                if action is not None:

                    if action != r["co2"]:

                        state_name = (
                            "Activated"
                            if action == 1
                            else "Deactivated"
                        )

                        insert_event(
                            rid,
                            "CO2",
                            state_name,
                            "ONOFF control",
                            "running"
                        )

                    r["co2"] = action

                    if not TEST_MODE:
                        set_co2(
                            rid,
                            r["co2"]
                        )

            # ========================
            # SAVE READING
            # ========================
            insert_reading(
                rid,
                now,
                ph,
                temp,
                r["co2"],
                r["mode"],
                light_state
            )

            # ========================
            # SAVE PERFORMANCE
            # ========================
            insert_performance(
                rid,
                r["iae"],
                r["ise"],
                r["itae"]
            )

            # ========================
            # CONSOLE
            # ========================
            print(
                f"\nR{rid} -----------\n"
                f"pH: {ph:.3f}\n"
                f"Temp: {temp:.2f}\n"
                f"CO2: {r['co2']}\n"
                f"Light: {light_state}\n"
                f"Mode: {r['mode']}\n"
                f"IAE: {r['iae']:.3f}\n"
                f"ISE: {r['ise']:.3f}\n"
                f"ITAE: {r['itae']:.3f}\n"
            )

        # ========================
        # SAVE STATE
        # ========================
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

            "pid_initialized": True
        })

        time.sleep(DT)

# ========================
# CTRL+C
# ========================
except KeyboardInterrupt:

    print("\nStopping system...")

    for rid, r in reactors.items():

        insert_summary(
            rid,
            r["iae"],
            r["ise"],
            r["itae"],
            r["mode"]
        )

# ========================
# FATAL ERROR
# ========================
except Exception as e:

    print(f"\n[FATAL ERROR] {e}")

    for rid, r in reactors.items():

        insert_summary(
            rid,
            r["iae"],
            r["ise"],
            r["itae"],
            r["mode"]
        )

# ========================
# CLEANUP
# ========================
finally:

    if not TEST_MODE:

        for rid in reactors:
            set_co2(rid, 0)

        set_light(0)

        GPIO.cleanup()

    print("System shutdown complete.")