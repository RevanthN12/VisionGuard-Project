"""
train.py — Synthetic Threat Dataset Generator & YOLO Fine-Tuning Pipeline
Generates synthetic threat images (guns, knives, suspicious packages), creates YOLO YAML configuration,
and fine-tunes custom YOLO models for VisionGuard threat monitoring.
"""

import builtins
_orig_delattr = builtins.delattr
def _safe_delattr(obj, name):
    try:
        _orig_delattr(obj, name)
    except AttributeError:
        pass
builtins.delattr = _safe_delattr

import os
import yaml
import numpy as np
import cv2
from ultralytics import YOLO

# Define dataset directory structure
DATASET_DIR = "synthetic_threat_dataset"
IMAGES_TRAIN = os.path.join(DATASET_DIR, "images", "train")
IMAGES_VAL = os.path.join(DATASET_DIR, "images", "val")
LABELS_TRAIN = os.path.join(DATASET_DIR, "labels", "train")
LABELS_VAL = os.path.join(DATASET_DIR, "labels", "val")

for path in [IMAGES_TRAIN, IMAGES_VAL, LABELS_TRAIN, LABELS_VAL]:
    os.makedirs(path, exist_ok=True)

THREAT_CLASSES = ["gun", "knife", "hazardous_package"]


def generate_synthetic_threat_image(img_name, threat_type, split="train"):
    """
    Generates a synthetic image with randomized textures and inserts a shape
    representing a gun (L-shape), knife (blade+handle), or hazardous package.
    Writes corresponding normalized YOLO bounding box label file.
    """
    h, w = 320, 320
    bg_color = np.random.randint(40, 180, size=3, dtype=int)
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = bg_color

    # Add random background noise/shapes to simulate real textures
    for _ in range(12):
        cx = np.random.randint(0, w)
        cy = np.random.randint(0, h)
        cr = np.random.randint(5, 35)
        color = np.random.randint(0, 255, size=3).tolist()
        cv2.circle(img, (cx, cy), cr, color, -1)

    target_cx = np.random.randint(80, 240)
    target_cy = np.random.randint(80, 240)

    if threat_type == "gun":
        label_class = 0
        gun_color = (40, 40, 40)
        cv2.rectangle(img, (target_cx - 10, target_cy), (target_cx + 10, target_cy + 30), gun_color, -1)
        cv2.rectangle(img, (target_cx - 10, target_cy - 10), (target_cx + 40, target_cy + 5), gun_color, -1)
        x1, y1 = target_cx - 15, target_cy - 15
        x2, y2 = target_cx + 45, target_cy + 35

    elif threat_type == "knife":
        label_class = 1
        blade_color = (210, 210, 210)
        handle_color = (40, 70, 110)
        cv2.line(img, (target_cx - 20, target_cy - 20), (target_cx + 20, target_cy + 20), blade_color, 4)
        cv2.line(img, (target_cx - 35, target_cy - 35), (target_cx - 20, target_cy - 20), handle_color, 6)
        x1, y1 = target_cx - 40, target_cy - 40
        x2, y2 = target_cx + 25, target_cy + 25

    else:  # hazardous_package
        label_class = 2
        box_color = (20, 100, 200)
        cv2.rectangle(img, (target_cx - 25, target_cy - 25), (target_cx + 25, target_cy + 25), box_color, -1)
        cv2.putText(img, "!", (target_cx - 8, target_cy + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        x1, y1 = target_cx - 30, target_cy - 30
        x2, y2 = target_cx + 30, target_cy + 30

    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)

    box_w = x2 - x1
    box_h = y2 - y1
    norm_cx = (x1 + box_w / 2) / w
    norm_cy = (y1 + box_h / 2) / h
    norm_w = box_w / w
    norm_h = box_h / h

    dest_img_dir = IMAGES_TRAIN if split == "train" else IMAGES_VAL
    cv2.imwrite(os.path.join(dest_img_dir, img_name), img)

    dest_lbl_dir = LABELS_TRAIN if split == "train" else LABELS_VAL
    lbl_filename = os.path.splitext(img_name)[0] + ".txt"
    with open(os.path.join(dest_lbl_dir, lbl_filename), "w") as f:
        f.write(f"{label_class} {norm_cx:.6f} {norm_cy:.6f} {norm_w:.6f} {norm_h:.6f}\n")


def generate_dataset(num_train=60, num_val=15):
    """Generates synthetic dataset samples for fine-tuning YOLO."""
    print(f"Generating synthetic dataset: {num_train} train, {num_val} val...")
    types = ["gun", "knife", "hazardous_package"]

    for i in range(num_train):
        threat = types[i % len(types)]
        generate_synthetic_threat_image(f"synth_train_{i:04d}.jpg", threat, split="train")

    for i in range(num_val):
        threat = types[i % len(types)]
        generate_synthetic_threat_image(f"synth_val_{i:04d}.jpg", threat, split="val")

    yaml_data = {
        "path": os.path.abspath(DATASET_DIR),
        "train": "images/train",
        "val": "images/val",
        "nc": len(THREAT_CLASSES),
        "names": THREAT_CLASSES
    }

    yaml_path = os.path.join(DATASET_DIR, "dataset.yaml")
    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)

    print(f"Dataset generated at '{DATASET_DIR}'. YAML config saved to '{yaml_path}'.")
    return yaml_path


def train_model(epochs=3, batch=8):
    """Fine-tunes YOLOv8 model on the synthetic dataset."""
    yaml_path = generate_dataset()
    print("Initializing YOLOv8n fine-tuning...")
    model = YOLO("yolov8n.pt")
    
    results = model.train(
        data=yaml_path,
        epochs=epochs,
        imgsz=320,
        batch=batch,
        project="runs/detect",
        name="threat_model",
        exist_ok=True
    )

    best_model_path = os.path.join("runs", "detect", "threat_model", "weights", "best.pt")
    target_path = os.path.join("models", "weapon_best.pt")

    if os.path.exists(best_model_path):
        os.makedirs("models", exist_ok=True)
        import shutil
        shutil.copy(best_model_path, target_path)
        print(f"✅ Fine-tuning complete! Model saved to '{target_path}'.")

    return results


if __name__ == "__main__":
    train_model(epochs=1)
