import cloudinary
import cloudinary.uploader
import threading
import config
import os

# Initialize Cloudinary from the environment variable (if provided)
if config.CLOUD_STORAGE_ENABLED and config.CLOUDINARY_URL:
    cloudinary.config(url=config.CLOUDINARY_URL)

def _upload_async(filepath: str, resource_type: str):
    """Internal function to upload to cloudinary asynchronously."""
    if not config.CLOUD_STORAGE_ENABLED or not config.CLOUDINARY_URL:
        return

    print(f"[CloudStorage] Starting background upload for: {filepath}")
    try:
        if not os.path.exists(filepath):
            print(f"[CloudStorage] Error: File not found: {filepath}")
            return
            
        # Use upload_large for videos, regular upload for images
        if resource_type == "video":
            response = cloudinary.uploader.upload_large(filepath, resource_type="video", folder="visionguard_evidence")
        else:
            response = cloudinary.uploader.upload(filepath, folder="visionguard_evidence")
            
        url = response.get("secure_url")
        print(f"[CloudStorage] [SUCCESS] File uploaded to Cloudinary: {url}")
        
    except Exception as e:
        print(f"[CloudStorage] [ERROR] Upload failed: {e}")

def upload_evidence(filepath: str, resource_type: str = "auto"):
    """
    Triggers an asynchronous upload of the evidence file to Cloudinary.
    resource_type should be 'image' or 'video'.
    """
    if not config.CLOUD_STORAGE_ENABLED or not config.CLOUDINARY_URL:
        return
        
    # Run upload in a background thread so it doesn't block the video stream
    t = threading.Thread(target=_upload_async, args=(filepath, resource_type), daemon=True)
    t.start()
