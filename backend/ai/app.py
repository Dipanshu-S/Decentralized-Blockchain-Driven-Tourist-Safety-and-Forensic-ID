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
import json
import base64
from datetime import datetime

# Local imports
sys.path.append('../')
from core.tracker import ByteTrack
from core.detector import PersonDetector
from utils.video_reader import VideoReader
from database.utils import generate_did, generate_feature_id, compute_id_hash
from database.db_manager import DatabaseManager
from database.mongo_manager import MongoManager

# ----------------------------------------------------
# LOGGING CONFIG
# ----------------------------------------------------
logger.remove()
logger.add(sys.stdout, colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")
logger.add("logs/app.log", rotation="10 MB")

# ----------------------------------------------------
# FLASK APP
# ----------------------------------------------------
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ----------------------------------------------------
# GLOBALS
# ----------------------------------------------------
detector = None

video_reader_1 = None
video_reader_2 = None

is_running_1 = False
is_running_2 = False

tracker_1 = None
tracker_2 = None

current_stats = {
    'camera1': {'fps': 0, 'persons': 0, 'detections': []},
    'camera2': {'fps': 0, 'persons': 0, 'detections': []},
    'total_persons': 0
}

# ----------------------------------------------------
# DATABASE INITIALIZATION  ✅ moved ABOVE server start
# ----------------------------------------------------
try:
    db_manager = DatabaseManager()
    mongo_manager = MongoManager()
    logger.success("Database managers initialized")
except Exception as e:
    logger.error(f"Database initialization failed: {e}")
    db_manager = None
    mongo_manager = None

# ----------------------------------------------------
# CAMERA STREAM FUNCTIONS
# ----------------------------------------------------
def generate_frames_camera1():
    global detector, video_reader_1, is_running_1, tracker_1, current_stats

    if not video_reader_1:
        logger.error("Camera 1 not initialized")
        return

    if tracker_1 is None:
        tracker_1 = ByteTrack(max_age=30, min_hits=3, iou_threshold=0.3)

    frame_count = 0
    start_time = time.time()
    process_every = 2
    last_tracked = []

    while is_running_1:
        ret, frame = video_reader_1.read()
        if not ret:
            break

        frame_count += 1
        resized = cv2.resize(frame, (640, 480))

        if frame_count % process_every == 0:
            detections = detector.detect(resized)
            tracked = tracker_1.update(detections)
            last_tracked = tracked
        else:
            tracked = last_tracked

        resized = detector.draw_tracked_detections(resized, tracked)
        fps = frame_count / (time.time() - start_time)

        current_stats["camera1"] = {
            "fps": round(fps, 1),
            "persons": len(tracked),
            "detections": tracked
        }

        if frame_count % 5 == 0:
            update_combined_stats()

        ret, buffer = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" +
               buffer.tobytes() + b"\r\n")


def generate_frames_camera2():
    global detector, video_reader_2, is_running_2, tracker_2, current_stats

    if not video_reader_2:
        logger.error("Camera 2 not initialized")
        return

    if tracker_2 is None:
        tracker_2 = ByteTrack(max_age=30, min_hits=3, iou_threshold=0.3)

    frame_count = 0
    start_time = time.time()
    process_every = 2
    last_tracked = []

    while is_running_2:
        ret, frame = video_reader_2.read()
        if not ret:
            break

        frame_count += 1
        resized = cv2.resize(frame, (640, 480))

        if frame_count % process_every == 0:
            detections = detector.detect(resized)
            tracked = tracker_2.update(detections)
            last_tracked = tracked
        else:
            tracked = last_tracked

        resized = detector.draw_tracked_detections(resized, tracked)
        fps = frame_count / (time.time() - start_time)

        current_stats["camera2"] = {
            "fps": round(fps, 1),
            "persons": len(tracked),
            "detections": tracked
        }

        if frame_count % 5 == 0:
            update_combined_stats()

        ret, buffer = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" +
               buffer.tobytes() + b"\r\n")


def update_combined_stats():
    total = current_stats["camera1"]["persons"] + current_stats["camera2"]["persons"]
    current_stats["total_persons"] = total

    all_dets = []

    for det in current_stats["camera1"]["detections"]:
        all_dets.append({**det, "camera": "Camera 1"})

    for det in current_stats["camera2"]["detections"]:
        all_dets.append({**det, "camera": "Camera 2"})

    socketio.emit("stats", {
        "camera1": current_stats["camera1"],
        "camera2": current_stats["camera2"],
        "total_persons": total,
        "all_detections": all_dets
    })

