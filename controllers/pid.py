import time

class PID:
    def __init__(self, Kp, Ki, Kd, setpoint=7.5, output_limits=(-1, 1)):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd

        self.setpoint = setpoint

        self.prev_error = 0
        self.integral = 0
        self.last_time = time.time()

        self.min_output, self.max_output = (-1, 1)

    def compute(self, current_value):
        current_time = time.time()
        dt = current_time - self.last_time

        if dt <= 0:
            return 0

        error = self.setpoint - current_value

        # Proportional
        P = self.Kp * error

        # Integral (with anti-windup)
        self.integral += error * dt
        I = self.Ki * self.integral

        # Derivative
        derivative = (error - self.prev_error) / dt
        D = self.Kd * derivative

        output = P + I + D

        # Clamp output (0 = OFF, 1 = ON)
        output = max(self.min_output, min(self.max_output, output))

        # Save state
        self.prev_error = error
        self.last_time = current_time

        return output