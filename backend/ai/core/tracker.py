"""
ByteTrack Tracker
Assigns persistent IDs to detected persons across frames
"""
import numpy as np
from scipy.optimize import linear_sum_assignment
from filterpy.kalman import KalmanFilter
from loguru import logger


class KalmanBoxTracker:
    """
    Kalman Filter for bounding box tracking
    State: [x, y, w, h, vx, vy, vw, vh]
    """
    count = 0
    
    def __init__(self, bbox):
        """bbox: [x1, y1, x2, y2]"""
        self.kf = KalmanFilter(dim_x=8, dim_z=4)
        
        # State transition matrix
        self.kf.F = np.array([
            [1, 0, 0, 0, 1, 0, 0, 0],
            [0, 1, 0, 0, 0, 1, 0, 0],
            [0, 0, 1, 0, 0, 0, 1, 0],
            [0, 0, 0, 1, 0, 0, 0, 1],
            [0, 0, 0, 0, 1, 0, 0, 0],
            [0, 0, 0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 0, 1]
        ])
        
        # Measurement matrix
        self.kf.H = np.array([
            [1, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0, 0]
        ])
        
        # Covariance matrices
        self.kf.R *= 10.0
        self.kf.P[4:, 4:] *= 1000.0
        self.kf.Q[4:, 4:] *= 0.01
        
        # Initialize state
        self.kf.x[:4] = self._convert_bbox_to_z(bbox)
        
        self.time_since_update = 0
        self.id = KalmanBoxTracker.count
        KalmanBoxTracker.count += 1
        self.history = []
        self.hits = 0
        self.hit_streak = 0
        self.age = 0
        
    def _convert_bbox_to_z(self, bbox):
        """Convert [x1, y1, x2, y2] to [cx, cy, w, h]"""
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        cx = bbox[0] + w / 2.0
        cy = bbox[1] + h / 2.0
        return np.array([cx, cy, w, h]).reshape((4, 1))
    
    def _convert_z_to_bbox(self, z):
        """Convert [cx, cy, w, h] to [x1, y1, x2, y2]"""
        w = z[2]
        h = z[3]
        x1 = z[0] - w / 2.0
        y1 = z[1] - h / 2.0
        x2 = z[0] + w / 2.0
        y2 = z[1] + h / 2.0
        return np.array([x1, y1, x2, y2])
    
    def update(self, bbox):
        """Update tracker with new detection"""
        self.time_since_update = 0
        self.history = []
        self.hits += 1
        self.hit_streak += 1
        self.kf.update(self._convert_bbox_to_z(bbox))
    
    def predict(self):
        """Predict next state"""
        if self.kf.x[2] + self.kf.x[3] <= 0:
            self.kf.x[2] = 1
        
        self.kf.predict()
        self.age += 1
        
        if self.time_since_update > 0:
            self.hit_streak = 0
        
        self.time_since_update += 1
        self.history.append(self._convert_z_to_bbox(self.kf.x[:4]))
        
        return self.history[-1]
    
    def get_state(self):
        """Get current bounding box"""
        return self._convert_z_to_bbox(self.kf.x[:4])


def iou(bbox1, bbox2):
    """Calculate Intersection over Union"""
    x1 = max(bbox1[0], bbox2[0])
    y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[2], bbox2[2])
    y2 = min(bbox1[3], bbox2[3])
    
    inter_area = max(0, x2 - x1) * max(0, y2 - y1)
    
    bbox1_area = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
    bbox2_area = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
    
    union_area = bbox1_area + bbox2_area - inter_area
    
    return inter_area / union_area if union_area > 0 else 0


class ByteTrack:
    """
    ByteTrack: Multi-Object Tracker
    Assigns and maintains persistent IDs
    """
    
    def __init__(self, max_age=30, min_hits=3, iou_threshold=0.3):
        """
        Args:
            max_age: Maximum frames to keep alive without detections
            min_hits: Minimum detections before confirmed
            iou_threshold: IoU threshold for matching
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        
        self.trackers = []
        self.frame_count = 0
        
        logger.info(f"ByteTrack initialized: max_age={max_age}, min_hits={min_hits}, iou={iou_threshold}")
    
    def update(self, detections):
        """
        Update tracker with new detections
        
        Returns:
            List of tracked objects with 'bbox', 'tracking_id', 'confidence'
        """
        self.frame_count += 1
        
        # Predict existing trackers
        predicted_bboxes = []
        to_delete = []
        
        for i, tracker in enumerate(self.trackers):
            bbox = tracker.predict()
            
            if np.any(np.isnan(bbox)):
                to_delete.append(i)
            else:
                predicted_bboxes.append(bbox)
        
        # Remove invalid trackers
        for i in reversed(to_delete):
            self.trackers.pop(i)
        
        # Match detections to trackers
        if len(detections) > 0:
            detection_bboxes = np.array([det['bbox'] for det in detections])
            
            if len(self.trackers) > 0:
                iou_matrix = np.zeros((len(detection_bboxes), len(self.trackers)))
                
                for d, det_bbox in enumerate(detection_bboxes):
                    for t, tracker in enumerate(self.trackers):
                        iou_matrix[d, t] = iou(det_bbox, tracker.get_state())
                
                # Hungarian algorithm
                matched_indices = linear_sum_assignment(-iou_matrix)
                matched_indices = np.array(list(zip(*matched_indices)))
                
                # Filter by IoU threshold
                matches = []
                for m in matched_indices:
                    if iou_matrix[m[0], m[1]] >= self.iou_threshold:
                        matches.append(m)
                
                # Update matched trackers
                matched_dets = []
                for m in matches:
                    self.trackers[m[1]].update(detection_bboxes[m[0]])
                    matched_dets.append(m[0])
                
                # Create new trackers for unmatched detections
                for i in range(len(detection_bboxes)):
                    if i not in matched_dets:
                        tracker = KalmanBoxTracker(detection_bboxes[i])
                        self.trackers.append(tracker)
            else:
                # No existing trackers, create new ones
                for det_bbox in detection_bboxes:
                    tracker = KalmanBoxTracker(det_bbox)
                    self.trackers.append(tracker)
        
        # Remove dead trackers
        self.trackers = [
            t for t in self.trackers 
            if t.time_since_update <= self.max_age
        ]
        
        # Return confirmed tracks
        tracked_objects = []
        for tracker in self.trackers:
            if tracker.hit_streak >= self.min_hits or self.frame_count <= self.min_hits:
                bbox = tracker.get_state()
                
                # Find corresponding detection for confidence
                conf = 0.5
                for det in detections:
                    if iou(bbox, det['bbox']) > 0.3:
                        conf = det['confidence']
                        break
                
                tracked_objects.append({
                    'bbox': [int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])],
                    'tracking_id': tracker.id + 1,
                    'confidence': conf,
                    'class': 'person'
                })
        
        return tracked_objects
    
    def reset(self):
        """Reset tracker"""
        self.trackers = []
        self.frame_count = 0
        KalmanBoxTracker.count = 0
        logger.info("ByteTrack reset")
