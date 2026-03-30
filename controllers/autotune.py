import time
import math

class RelayAutotune:
    def __init__(self, setpoint=7.5, relay_amplitude=1.0):
        self.setpoint = setpoint
        self.relay_amplitude = relay_amplitude

        self.state = 1
        self.history = []

    def step(self, current_value):
        error = self.setpoint - current_value

        # Relay switching
        if error > 0:
            self.state = 1
        else:
            self.state = -1

        return self.state * self.relay_amplitude

    def record(self, value):
        self.history.append((time.time(), value))

        # Keep recent data only
        if len(self.history) > 50:
            self.history.pop(0)

    def get_params(self):
        if len(self.history) < 10:
            return None, None

        values = [v for t, v in self.history]
        times = [t for t, v in self.history]

        max_val = max(values)
        min_val = min(values)

        amplitude = (max_val - min_val) / 2

        # Estimate period (last oscillation)
        try:
            period = times[-1] - times[-5]
        except:
            return None, None

        return amplitude, period

    def compute_pid(self, amplitude, period):
        if amplitude == 0 or period is None:
            return None

        Ku = (4 * self.relay_amplitude) / (math.pi * amplitude)
        Pu = period

        # Ziegler-Nichols PID tuning
        Kp = 0.6 * Ku
        Ki = 1.2 * Ku / Pu
        Kd = 0.075 * Ku * Pu

        return Kp, Ki, Kd