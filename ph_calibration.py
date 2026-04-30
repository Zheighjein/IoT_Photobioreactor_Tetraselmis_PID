import time
import json
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# =========================
# SETUP
# =========================
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
ads.gain = 2
chan = AnalogIn(ads, 0)

CAL_FILE = "ph_calibration.json"


# =========================
# STABLE VOLTAGE READ
# =========================
def read_voltage(samples=15):
    vals = []
    for _ in range(samples):
        vals.append(chan.voltage)
        time.sleep(0.05)

    vals.sort()
    avg = sum(vals[3:-3]) / (len(vals) - 6)
    return avg


# =========================
# CALIBRATION (4 & 7)
# =========================
def calibrate():
    print("\n=== pH CALIBRATION (4 & 7) ===")

    # --- pH 7 ---
    input("Place probe in pH 7 solution, wait ~10s, then press ENTER...")
    v7 = read_voltage()
    print(f"Voltage @ pH 7: {v7:.4f} V\n")

    # --- pH 4 ---
    input("Rinse probe, place in pH 4 solution, wait ~10s, then press ENTER...")
    v4 = read_voltage()
    print(f"Voltage @ pH 4: {v4:.4f} V\n")

    # Compute calibration
    slope = (7.0 - 4.0) / (v7 - v4)
    offset = 7.0 - slope * v7

    print("=== Calibration Complete ===")
    print(f"Slope:  {slope:.4f}")
    print(f"Offset: {offset:.4f}")

    # Save
    with open(CAL_FILE, "w") as f:
        json.dump({"slope": slope, "offset": offset}, f)

    print("Saved to ph_calibration.json\n")

    return slope, offset


# =========================
# LOAD CALIBRATION
# =========================
def load_calibration():
    try:
        with open(CAL_FILE, "r") as f:
            data = json.load(f)
            print("Loaded saved calibration.\n")
            return data["slope"], data["offset"]
    except:
        print("No calibration found. Starting calibration...")
        return calibrate()


# =========================
# MAIN
# =========================
slope, offset = load_calibration()

print("=== LIVE pH MONITOR ===\n")

while True:
    voltage = read_voltage()
    ph = slope * voltage + offset

    print(f"Voltage: {voltage:.3f} V")
    print(f"pH: {ph:.3f}")
    print("----------------------")

    time.sleep(1)
