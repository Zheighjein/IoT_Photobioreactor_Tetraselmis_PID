import RPi.GPIO as GPIO
import time

PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN, GPIO.OUT)

try:
    while True:
        GPIO.output(PIN, 0)  # ON (active LOW)
        print("CO2 ON")
        time.sleep(3)

        GPIO.output(PIN, 1)  # OFF
        print("CO2 OFF")
        time.sleep(3)

except KeyboardInterrupt:
    GPIO.cleanup()