import time
import math


class RelayAutotune:
    def __init__(
        self,
        setpoint=7.5,
        relay_amplitude=1.0,
        hysteresis=0.05,
        max_history=500,
        min_cycles=3,
        min_amplitude=0.02,
    ):
        self.setpoint = setpoint
        self.relay_amplitude = relay_amplitude
        self.hysteresis = hysteresis
        self.max_history = max_history
        self.min_cycles = min_cycles
        self.min_amplitude = min_amplitude

        # In your hardware_main.py:
        # output < 0  -> CO2 ON
        # output >= 0 -> CO2 OFF
        self.state = 1   # start with CO2 OFF
        self.history = []

    def step(self, current_value):
        upper = self.setpoint + self.hysteresis
        lower = self.setpoint - self.hysteresis

        # Hysteresis relay:
        # if pH too high -> turn CO2 ON
        # if pH too low  -> turn CO2 OFF
        if current_value > upper:
            self.state = -1   # CO2 ON
        elif current_value < lower:
            self.state = 1    # CO2 OFF

        return self.state * self.relay_amplitude

    def record(self, value, timestamp=None):
        if timestamp is None:
            timestamp = time.time()

        self.history.append((timestamp, value, self.state))

        if len(self.history) > self.max_history:
            self.history.pop(0)

    def _find_extrema(self):
        if len(self.history) < 7:
            return [], []

        values = [v for _, v, _ in self.history]
        times = [t for t, _, _ in self.history]

        peaks = []
        troughs = []

        for i in range(1, len(values) - 1):
            if values[i] > values[i - 1] and values[i] > values[i + 1]:
                peaks.append((times[i], values[i]))
            elif values[i] < values[i - 1] and values[i] < values[i + 1]:
                troughs.append((times[i], values[i]))

        return peaks, troughs

    def get_params(self):
        # Must return only 2 values because hardware_main.py does:
        # amp, per = autotune.get_params()

        if len(self.history) < 20:
            return None, None

        peaks, troughs = self._find_extrema()

        if len(peaks) < self.min_cycles or len(troughs) < self.min_cycles:
            return None, None

        usable_pairs = min(len(peaks), len(troughs))
        recent_peaks = peaks[-usable_pairs:]
        recent_troughs = troughs[-usable_pairs:]

        amplitudes = []
        for (_, peak_val), (_, trough_val) in zip(recent_peaks, recent_troughs):
            amplitudes.append(abs(peak_val - trough_val) / 2.0)

        if not amplitudes:
            return None, None

        amplitude = sum(amplitudes) / len(amplitudes)

        # Reject noise-level oscillation
        if amplitude < self.min_amplitude:
            return None, None

        # Estimate period from peak-to-peak intervals
        if len(recent_peaks) < 2:
            return None, None

        peak_periods = []
        for i in range(1, len(recent_peaks)):
            peak_periods.append(recent_peaks[i][0] - recent_peaks[i - 1][0])

        if not peak_periods:
            return None, None

        period = sum(peak_periods) / len(peak_periods)

        if period <= 0:
            return None, None

        return amplitude, period

    def compute_pid(self, amplitude, period):
        if amplitude is None or period is None:
            return None

        if amplitude <= 0 or period <= 0:
            return None

        Ku = (4 * self.relay_amplitude) / (math.pi * amplitude)
        Pu = period

        # Ziegler-Nichols closed-loop PID
        Kp = 0.6 * Ku
        Ki = 1.2 * Ku / Pu
        Kd = 0.075 * Ku * Pu

        return Kp, Ki, Kd