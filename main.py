import time
import os
from dotenv import load_dotenv

from controllers.pid import PID
from controllers.onoff import onoff_control
from controllers.autotune import get_heuristic_pid

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
# HEURISTIC PID PARAMS
# ========================
Kp, Ki, Kd = get_heuristic_pid()
insert_pid(1, Kp, Ki, Kd, None, None, None)
print(f">>> Heuristic PID — Kp={Kp} Ki={Ki} Kd={Kd}")

# ========================
# REACTORS
# ========================
reactors = {
    1: {"sim": TetraselmisSim(), "co2": 0, "mode": "PID",   "iae": 0, "ise": 0, "itae": 0, "pid": PID(Kp, Ki, Kd, setpoint=SETPOINT)},
    2: {"sim": TetraselmisSim(), "co2": 0, "mode": "ONOFF", "iae": 0, "ise": 0, "itae": 0}
}

insert_event(1, "SYSTEM", "Control started", "PID active", "running")
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
            ph, temp = r["sim"].step(r["co2"])

            error = SETPOINT - ph
            abs_error = abs(error)

            # PERFORMANCE METRICS
            r["iae"]  += abs_error * DT
            r["ise"]  += (error ** 2) * DT
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

            # LOGGING
            insert_reading(rid, now, ph, temp, r["co2"], r["mode"], 0)
            insert_performance(rid, r["iae"], r["ise"], r["itae"])

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
