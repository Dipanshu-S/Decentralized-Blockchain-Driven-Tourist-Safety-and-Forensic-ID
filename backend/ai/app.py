"""
Flask Web Server for Smart Tourist Safety System
Real-time person detection with DUAL CAMERA support
"""
from flask import Flask, render_template, Response, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import cv2
import time
from loguru import logger
import sys
import threading

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
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global variables for DUAL cameras
detector = None

# Camera 1
video_reader_1 = None
is_running_1 = False

# Camera 2
video_reader_2 = None
is_running_2 = False

# Combined stats
current_stats = {
    'camera1': {'fps': 0, 'persons': 0, 'detections': []},
    'camera2': {'fps': 0, 'persons': 0, 'detections': []},
    'total_persons': 0
}

def generate_frames_camera1():
    """Generate frames for Camera 1"""
    global detector, video_reader_1, is_running_1, current_stats
    
    if not video_reader_1 or not video_reader_1.is_opened():
        logger.error("Camera 1 video reader not initialized")
        return
    
    frame_count = 0
    start_time = time.time()
    process_every_n_frames = 2
    last_detections = []
    
    logger.info("Camera 1: Starting frame generation...")
    
    while is_running_1:
        ret, frame = video_reader_1.read()
        
        if not ret:
            if isinstance(video_reader_1.source, str) and video_reader_1.source.endswith('.mp4'):
                video_reader_1.release()
                video_reader_1 = VideoReader(video_reader_1.source)
                continue
            else:
                break
        
        frame_count += 1
        display_frame = cv2.resize(frame, (640, 480))
        
        # Run detection
        if frame_count % process_every_n_frames == 0:
            detections = detector.detect(display_frame)
            last_detections = detections
        else:
            detections = last_detections
        
        # Draw boxes
        display_frame = detector.draw_detections(display_frame, detections)
        
        # Calculate FPS
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0
        
        # Draw stats
        stats_text = f'FPS: {fps:.1f} | Persons: {len(detections)}'
        cv2.putText(display_frame, stats_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(display_frame, stats_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 1, cv2.LINE_AA)
        
        # Update stats
        current_stats['camera1'] = {
            'fps': round(fps, 1),
            'persons': len(detections),
            'detections': detections
        }
        
        # Emit stats
        if frame_count % 5 == 0:
            update_combined_stats()
        
        # Encode
        ret, buffer = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    
    logger.info("Camera 1: Frame generation stopped")

def generate_frames_camera2():
    """Generate frames for Camera 2"""
    global detector, video_reader_2, is_running_2, current_stats
    
    if not video_reader_2 or not video_reader_2.is_opened():
        logger.error("Camera 2 video reader not initialized")
        return
    
    frame_count = 0
    start_time = time.time()
    process_every_n_frames = 2
    last_detections = []
    
    logger.info("Camera 2: Starting frame generation...")
    
    while is_running_2:
        ret, frame = video_reader_2.read()
        
        if not ret:
            if isinstance(video_reader_2.source, str) and video_reader_2.source.endswith('.mp4'):
                video_reader_2.release()
                video_reader_2 = VideoReader(video_reader_2.source)
                continue
            else:
                break
        
        frame_count += 1
        display_frame = cv2.resize(frame, (640, 480))
        
        # Run detection
        if frame_count % process_every_n_frames == 0:
            detections = detector.detect(display_frame)
            last_detections = detections
        else:
            detections = last_detections
        
        # Draw boxes
        display_frame = detector.draw_detections(display_frame, detections)
        
        # Calculate FPS
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0
        
        # Draw stats
        stats_text = f'FPS: {fps:.1f} | Persons: {len(detections)}'
        cv2.putText(display_frame, stats_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(display_frame, stats_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 1, cv2.LINE_AA)
        
        # Update stats
        current_stats['camera2'] = {
            'fps': round(fps, 1),
            'persons': len(detections),
            'detections': detections
        }
        
        # Emit stats
        if frame_count % 5 == 0:
            update_combined_stats()
        
        # Encode
        ret, buffer = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    
    logger.info("Camera 2: Frame generation stopped")

def update_combined_stats():
    """Combine stats from both cameras and emit via WebSocket"""
    total_persons = current_stats['camera1']['persons'] + current_stats['camera2']['persons']
    current_stats['total_persons'] = total_persons
    
    # Combine detections from both cameras
    all_detections = []
    
    for det in current_stats['camera1']['detections']:
        all_detections.append({
            **det,
            'camera': 'Camera 1'
        })
    
    for det in current_stats['camera2']['detections']:
        all_detections.append({
            **det,
            'camera': 'Camera 2'
        })
    
    socketio.emit('stats', {
        'camera1': current_stats['camera1'],
        'camera2': current_stats['camera2'],
        'total_persons': total_persons,
        'all_detections': all_detections
    })

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed_1')
def video_feed_1():
    """Video streaming for Camera 1"""
    return Response(generate_frames_camera1(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_2')
def video_feed_2():
    """Video streaming for Camera 2"""
    return Response(generate_frames_camera2(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/start_camera', methods=['POST'])
def start_camera():
    """Start specific camera"""
    global detector, video_reader_1, video_reader_2, is_running_1, is_running_2
    
    data = request.get_json()
    camera_num = data.get('camera', 1)
    source_type = data.get('source_type', 'webcam')
    
    logger.info(f"Starting Camera {camera_num} with source: {source_type}")
    
    try:
        # Determine video source
        if source_type == 'webcam':
            source = camera_num - 1  # Camera 1 = index 0, Camera 2 = index 1
        elif source_type == 'video':
            source = data.get('video_path', f'videos/sample.mp4')
        elif source_type == 'esp32cam':
            source = data.get('esp32_url', 'http://192.168.1.100:81/stream')
            logger.info(f"Using IP camera URL: {source}")  # Debug log
        else:
            return jsonify({'error': 'Invalid source type'}), 400
        
        # Initialize appropriate camera
        if camera_num == 1:
            video_reader_1 = VideoReader(source)
            is_running_1 = True
            video_info = video_reader_1.get_info()
        else:
            video_reader_2 = VideoReader(source)
            is_running_2 = True
            video_info = video_reader_2.get_info()
        
        logger.success(f"Camera {camera_num} started: {video_info}")
        
        return jsonify({
            'status': 'started',
            'camera': camera_num,
            'source': source_type,
            'video_info': video_info
        })
    
    except Exception as e:
        logger.error(f"Failed to start Camera {camera_num}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop_camera', methods=['POST'])
def stop_camera():
    """Stop specific camera"""
    global is_running_1, is_running_2, video_reader_1, video_reader_2
    
    data = request.get_json()
    camera_num = data.get('camera', 1)
    
    logger.info(f"Stopping Camera {camera_num}...")
    
    if camera_num == 1:
        is_running_1 = False
        if video_reader_1:
            video_reader_1.release()
            video_reader_1 = None
    else:
        is_running_2 = False
        if video_reader_2:
            video_reader_2.release()
            video_reader_2 = None
    
    return jsonify({'status': 'stopped', 'camera': camera_num})

@app.route('/api/status')
def get_status():
    return jsonify({
        'camera1_running': is_running_1,
        'camera2_running': is_running_2,
        'device': detector.device if detector else 'none',
        'model_loaded': detector is not None,
        'stats': current_stats
    })

@socketio.on('connect')
def handle_connect():
    logger.info("Client connected to WebSocket")
    emit('connected', {'data': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected from WebSocket")

if __name__ == '__main__':
    logger.info("="*60)
    logger.info("🚀 Smart Tourist Safety System - Dual Camera MCPT")
    logger.info("="*60)
    
    detector = PersonDetector(
        model_path='models/yolov8n.pt',
        conf_threshold=0.4,
        img_size=320
    )
    
    logger.info(f"📍 Dashboard: http://localhost:5000")
    logger.info(f"🤖 AI Device: {detector.device}")
    logger.info(f"📹 Camera 1: http://localhost:5000/video_feed_1")
    logger.info(f"📹 Camera 2: http://localhost:5000/video_feed_2")
    logger.info("="*60)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
