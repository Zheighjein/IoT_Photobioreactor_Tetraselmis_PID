"""
Heuristic PID Parameters
Selected through offline simulation
and performance metric evaluation.
"""

Kp = 2.0
Ki = 0.5
Kd = 0.1


def get_pid_values():

    return {
        "kp": Kp,
        "ki": Ki,
        "kd": Kd
    }