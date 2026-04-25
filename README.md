# IoT_Photobioreactor_Tetraselmis_PID
Code for the thesis "COMPARATIVE ANALYSIS OF ON/OFF AND PID CONTROL FOR PROACTIVE PH REGULATION IN A SMALL-SCALE IOT PHOTOBIOREACTOR  CULTIVATING TETRASELMIS SP."

Ctrl + , 
Search: "python.terminal.useEnvFile"
and check


# ACTIVATE THE ENVIRONMENT
1. python3 -m venv venv 
2. source venv/bin/activate


don't forget to download the requirements.txt in terminal

"pip install -r requirements.txt"

install the environment
"pip install python-dotenv"

install the library for pi (hardware)
"pip install adafruit-circuitpython-ads1x15 RPi.GPIO"

Run the environment in the terminal
"python main.py"
Then run this in another terminal
"python dashboard/app.py"

to get values for evaluation metrics, stop main.py then go back to the dashboard. 


after the output you can press
"Ctrl + C" to stop it

both reactors work simultanously now.

EVALUATION METRICS: IAE


the pbr_sim.db won't be logged for now. If you try to push/commit it nothing will happen.
Will turn this on again after final code





must turn on i2c on pi  (IGNORE for raspberry pi only)
"sudo raspi-config"
-interface options
-i2c --enable
"sudo reboot"

to test:
"i2cdetect -y 1"
if working you'll see "48"

____________________________________________________________________________________________________



- SENSOR_1 = "28-0000006dc349" - RED
- SENSOR_2 = "28-000000b2e281" - BLUE
