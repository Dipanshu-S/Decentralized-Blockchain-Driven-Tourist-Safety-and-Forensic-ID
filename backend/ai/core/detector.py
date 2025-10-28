"""
YOLOv8 Person Detector
Detects persons in video frames using pre-trained YOLOv8x model
"""
import cv2
import torch
from ultralytics import YOLO
import numpy as np
from loguru import logger

class PersonDetector:
    def __init__(self, model_path='models/yolov8x.pt', conf_threshold=0.3):
        """
        Initialize YOLOv8 detector
        
        Args:
            model_path: Path to YOLOv8 weights
            conf_threshold: Minimum confidence score (0.0 to 1.0)
        """
        logger.info("Initializing YOLOv8 Person Detector...")
        
        self.model = YOLO(model_path)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.conf_threshold = conf_threshold
        
        # COCO dataset class IDs
        self.PERSON_CLASS_ID = 0  # 'person' is class 0 in COCO
        
        logger.success(f"Model loaded on device: {self.device}")
        logger.info(f"Confidence threshold: {self.conf_threshold}")
    
    def detect(self, frame):
        """
        Detect persons in a single frame
        
        Args:
            frame: OpenCV image (numpy array)
        
        Returns:
            List of detections: [
                {
                    'bbox': [x1, y1, x2, y2],
                    'confidence': float,
                    'class': 'person'
                },
                ...
            ]
        """
        # Run inference
        results = self.model(frame, verbose=False, device=self.device)
        
        detections = []
        
        for result in results:
            boxes = result.boxes
            
            for box in boxes:
                # Get class ID
                cls_id = int(box.cls[0])
                
                # Only process 'person' class
                if cls_id == self.PERSON_CLASS_ID:
                    conf = float(box.conf[0])
                    
                    if conf >= self.conf_threshold:
                        # Get bounding box (xyxy format)
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        
                        detections.append({
                            'bbox': [int(x1), int(y1), int(x2), int(y2)],
                            'confidence': round(float(conf), 3),
                            'class': 'person'
                        })
        
        return detections
    
    def draw_detections(self, frame, detections, color=(0, 255, 0), thickness=2):
        """
        Draw bounding boxes on frame
        
        Args:
            frame: OpenCV image
            detections: List of detection dicts
            color: BGR color tuple
            thickness: Line thickness
        
        Returns:
            Annotated frame
        """
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            conf = det['confidence']
            
            # Draw rectangle
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            
            # Draw label background
            label = f"Person {conf:.2f}"
            (text_width, text_height), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, thickness
            )
            cv2.rectangle(
                frame, 
                (x1, y1 - text_height - 10), 
                (x1 + text_width, y1), 
                color, 
                -1
            )
            
            # Draw label text
            cv2.putText(
                frame, label, (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), thickness
            )
        
        return frame
