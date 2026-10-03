import os
import time
import cloud_storage

# Test video path
test_vid_path = "test.mp4"

if os.path.exists(test_vid_path):
    print(f"Testing Cloud Video Storage Upload for: {test_vid_path}...")
    cloud_storage.upload_evidence(test_vid_path, resource_type="video")
    print("Upload command dispatched asynchronously! Check server logs for URL confirmation.")
else:
    print(f"Test video not found at {test_vid_path}")
