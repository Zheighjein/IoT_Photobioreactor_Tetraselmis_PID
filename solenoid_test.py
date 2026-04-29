import time
import RPi.GPIO as GPIO

# Two CO2 relays
CO2_1 = 17
CO2_2 = 27

# Active LOW relay
ON = GPIO.LOW
OFF = GPIO.HIGH

GPIO.setmode(GPIO.BCM)
GPIO.setup(CO2_1, GPIO.OUT)
GPIO.setup(CO2_2, GPIO.OUT)

def co2_on():
    GPIO.output(CO2_1, ON)
    GPIO.output(CO2_2, ON)
    print("CO2 BOTH OPEN")

def co2_off():
    GPIO.output(CO2_1, OFF)
    GPIO.output(CO2_2, OFF)
    print("CO2 BOTH CLOSED")

try:
    # Start closed
    co2_off()
    time.sleep(2)

    while True:
        # Open briefly → release pressure / bubbles
        co2_on()
        time.sleep(2)

        # Close → stabilize
        co2_off()
        time.sleep(5)

except KeyboardInterrupt:
    print("Stopping...")

finally:
    co2_off()
    GPIO.cleanup()

