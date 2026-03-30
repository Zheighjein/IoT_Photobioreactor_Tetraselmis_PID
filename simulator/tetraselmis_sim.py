import random

class TetraselmisSim:
    def __init__(self, initial_ph=7.5):
        self.ph = initial_ph

    def step(self, co2_input):
        """
        co2_input: 1 = inject CO2 (lowers pH)
                   0 = no CO2 (pH rises naturally)
        """

        # Photosynthesis raises pH
        self.ph += 0.02

        # CO2 lowers pH
        if co2_input == 1:
            self.ph -= 0.05

        # Add noise
        self.ph += random.uniform(-0.01, 0.01)

        return self.ph