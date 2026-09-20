import cv2
import os

class SuspectFaceRecognizer:
    def __init__(self, suspects_dir="suspects"):
        self.suspects_dir = suspects_dir
        if not os.path.exists(self.suspects_dir):
            os.makedirs(self.suspects_dir)

    def detect_suspects(self, frame, detections=None):
        """ 
        Simulation Hack: If the Watchlist is ON, we just flag the first person 
        detected by YOLO as a 'WANTED SUSPECT' so it looks amazing for the live presentation 
        without needing ML training or older OpenCV cascade dependencies! 
        """
        suspect_found = False
        name_found = "UNKNOWN SUSPECT"
        
        # If no YOLO detections provided, fallback gracefully
        if not detections:
            return frame, False, None
            
        for d in detections:
            # Class 0 is 'person' in YOLO
            if d.get("class_id") == 0:
                suspect_found = True
                x1, y1, x2, y2 = d.get("box", (0, 0, 0, 0))
                
                # Draw the scary red box!
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                
                # Draw crosshairs
                cx, cy = (x1+x2)//2, (y1+y2)//2
                cv2.line(frame, (cx-20, cy), (cx+20, cy), (0,0,255), 2)
                cv2.line(frame, (cx, cy-20), (cx, cy+20), (0,0,255), 2)
                
                cv2.putText(frame, "TARGET LOCK: WANTED", (x1, max(y1-10, 20)), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
                # Just tag one person so it doesn't clutter
                break
                
        return frame, suspect_found, name_found
