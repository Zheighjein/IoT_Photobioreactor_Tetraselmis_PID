import time
import os

from dotenv import load_dotenv

from controllers.pid import PID
from controllers.autotune import RelayAutotune
from controllers.onoff import onoff_control
from controllers.heuristic import get_heuristic_pid

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
SETPOINT = float(
    os.getenv("SP", 7.5)
)

DT = float(
    os.getenv("DT", 5)
)

TEST_MODE = (
    os.getenv("TEST_MODE", "true")
    .lower() == "true"
)

# ========================
# SAFETY LIMITS
# ========================
MAX_KP = 10
MAX_KI = 5
MAX_KD = 2

# ========================
# START EVENT
# ========================
insert_event(
    0,
    "SYSTEM",
    "Startup",
    "Relay autotuning enabled",
    "running"
)

# ========================
# STATE
# ========================
state = load_state()

if state:

    start = state["start_time"]

else:

    start = time.time()

# ========================
# REACTORS
# ========================
reactors = {

    1: {
        "co2": 0,
        "mode": "AUTOTUNE",

        "iae": 0,
        "ise": 0,
        "itae": 0,

        "pid_source": None
    },

    2: {
        "co2": 0,
        "mode": "ONOFF",

        "iae": 0,
        "ise": 0,
        "itae": 0,

        "pid_source": "ONOFF"
    }
}

# ========================
# AUTOTUNE INIT
# ========================
autotune = RelayAutotune(
    setpoint=SETPOINT,
    relay_amplitude=0.2,
    sample_time=DT
)

insert_event(
    1,
    "AUTOTUNE",
    "Started",
    "Relay autotuning initiated",
    "running"
)

# ========================
# LIGHT CONFIG
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
        if cycle_time < (
            LIGHT_ON_HOURS * 3600
        ):
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

                continue

            # ========================
            # METRICS
            # ========================
            error = SETPOINT - ph
            abs_error = abs(error)

            r["iae"] += abs_error * DT
            r["ise"] += (error ** 2) * DT
            r["itae"] += t * abs_error * DT

            # ========================
            # AUTOTUNE MODE
            # ========================
            if r["mode"] == "AUTOTUNE":

                output = autotune.step(ph)

                r["co2"] = output

                if not TEST_MODE:
                    set_co2(rid, output)

                insert_reading(
                    rid,
                    now,
                    ph,
                    temp,
                    output,
                    r["mode"],
                    light_state
                )

                # ========================
                # AUTOTUNE COMPLETE
                # ========================
                if autotune.is_finished():

                    kp, ki, kd = (
                        autotune.get_params()
                    )

                    amplitude = autotune.amplitude
                    period = autotune.period
                    ku = autotune.ku

                    # ========================
                    # SAFETY CHECK
                    # ========================
                    unsafe = (

                        kp > MAX_KP or
                        ki > MAX_KI or
                        kd > MAX_KD or

                        kp <= 0 or
                        ki <= 0 or
                        kd < 0
                    )

                    # ========================
                    # FALLBACK
                    # ========================
                    if unsafe:

                        kp, ki, kd = (
                            get_heuristic_pid()
                        )

                        pid_source = "HEURISTIC"

                        insert_event(
                            1,
                            "PID",
                            "Fallback Activated",
                            (
                                "Unsafe autotune gains "
                                "detected. "
                                "Using heuristic PID."
                            ),
                            "warning"
                        )

                    else:

                        pid_source = "AUTOTUNE"

                        insert_event(
                            1,
                            "PID",
                            "Autotune Success",
                            (
                                f"Kp={kp:.3f}, "
                                f"Ki={ki:.3f}, "
                                f"Kd={kd:.3f}"
                            ),
                            "running"
                        )

                    # ========================
                    # STORE PID
                    # ========================
                    insert_pid(
                        1,
                        kp,
                        ki,
                        kd,
                        amplitude,
                        period,
                        ku,
                        pid_source
                    )

                    # ========================
                    # INIT PID
                    # ========================
                    reactors[1]["pid"] = PID(
                        kp,
                        ki,
                        kd,
                        setpoint=SETPOINT
                    )

                    reactors[1]["mode"] = "PID"

                    reactors[1]["pid_source"] = (
                        pid_source
                    )

            # ========================
            # PID MODE
            # ========================
            elif r["mode"] == "PID":

                output = (
                    r["pid"].compute(ph)
                )

                HIGH_BOUND = 7.52

                if ph >= HIGH_BOUND:

                    on_time = max(
                        2.0,
                        output * DT
                    )

                    off_time = (
                        DT - on_time
                    )

                    if on_time > 0:

                        r["co2"] = 1

                        if not TEST_MODE:
                            set_co2(rid, 1)

                        time.sleep(on_time)

                    r["co2"] = 0

                    if not TEST_MODE:
                        set_co2(rid, 0)

                    if off_time > 0:
                        time.sleep(off_time)

                else:

                    r["co2"] = 0

                    if not TEST_MODE:
                        set_co2(rid, 0)

            # ========================
            # ON/OFF
            # ========================
            elif r["mode"] == "ONOFF":

                action = onoff_control(
                    ph,
                    SETPOINT
                )

                if action is not None:

                    r["co2"] = action

                    if not TEST_MODE:
                        set_co2(
                            rid,
                            action
                        )

            # ========================
            # STORE READING
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
            # STORE PERFORMANCE
            # ========================
            insert_performance(
                rid,
                r["iae"],
                r["ise"],
                r["itae"]
            )

            print(
                f"\nR{rid} ---------\n"
                f"Mode: {r['mode']}\n"
                f"pH: {ph:.3f}\n"
                f"Temp: {temp:.2f}\n"
                f"CO2: {r['co2']}\n"
                f"IAE: {r['iae']:.3f}\n"
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

            "autotune_done": (
                reactors[1]["mode"] == "PID"
            )
        })

        time.sleep(DT)

except KeyboardInterrupt:

    print("\nStopping system...")

    for rid, r in reactors.items():

        insert_summary(
            rid,
            r["iae"],
            r["ise"],
            r["itae"],
            r["mode"],
            r["pid_source"]
        )

except Exception as e:

    print(f"\n[FATAL ERROR] {e}")

finally:

    if not TEST_MODE:

        for rid in reactors:
            set_co2(rid, 0)

        set_light(0)

        GPIO.cleanup()

    print("System shutdown complete.")