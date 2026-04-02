import random

class TetraselmisSim:
    def __init__(self, initial_ph=7.5, initial_temp=25):
        self.ph = initial_ph
        self.temp = initial_temp

    def step(self, co2):
        self.ph += 0.02
        if co2 == 1:
            self.ph -= 0.05
        self.ph += random.uniform(-0.01, 0.01)

        self.temp += random.uniform(-0.1, 0.1)

        return self.ph, self.temp