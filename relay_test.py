import time
import RPi.GPIO as GPIO

PINS = [22, 17, 27]

GPIO.setmode(GPIO.BCM)

for pin in PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.HIGH)  # OFF for active LOW relay

try:
    while True:
        for pin in PINS:
            print(f"Testing GPIO {pin} ON")
            GPIO.output(pin, GPIO.LOW)
            time.sleep(3)

            print(f"Testing GPIO {pin} OFF")
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(2)

except KeyboardInterrupt:
    pass

finally:
    for pin in PINS:
        GPIO.output(pin, GPIO.HIGH)
    GPIO.cleanup()
