import os
import csv
import random

# Ensure the dataset directory exists
os.makedirs("dataset", exist_ok=True)
CSV_FILE = "dataset/stampede_features.csv"

def save_features(people_count, density_score, movement_score, behavior_score, congestion_score, violence_score, weapon_score, risk_label=""):
    """
    Appends a single row of features to the dataset CSV file.
    """
    file_exists = os.path.isfile(CSV_FILE)
    
    with open(CSV_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "people_count", "density_score", "movement_score", 
                "behavior_score", "congestion_score", "violence_score", 
                "weapon_score", "risk_label"
            ])
        writer.writerow([
            people_count, density_score, movement_score, 
            behavior_score, congestion_score, violence_score, 
            weapon_score, risk_label
        ])

def generate_synthetic_data(num_samples=1000):
    """
    Generates synthetic data based on the existing heuristic rules 
    so the ML model can be trained initially.
    """
    print(f"Generating {num_samples} synthetic samples in {CSV_FILE}...")
    for _ in range(num_samples):
        people_count = random.randint(0, 500)
        density_score = random.uniform(0, 100)
        movement_score = random.uniform(0, 100)
        behavior_score = random.uniform(0, 100)
        congestion_score = random.uniform(0, 100)
        violence_score = random.uniform(0, 100) if random.random() > 0.8 else 0.0
        weapon_score = 100.0 if random.random() > 0.95 else 0.0
        
        # Heuristic calculation for label
        threat_s = min(violence_score * 0.5 + weapon_score * 0.5, 100.0)
        raw = (
            density_score * 0.35 +
            movement_score * 0.25 +
            behavior_score * 0.20 +
            congestion_score * 0.10 +
            threat_s * 0.10
        )
        
        if raw < 30:
            label = "SAFE"
        elif raw < 50:
            label = "CAUTION"
        elif raw < 70:
            label = "WARNING"
        elif raw < 85:
            label = "HIGH_RISK"
        else:
            label = "CRITICAL"
            
        save_features(
            people_count, density_score, movement_score, 
            behavior_score, congestion_score, violence_score, 
            weapon_score, label
        )

if __name__ == "__main__":
    # If run standalone, generate some initial synthetic data for training
    if not os.path.exists(CSV_FILE):
        generate_synthetic_data(1000)
    else:
        print(f"{CSV_FILE} already exists. Appending 200 more samples.")
        generate_synthetic_data(200)
