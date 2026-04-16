import time
import board
import busio
import RPi.GPIO as GPIO
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# ========================
# GPIO SETUP
# ========================
RELAY_PIN = 17  # GPIO17 (change if needed)

GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT)

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

    # WE NEED TO CALIBRATE THIS USING BUFFER SOLUTIONS IN THE KIT
    ph = 7 + ((2.5 - voltage) / 0.18)

    return ph

# ========================
# TEMPERATURE SENSOR (PLACEHOLDER)
# ========================
def read_temp():
    # Replace with real sensor later 
    return 25.0

# ========================
# CO2 CONTROL
# ========================
def set_co2(state):
    GPIO.output(RELAY_PIN, GPIO.HIGH if state == 1 else GPIO.LOW)