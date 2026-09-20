import numpy as np

class NoiseMonitor:
    def __init__(self):
        self.base_db = 48.0
        
    def get_decibels(self, inject_scream=False):
        """
        Returns simulated decibel level of ambient environment.
        Screams or explosions spike the dB rating above 95 dB.
        """
        if inject_scream:
            # Gunshot or scream peaks
            return round(float(np.random.uniform(98.0, 115.0)), 1)
            
        # Normal ambient chatter
        drift = np.random.uniform(-3.0, 3.0)
        current_db = min(max(35.0, self.base_db + drift), 65.0)
        return round(float(current_db), 1)
