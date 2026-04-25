import time
import board
import busio
import RPi.GPIO as GPIO
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import os
from dotenv import load_dotenv

load_dotenv()
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"


# ========================
# GPIO SETUP (2 RELAYS)
# ========================
RELAY_1 = 17
RELAY_2 = 27

GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_1, GPIO.OUT)
GPIO.setup(RELAY_2, GPIO.OUT)

# ========================
# I2C + ADS1115 SETUP
# ========================
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)

ph_channel = AnalogIn(ads, ADS.P0)

# ========================
# PH SENSOR
# ========================
def read_ph():
    voltage = ph_channel.voltage

    # CALIBRATE THIS WITH BUFFER SOLUTIONS
    ph = 7 + ((2.5 - voltage) / 0.18)

    return ph

# ========================
# TEMPERATURE SENSOR (DS18B20)
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
# CO2 CONTROL
# ========================
def set_co2(reactor_id, state):
    if TEST_MODE:
        print(f"[TEST MODE] Reactor {reactor_id} CO2 -> {state}")
        return

    pin = RELAY_1 if reactor_id == 1 else RELAY_2
    GPIO.output(pin, GPIO.HIGH if state == 1 else GPIO.LOW)