# ----------------------------------------------------
# ROUTES (ALL moved ABOVE __main__)
# ----------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed_1")
def video_feed_1():
    return Response(generate_frames_camera1(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/video_feed_2")
def video_feed_2():
    return Response(generate_frames_camera2(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/start_camera", methods=["POST"])
def start_camera():
    global video_reader_1, video_reader_2
    global is_running_1, is_running_2
    global tracker_1, tracker_2

    data = request.get_json()
    cam = data.get("camera", 1)
    stype = data.get("source_type", "webcam")

    if stype == "webcam":
        source = cam - 1
    elif stype == "video":
        source = data.get("video_path")
    else:
        source = data.get("esp32_url")

    if cam == 1:
        video_reader_1 = VideoReader(source)
        tracker_1 = ByteTrack()
        is_running_1 = True
        info = video_reader_1.get_info()
    else:
        video_reader_2 = VideoReader(source)
        tracker_2 = ByteTrack()
        is_running_2 = True
        info = video_reader_2.get_info()

    return jsonify({"status": "started", "camera": cam, "video_info": info})


@app.route("/api/stop_camera", methods=["POST"])
def stop_camera():
    global video_reader_1, video_reader_2
    global is_running_1, is_running_2
    global tracker_1, tracker_2

    cam = request.get_json().get("camera", 1)

    if cam == 1:
        is_running_1 = False
        if video_reader_1: video_reader_1.release()
        tracker_1 = None
    else:
        is_running_2 = False
        if video_reader_2: video_reader_2.release()
        tracker_2 = None

    return jsonify({"status": "stopped", "camera": cam})


@app.route("/register")
def register_page():
    return render_template("register.html")


@app.route("/api/register_tourist", methods=["POST"])
def register_tourist():
    global db_manager, mongo_manager

    if not db_manager or not mongo_manager:
        return jsonify({"error": "DB not initialized"}), 500

    data = request.get_json()

    did = generate_did("tourist")
    id_hash, salt = compute_id_hash(data["id_number"])

    tourist_data = {
        "did": did,
        "name": data["name"],
        "id_type": data["id_type"],
        "id_number": data["id_number"],
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "entry_point": data["entry_point"],
        "itinerary": data.get("itinerary", [])
    }

    tourist_id, stored_hash = db_manager.register_tourist(tourist_data)

    feature_id = None
    if "face_images" in data and len(data["face_images"]) > 0:
        feature_id = generate_feature_id()
        mongo_manager.store_tourist_features({
            "feature_id": feature_id,
            "did": did,
            "reid_embedding": [0.0] * 512,
            "camera_id": "registration_desk",
            "capture_angles": [{"angle": "front", "quality_score": 0.95}],
            "feature_quality": 0.95
        })

    qr_data = {
        "did": did,
        "name": data["name"],
        "entry_point": data["entry_point"],
        "timestamp": datetime.now().isoformat()
    }

    return jsonify({
        "success": True,
        "tourist_id": tourist_id,
        "did": did,
        "id_hash": stored_hash,
        "feature_id": feature_id,
        "qr_data": qr_data
    })


@app.route("/api/search_tourist", methods=["GET"])
def search_tourist():
    if not db_manager:
        return jsonify({"error": "DB not initialized"}), 500

    did = request.args.get("did")
    if not did:
        return jsonify({"error": "DID required"}), 400

    tourist = db_manager.get_tourist_by_did(did)
    if not tourist:
        return jsonify({"error": "Not found"}), 404

    # remove encrypted fields
    tourist.pop("name_encrypted", None)
    tourist.pop("id_number_encrypted", None)
    tourist.pop("phone_encrypted", None)
    tourist.pop("email_encrypted", None)

    return jsonify({"success": True, "tourist": tourist})


@app.route("/api/get_tourist_trajectory", methods=["GET"])
def get_tourist_trajectory():
    if not mongo_manager:
        return jsonify({"error": "DB not initialized"}), 500

    did = request.args.get("did")
    traj = mongo_manager.get_tourist_trajectory(did)
    return jsonify({"success": True, "did": did, "trajectory": traj})

# ----------------------------------------------------
# WEBSOCKET EVENTS
# ----------------------------------------------------
@socketio.on("connect")
def handle_connect():
    logger.info("Client connected")
    emit("connected", {"data": "Connected"})


@socketio.on("disconnect")
def handle_disconnect():
    logger.info("Client disconnected")

# ----------------------------------------------------
# SERVER START (BOTTOM ONLY)
# ----------------------------------------------------
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 Smart Tourist Safety System - Dual Camera")
    logger.info("=" * 60)

    detector = PersonDetector("models/yolov8n.pt", conf_threshold=0.4, img_size=320)

    socketio.run(app, host="0.0.0.0", port=5000,
                 debug=False, allow_unsafe_werkzeug=True)
