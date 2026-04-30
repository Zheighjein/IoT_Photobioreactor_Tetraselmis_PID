import time
import json
import board
import busio
import RPi.GPIO as GPIO
import os
from dotenv import load_dotenv

import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# ========================
# ENV
# ========================
load_dotenv()
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"

# ========================
# LOAD CALIBRATION
# ========================
def load_cal(reactor_id):
    cal_file = os.path.join(os.path.dirname(__file__), '..', f'ph_calibration_r{reactor_id}.json')
    try:
        with open(cal_file, 'r') as f:
            cal = json.load(f)
        print(f"R{reactor_id} pH calibration loaded: slope={cal['slope']:.4f}, offset={cal['offset']:.4f}")
        return cal['slope'], cal['offset']
    except FileNotFoundError:
        print(f"⚠️  ph_calibration_r{reactor_id}.json not found — run: python ph_calibration.py {reactor_id}")
        slope = (7.0 - 4.0) / (2.5 - 3.0)
        return slope, 7.0 - slope * 2.5

SLOPE_R1, INTERCEPT_R1 = load_cal(1)
SLOPE_R2, INTERCEPT_R2 = load_cal(2)

# ========================
# GPIO SETUP
# ========================
RELAY_1     = 17   # CO2 Reactor 1
RELAY_2     = 27   # CO2 Reactor 2
RELAY_LIGHT = 22   # LIGHT

# Active LOW relay: LOW = ON, HIGH = OFF
RELAY_ON  = GPIO.LOW
RELAY_OFF = GPIO.HIGH

if not TEST_MODE:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAY_1,     GPIO.OUT)
    GPIO.setup(RELAY_2,     GPIO.OUT)
    GPIO.setup(RELAY_LIGHT, GPIO.OUT)

    GPIO.output(RELAY_1,     RELAY_OFF)
    GPIO.output(RELAY_2,     RELAY_OFF)
    GPIO.output(RELAY_LIGHT, RELAY_OFF)

# ========================
# I2C + ADS1115 SETUP
# ========================
if not TEST_MODE:
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS.ADS1115(i2c)
    ph_channels = {
        1: AnalogIn(ads, 0),
        2: AnalogIn(ads, 1)
    }
else:
    ph_channels = {}

# ========================
# PH SENSOR
# ========================
def read_ph(reactor_id):
    if reactor_id not in ph_channels:
        raise ValueError(f"No pH channel configured for Reactor {reactor_id}")

    voltage = ph_channels[reactor_id].voltage
    slope     = SLOPE_R1     if reactor_id == 1 else SLOPE_R2
    intercept = INTERCEPT_R1 if reactor_id == 1 else INTERCEPT_R2

    ph = intercept + slope * voltage
    ph = max(0.0, min(14.0, ph))
    return round(ph, 3)

# ========================
# TEMPERATURE SENSOR
# ========================
def read_temp(sensor_id):
    path = f"/sys/bus/w1/devices/{sensor_id}/w1_slave"
    with open(path, "r") as f:
        lines = f.readlines()

    if "YES" not in lines[0]:
        raise Exception("Temp sensor read error")

    temp_c = float(lines[1].split("t=")[-1]) / 1000.0
    return temp_c

# ========================
# CO2 CONTROL
# ========================
def set_co2(reactor_id, state):
    if TEST_MODE:
        print(f"[TEST MODE] Reactor {reactor_id} CO2 -> {state}")
        return

    pin = RELAY_1 if reactor_id == 1 else RELAY_2
    GPIO.output(pin, RELAY_ON if state else RELAY_OFF)

# ========================
# LIGHT CONTROL
# ========================
def set_light(state):
    if TEST_MODE:
        print(f"[TEST MODE] LIGHT -> {state}")
        return

    GPIO.output(RELAY_LIGHT, RELAY_ON if state else RELAY_OFF)
    print("LIGHT ON" if state else "LIGHT OFF")
