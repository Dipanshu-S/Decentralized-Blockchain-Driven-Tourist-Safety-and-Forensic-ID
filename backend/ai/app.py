"""
Flask Web Server for Smart Tourist Safety System
Real-time person detection with web UI
"""
from flask import Flask, render_template, Response, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import cv2
import time
from loguru import logger
import sys

# Import our modules
from core.detector import PersonDetector
from utils.video_reader import VideoReader

# Configure logger
logger.remove()
logger.add(sys.stdout, colorize=True, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")
logger.add("logs/app.log", rotation="10 MB")

# Initialize Flask app
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables
detector = None
video_reader = None
is_running = False
current_stats = {
    'fps': 0,
    'persons': 0,
    'detections': []
}

def generate_frames():
    """Generate video frames with detection overlay"""
    global detector, video_reader, is_running, current_stats
    
    if not video_reader or not video_reader.is_opened():
        logger.error("Video reader not initialized")
        return
    
    frame_count = 0
    start_time = time.time()
    
    logger.info("Starting frame generation...")
    
    while is_running:
        ret, frame = video_reader.read()
        
        if not ret:
            # If video file ends, loop it
            if isinstance(video_reader.source, str) and video_reader.source.endswith('.mp4'):
                video_reader.release()
                video_reader = VideoReader(video_reader.source)
                continue
            else:
                logger.warning("Failed to read frame")
                break
        
        # Detect persons
        detections = detector.detect(frame)
        
        # Draw bounding boxes
        frame = detector.draw_detections(frame, detections)
        
        # Calculate FPS
        frame_count += 1
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0
        
        # Draw stats on frame
        stats_text = f'FPS: {fps:.1f} | Persons: {len(detections)}'
        cv2.putText(frame, stats_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, stats_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 1, cv2.LINE_AA)
        
        # Update global stats
        current_stats = {
            'fps': round(fps, 1),
            'persons': len(detections),
            'detections': detections
        }
        
        # Emit stats via WebSocket (every 10 frames to reduce overhead)
        if frame_count % 10 == 0:
            socketio.emit('stats', current_stats)
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        frame_bytes = buffer.tobytes()
        
        # Yield frame for streaming
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    
    logger.info(f"Frame generation stopped. Total frames: {frame_count}")

@app.route('/')
def index():
    """Serve main dashboard"""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/start', methods=['POST'])
def start_detection():
    """Start detection"""
    global detector, video_reader, is_running
    
    data = request.get_json()
    source_type = data.get('source_type', 'webcam')
    
    logger.info(f"Starting detection with source: {source_type}")
    
    try:
        # Determine video source
        if source_type == 'webcam':
            source = 0
        elif source_type == 'video':
            source = data.get('video_path', 'videos/sample.mp4')
        elif source_type == 'esp32cam':
            source = data.get('esp32_url', 'http://192.168.1.100:81/stream')
        else:
            return jsonify({'error': 'Invalid source type'}), 400
        
        # Initialize video reader
        video_reader = VideoReader(source)
        is_running = True
        
        video_info = video_reader.get_info()
        
        logger.success(f"Detection started: {video_info}")
        
        return jsonify({
            'status': 'started',
            'source': source_type,
            'device': detector.device,
            'video_info': video_info
        })
    
    except Exception as e:
        logger.error(f"Failed to start detection: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop', methods=['POST'])
def stop_detection():
    """Stop detection"""
    global is_running, video_reader
    
    logger.info("Stopping detection...")
    is_running = False
    
    if video_reader:
        video_reader.release()
        video_reader = None
    
    return jsonify({'status': 'stopped'})

@app.route('/api/status')
def get_status():
    """Get current system status"""
    return jsonify({
        'is_running': is_running,
        'device': detector.device if detector else 'none',
        'model_loaded': detector is not None,
        'stats': current_stats
    })

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    logger.info("Client connected to WebSocket")
    emit('connected', {'data': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    logger.info("Client disconnected from WebSocket")

if __name__ == '__main__':
    logger.info("="*60)
    logger.info("🚀 Smart Tourist Safety System - MCPT Demo")
    logger.info("="*60)
    
    # Initialize detector
    detector = PersonDetector(model_path='models/yolov8x.pt', conf_threshold=0.5)
    
    logger.info(f"📍 Dashboard: http://localhost:5000")
    logger.info(f"🤖 AI Device: {detector.device}")
    logger.info(f"📹 Video API: http://localhost:5000/video_feed")
    logger.info("="*60)
    
    # Run Flask app
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
