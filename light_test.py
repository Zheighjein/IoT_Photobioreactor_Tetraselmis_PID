import time
import RPi.GPIO as GPIO

RELAY_LIGHT = 22

# Active LOW relay
LIGHT_ON = GPIO.LOW
LIGHT_OFF = GPIO.HIGH

GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_LIGHT, GPIO.OUT)

def set_light(state):
    if state:
        GPIO.output(RELAY_LIGHT, LIGHT_ON)
        print("LIGHT ON")
    else:
        GPIO.output(RELAY_LIGHT, LIGHT_OFF)
        print("LIGHT OFF")

try:
    while True:
        set_light(0)
        time.sleep(5)

        set_light(1)
        time.sleep(5)

except KeyboardInterrupt:
    print("Stopping...")

finally:
    set_light(0)
    GPIO.cleanup()