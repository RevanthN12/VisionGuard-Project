import os
import time
import cv2
import cloud_storage

# Create a temporary test image
test_img_path = "outputs/evidence/images/cloud_test_image.jpg"
os.makedirs("outputs/evidence/images", exist_ok=True)

# Generate a blank red image
img = cv2.resize(cv2.imread("website/assets/hero.jpg", 1), (640, 480))
cv2.putText(img, "CLOUD STORAGE TEST", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
cv2.imwrite(test_img_path, img)

print(f"Created test image at: {test_img_path}")
print("Attempting to upload to Cloudinary...")

# Upload
cloud_storage.upload_evidence(test_img_path, resource_type="image")

print("Upload command sent! Check your Cloudinary Dashboard in a few seconds.")
