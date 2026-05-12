# Manual input after heuristic tuning

HEURISTIC_KP = 2.0
HEURISTIC_KI = 0.5
HEURISTIC_KD = 0.1


def get_heuristic_pid():
    return (
        HEURISTIC_KP,
        HEURISTIC_KI,
        HEURISTIC_KD
    )
