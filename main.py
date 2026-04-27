import time
import os
from dotenv import load_dotenv

from controllers.pid import PID
from controllers.onoff import onoff_control
from controllers.autotune import RelayAutotune

from simulator.tetraselmis_sim import TetraselmisSim
from database.db import *

# ========================
# INIT
# ========================
load_dotenv()
init_db()

SETPOINT = float(os.getenv("SP", 7.5))
DT = float(os.getenv("DT", 5))

# ========================
# REACTORS
# ========================
reactors = {
    1: {"sim": TetraselmisSim(), "co2": 0, "mode": "AUTOTUNE", "iae": 0, "ise": 0, "itae": 0},
    2: {"sim": TetraselmisSim(), "co2": 0, "mode": "IDLE", "iae": 0, "ise": 0, "itae": 0}
}

# ========================
# AUTOTUNE PHASE
# ========================
autotune = RelayAutotune(setpoint=SETPOINT)

insert_event(1, "SYSTEM", "Starting autotune", "Relay tuning", "adjusting")

while reactors[1]["mode"] == "AUTOTUNE":
    ph, temp = reactors[1]["sim"].step(reactors[1]["co2"])

    output = autotune.step(ph)
    reactors[1]["co2"] = 1 if output < 0 else 0

    autotune.record(ph)

    insert_reading(1, time.time(), ph, temp, reactors[1]["co2"], "AUTOTUNE")
    insert_event(1, "PH", "Autotuning in progress", "Oscillation", "adjusting")

    amp, per = autotune.get_params()

    if amp and per:
        pid_vals = autotune.compute_pid(amp, per)

        if pid_vals:
            Kp, Ki, Kd = pid_vals

            # SAVE PID VALUES
            insert_pid(1, Kp, Ki, Kd)

            insert_event(1, "SYSTEM", "Autotune complete", "PID parameters ready", "success")

            # APPLY PID VALUES
            reactors[1]["pid"] = PID(Kp, Ki, Kd, setpoint=SETPOINT)

            # RESET IAE
            reactors[1]["iae"] = 0
            reactors[2]["iae"] = 0

            # START BOTH SYSTEMS
            reactors[1]["mode"] = "PID"
            reactors[2]["mode"] = "ONOFF"

            insert_event(1, "SYSTEM", "Control started", "PID active", "running")
            insert_event(2, "SYSTEM", "Control started", "ON/OFF active", "running")

            break

    time.sleep(DT)

# ========================
# MAIN LOOP
# ========================
start = time.time()

try:
    while True:
        t = time.time() - start
        now = time.time()

        for rid, r in reactors.items():
            ph, temp = r["sim"].step(r["co2"])

            error = SETPOINT - ph
            abs_error = abs(error)

            # PERFORMANCE METRICS
            r["iae"] += abs_error * DT
            r["ise"] += (error ** 2) * DT
            r["itae"] += t * abs_error * DT

            if r["mode"] == "PID":
                output = r["pid"].compute(ph)
                r["co2"] = 1 if output < 0 else 0

                if ph > SETPOINT:
                    insert_event(rid, "PH", "Above setpoint", "Inject CO2", "adjusting")
                else:
                    insert_event(rid, "PH", "Stable", "No action", "success")

            elif r["mode"] == "ONOFF":
                action = onoff_control(ph, SETPOINT)
                if action is not None:
                    r["co2"] = action

            elif r["mode"] == "IDLE":
                continue

            # LOGGING
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