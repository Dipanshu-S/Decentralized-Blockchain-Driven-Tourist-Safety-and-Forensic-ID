"""
Video Reader - Supports Webcam, MP4, ESP32-CAM
"""
import cv2
from loguru import logger

class VideoReader:
    def __init__(self, source=0):
        """
        Initialize video reader
        
        Args:
            source: int (webcam), str (video file path), or URL (ESP32-CAM)
        """
        self.source = source
        self.cap = None
        self.fps = 0
        self.width = 0
        self.height = 0
        
        self._open()
    
    def _open(self):
        """Open video source"""
        logger.info(f"Opening video source: {self.source}")
        
        self.cap = cv2.VideoCapture(self.source)
        
        if not self.cap.isOpened():
            raise ValueError(f"Cannot open video source: {self.source}")
        
        # Get video properties
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        logger.success(f"Video opened: {self.width}x{self.height} @ {self.fps} FPS")
    
    def read(self):
        """
        Read next frame
        
        Returns:
            (success: bool, frame: numpy array)
        """
        return self.cap.read()
    
    def release(self):
        """Release video capture"""
        if self.cap:
            self.cap.release()
            logger.info("Video source released")
    
    def is_opened(self):
        """Check if video is opened"""
        return self.cap and self.cap.isOpened()
    
    def get_info(self):
        """Get video information"""
        return {
            'source': self.source,
            'fps': self.fps,
            'width': self.width,
            'height': self.height
        }
