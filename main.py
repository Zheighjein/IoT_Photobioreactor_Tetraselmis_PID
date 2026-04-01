import time
import os
import pandas as pd
from dotenv import load_dotenv

from controllers.pid import PID
from controllers.onoff import onoff_control
from controllers.autotune import RelayAutotune

# ========================
# LOAD ENV VARIABLES
# ========================
load_dotenv()

SIM_MODE = os.getenv("SIM_MODE", "true").lower() == "true"
SETPOINT = float(os.getenv("SP", 7.5))
DT = float(os.getenv("DT", 1))

MODE = "AUTOTUNE"   # CHANGE THIS TO AUTOTUNE / ONOFF #DEPENDS ON THE MODE BUT MAKE SURE TO RUN EACH FOR ATLEAST 30-60 SECS

# ========================
# LOAD SIMULATOR
# ========================
if SIM_MODE:
    from simulator.tetraselmis_sim import TetraselmisSim
    sim = TetraselmisSim(initial_ph=7.5)
    print("=== RUNNING IN SIMULATION MODE ===\n")

# ========================
# LOGGING SETUP
# ========================
log_data = []
start_time = time.time()
total_iae = 0

# ========================
# AUTOTUNE PHASE
# ========================
if MODE == "AUTOTUNE":
    autotune = RelayAutotune(setpoint=SETPOINT)

    print("Starting Relay Autotuning...\n")

    co2 = 0

    while True:
        ph = sim.step(co2)

        print(f"[AUTOTUNE] pH: {ph:.3f}")

        # Relay control
        output = autotune.step(ph)

        # ✅ FIX: correct direction
        co2 = 1 if output < 0 else 0

        autotune.record(ph)

        amplitude, period = autotune.get_params()

        if amplitude and period:
            print(f"Amplitude: {amplitude:.3f}, Period: {period:.3f}")

            pid_values = autotune.compute_pid(amplitude, period)

            if pid_values:
                Kp, Ki, Kd = pid_values

                print("\n=== AUTOTUNE COMPLETE ===")
                print(f"Kp = {Kp:.4f}")
                print(f"Ki = {Ki:.4f}")
                print(f"Kd = {Kd:.4f}\n")
                break

        time.sleep(DT)

    pid = PID(Kp, Ki, Kd, setpoint=SETPOINT)
    MODE = "PID"

# ========================
# MAIN CONTROL LOOP
# ========================
print("Starting Main Control Loop...\n")

co2 = 0

try:
    while True:
        current_time = time.time() - start_time

        ph = sim.step(co2)

        error = abs(SETPOINT - ph)
        total_iae += error

        # ========================
        # CONTROL LOGIC
        # ========================
        if MODE == "PID":
            output = pid.compute(ph)

            # ✅ FIX: correct direction
            co2 = 1 if output < 0 else 0

            # 🔍 DEBUG (you can remove later)
            print(f"PID Output: {output:.4f}")

        elif MODE == "ONOFF":
            action = onoff_control(ph, SETPOINT)
            if action is not None:
                co2 = action

        # ========================
        # LOG DATA
        # ========================
        log_data.append({
            "time": current_time,
            "ph": ph,
            "setpoint": SETPOINT,
            "error": error,
            "co2": co2,
            "mode": MODE
        })

        # ========================
        # PRINT STATUS
        # ========================
        print(
            f"Time: {current_time:.1f}s | "
            f"pH: {ph:.3f} | "
            f"Error: {error:.3f} | "
            f"IAE: {total_iae:.4f} | "
            f"CO2: {co2}"
        )

        time.sleep(DT)

# ========================
# SAVE DATA ON EXIT
# ========================
except KeyboardInterrupt:
    print("\nStopping simulation...")

    df = pd.DataFrame(log_data)

    filename = f"{MODE.lower()}_log.csv"
    df.to_csv(filename, index=False)

    print(f"Data saved to {filename}")
    print(f"Final IAE: {total_iae:.4f}")