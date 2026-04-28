import time
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
# GPIO SETUP
# ========================
RELAY_1 = 17      # CO2 Reactor 1
RELAY_2 = 27      # CO2 Reactor 2
RELAY_LIGHT = 22  # LIGHT

# Active LOW relay:
# LOW  = ON
# HIGH = OFF
RELAY_ON = GPIO.LOW
RELAY_OFF = GPIO.HIGH

if not TEST_MODE:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAY_1, GPIO.OUT)
    GPIO.setup(RELAY_2, GPIO.OUT)
    GPIO.setup(RELAY_LIGHT, GPIO.OUT)

    # Start everything OFF
    GPIO.output(RELAY_1, RELAY_OFF)
    GPIO.output(RELAY_2, RELAY_OFF)
    GPIO.output(RELAY_LIGHT, RELAY_OFF)

# ========================
# I2C + ADS1115 SETUP
# ========================
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)

ph_channels = {
    1: AnalogIn(ads, 0),
    2: AnalogIn(ads, 1)
}

# ========================
# PH SENSOR
# ========================
def read_ph(reactor_id):
    if reactor_id not in ph_channels:
        raise ValueError(f"No pH channel configured for Reactor {reactor_id}")

    channel = ph_channels[reactor_id]
    voltage = channel.voltage

    ph = 7 + ((2.5 - voltage) / 0.18)
    return ph

# ========================
# TEMPERATURE SENSOR
# ========================
def read_temp(sensor_id):
    path = f"/sys/bus/w1/devices/{sensor_id}/w1_slave"
    with open(path, "r") as f:
        lines = f.readlines()

    if "YES" not in lines[0]:
        raise Exception("Temp sensor read error")

    temp_str = lines[1].split("t=")[-1]
    temp_c = float(temp_str) / 1000.0
    return temp_c

# ========================
# SECOND ANALOG PH CHANNEL
# ========================
def read_channel_2():
    return ph_channels[2].voltage

# ========================
# CO2 CONTROL
# ========================
def set_co2(reactor_id, state):
    if TEST_MODE:
        print(f"[TEST MODE] Reactor {reactor_id} CO2 -> {state}")
        return

    pin = RELAY_1 if reactor_id == 1 else RELAY_2

    if state:
        GPIO.output(pin, RELAY_ON)
    else:
        GPIO.output(pin, RELAY_OFF)

# ========================
# LIGHT CONTROL
# ========================
def set_light(state):
    if TEST_MODE:
        print(f"[TEST MODE] LIGHT -> {state}")
        return

    if state:
        GPIO.output(RELAY_LIGHT, RELAY_ON)
        print("LIGHT ON")
    else:
        GPIO.output(RELAY_LIGHT, RELAY_OFF)
        print("LIGHT OFF")