import os
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import feature_collector

MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "stampede_risk_model.joblib")
CSV_FILE = "dataset/stampede_features.csv"

def train_model():
    """
    Trains a Random Forest model on the collected features and saves it to a file.
    """
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    # Generate synthetic data if the CSV doesn't exist
    if not os.path.exists(CSV_FILE):
        feature_collector.generate_synthetic_data(1000)

    print(f"Loading data from {CSV_FILE}...")
    df = pd.read_csv(CSV_FILE)
    
    if len(df) < 50:
        print("Not enough data to train. Generating synthetic data...")
        feature_collector.generate_synthetic_data(1000)
        df = pd.read_csv(CSV_FILE)

    X = df[["people_count", "density_score", "movement_score", 
            "behavior_score", "congestion_score", "violence_score", "weapon_score"]]
    y = df["risk_label"]

    print("Splitting dataset...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print("Training Random Forest Classifier...")
    # Initialize Random Forest with class_weight='balanced' to handle any class imbalance
    clf = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    clf.fit(X_train, y_train)

    print("Evaluating model...")
    y_pred = clf.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Accuracy: {accuracy:.4f}")
    print("Classification Report:")
    print(classification_report(y_test, y_pred))

    print(f"Saving model to {MODEL_PATH}...")
    joblib.dump(clf, MODEL_PATH)
    print("Training complete!")

if __name__ == "__main__":
    train_model()
