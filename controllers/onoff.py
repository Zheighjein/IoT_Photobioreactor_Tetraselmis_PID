
def onoff_control(ph, setpoint=7.5, tolerance=0.1):
    if ph > setpoint + tolerance:
        return 1  # CO2 ON
    elif ph < setpoint - tolerance:
        return 0  # CO2 OFF
    return None  # no change