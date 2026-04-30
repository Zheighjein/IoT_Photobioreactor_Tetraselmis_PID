import sys
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

# Run as: python ph_calibration.py 1   (Reactor 1, channel 0)
#         python ph_calibration.py 2   (Reactor 2, channel 1)
reactor_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1

CHANNEL    = 0 if reactor_id == 1 else 1
CAL_FILE   = f"ph_calibration_r{reactor_id}.json"

chan = AnalogIn(ads, CHANNEL)

print(f"\n=== Calibrating Reactor {reactor_id} (ADS1115 channel {CHANNEL}) ===")
print(f"Calibration will be saved to: {CAL_FILE}\n")


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
    print("=== pH CALIBRATION (4 & 7) ===")

    input("Place probe in pH 7 solution, wait ~10s, then press ENTER...")
    v7 = read_voltage()
    print(f"Voltage @ pH 7: {v7:.4f} V\n")

    input("Rinse probe, place in pH 4 solution, wait ~10s, then press ENTER...")
    v4 = read_voltage()
    print(f"Voltage @ pH 4: {v4:.4f} V\n")

    slope  = (7.0 - 4.0) / (v7 - v4)
    offset = 7.0 - slope * v7

    print("=== Calibration Complete ===")
    print(f"Slope:  {slope:.4f}")
    print(f"Offset: {offset:.4f}")

    with open(CAL_FILE, "w") as f:
        json.dump({"slope": slope, "offset": offset}, f)

    print(f"Saved to {CAL_FILE}\n")
    return slope, offset


# =========================
# LOAD OR RUN CALIBRATION
# =========================
try:
    with open(CAL_FILE, "r") as f:
        data = json.load(f)
    slope  = data["slope"]
    offset = data["offset"]
    print(f"Loaded existing calibration: slope={slope:.4f}, offset={offset:.4f}\n")
    redo = input("Re-calibrate? (y/n): ").strip().lower()
    if redo == 'y':
        slope, offset = calibrate()
except FileNotFoundError:
    print("No calibration file found. Starting calibration...\n")
    slope, offset = calibrate()


# =========================
# LIVE MONITOR
# =========================
print("=== LIVE pH MONITOR === (Ctrl+C to stop)\n")

while True:
    voltage = read_voltage()
    ph = slope * voltage + offset
    ph = max(0.0, min(14.0, ph))

    print(f"R{reactor_id} | Voltage: {voltage:.3f} V | pH: {ph:.3f}")
    print("----------------------")

    time.sleep(1)
