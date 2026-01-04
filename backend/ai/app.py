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
# using thread async mode (eventlet/gevent optional)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ----------------------------------------------------
# GLOBALS
# ----------------------------------------------------
detector = None

video_reader_1 = None
video_reader_2 = None

is_running_1 = False
is_running_2 = False

# Keep trackers as globals but don't depend on them to always exist while generator runs.
tracker_1 = None
tracker_2 = None

current_stats = {
    'camera1': {'fps': 0, 'persons': 0, 'detections': []},
    'camera2': {'fps': 0, 'persons': 0, 'detections': []},
    'total_persons': 0
}

# ----------------------------------------------------
# DATABASE INITIALIZATION
# try to initialize DBs but continue even if Mongo is down (we'll handle None checks)
# ----------------------------------------------------
try:
    db_manager = DatabaseManager()
    try:
        mongo_manager = MongoManager()
    except Exception as e:
        # Don't crash server if Mongo is not running; log and set to None.
        logger.error(f"MongoManager init failed: {e}")
        mongo_manager = None
    logger.success("Database managers initialized (sqlite ok, mongo may be None)")
except Exception as e:
    logger.error(f"Database initialization failed: {e}")
    db_manager = None
    mongo_manager = None

# ----------------------------------------------------
# HELPERS
# ----------------------------------------------------
def safe_create_local_tracker(global_tracker, **kwargs):
    """
    Return a tracker instance to use in the generator loop.
    If a global tracker exists, use it. Otherwise create a temporary local one.
    This prevents race conditions where the global is set to None while generator is running.
    """
    if global_tracker is not None:
        return global_tracker, False  # (tracker_to_use, is_local_flag)
    else:
        return ByteTrack(**kwargs), True

# ----------------------------------------------------
# CAMERA STREAM FUNCTIONS (robust & defensive)
# ----------------------------------------------------
def generate_frames_camera1():
    global detector, video_reader_1, is_running_1, tracker_1, current_stats

    if not video_reader_1:
        logger.error("Camera 1 not initialized")
        # Return a small generator that yields nothing
        if False:
            yield b''
        return

    frame_count = 0
    start_time = time.time()
    process_every = 2
    last_tracked = []

    # Use a local tracker if global is None to avoid AttributeError when global cleared.
    # But prefer global so state (IDs) is maintained.
    while is_running_1:
        try:
            ret, frame = video_reader_1.read()
            if not ret or frame is None:
                logger.info("Camera 1 read returned no frame, stopping generator")
                # gracefully end stream
                is_running_1 = False
                break

            frame_count += 1
            resized = cv2.resize(frame, (640, 480))

            # get tracker safely
            t, is_local = safe_create_local_tracker(tracker_1, max_age=30, min_hits=3, iou_threshold=0.3)

            if frame_count % process_every == 0:
                # ensure detector exists
                if detector is None:
                    detections = []
                else:
                    detections = detector.detect(resized)

                # update tracking (guarded)
                try:
                    tracked = t.update(detections)
                except Exception as e:
                    logger.exception("Tracker update failed (camera1): {}", e)
                    tracked = last_tracked

                last_tracked = tracked
            else:
                tracked = last_tracked

            # If tracker used was local (temporary), we drop it (do not assign back)
            if not is_local:
                # global tracker_1 remains as-is
                pass

            # Draw detections (detector handles drawing)
            if detector:
                resized = detector.draw_tracked_detections(resized, tracked)

            # compute fps safely
            elapsed = max(1e-6, time.time() - start_time)
            fps = frame_count / elapsed

            # update stats
            current_stats["camera1"] = {
                "fps": round(fps, 1),
                "persons": len(tracked) if tracked is not None else 0,
                "detections": tracked or []
            }

            # emit combined stats periodically (every 5 frames)
            if frame_count % 5 == 0:
                update_combined_stats()

            ret2, buffer = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ret2:
                logger.warning("Failed to encode frame for camera1")
                continue

            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" +
                   buffer.tobytes() + b"\r\n")

        except GeneratorExit:
            # client disconnected, break
            logger.info("GeneratorExit in camera1 generator - client disconnected")
            break
        except Exception as e:
            logger.exception("Unhandled exception in generate_frames_camera1: {}", e)
            # avoid tight error loop — sleep slightly
            time.sleep(0.1)
            # continue loop or break — better to break to let client reconnect cleanly
            break

    # cleanup local resources if any
    try:
        if video_reader_1:
            # don't release video_reader here if other threads rely on it; caller stop_camera handles release
            pass
    except Exception:
        pass


def generate_frames_camera2():
    global detector, video_reader_2, is_running_2, tracker_2, current_stats

    if not video_reader_2:
        logger.error("Camera 2 not initialized")
        if False:
            yield b''
        return

    frame_count = 0
    start_time = time.time()
    process_every = 2
    last_tracked = []

    while is_running_2:
        try:
            ret, frame = video_reader_2.read()
            if not ret or frame is None:
                logger.info("Camera 2 read returned no frame, stopping generator")
                is_running_2 = False
                break

            frame_count += 1
            resized = cv2.resize(frame, (640, 480))

            t, is_local = safe_create_local_tracker(tracker_2, max_age=30, min_hits=3, iou_threshold=0.3)

            if frame_count % process_every == 0:
                if detector is None:
                    detections = []
                else:
                    detections = detector.detect(resized)

                try:
                    tracked = t.update(detections)
                except Exception as e:
                    logger.exception("Tracker update failed (camera2): {}", e)
                    tracked = last_tracked

                last_tracked = tracked
            else:
                tracked = last_tracked

            if detector:
                resized = detector.draw_tracked_detections(resized, tracked)

            elapsed = max(1e-6, time.time() - start_time)
            fps = frame_count / elapsed

            current_stats["camera2"] = {
                "fps": round(fps, 1),
                "persons": len(tracked) if tracked is not None else 0,
                "detections": tracked or []
            }

            if frame_count % 5 == 0:
                update_combined_stats()

            ret2, buffer = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ret2:
                logger.warning("Failed to encode frame for camera2")
                continue

            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" +
                   buffer.tobytes() + b"\r\n")

        except GeneratorExit:
            logger.info("GeneratorExit in camera2 generator - client disconnected")
            break
        except Exception as e:
            logger.exception("Unhandled exception in generate_frames_camera2: {}", e)
            time.sleep(0.1)
            break

# ----------------------------------------------------
# STATS EMISSION
# ----------------------------------------------------
def update_combined_stats():
    # sum persons safely
    try:
        total = int(current_stats.get("camera1", {}).get("persons", 0)) + int(current_stats.get("camera2", {}).get("persons", 0))
    except Exception:
        total = 0
    current_stats["total_persons"] = total

    all_dets = []

    for det in current_stats.get("camera1", {}).get("detections", []) or []:
        # ensure dict-like
        try:
            all_dets.append({**(det or {}), "camera": "Camera 1"})
        except Exception:
            all_dets.append({"camera": "Camera 1", "raw": str(det)})

    for det in current_stats.get("camera2", {}).get("detections", []) or []:
        try:
            all_dets.append({**(det or {}), "camera": "Camera 2"})
        except Exception:
            all_dets.append({"camera": "Camera 2", "raw": str(det)})

    # emit robust payload
    try:
        socketio.emit("stats", {
            "camera1": current_stats.get("camera1", {}),
            "camera2": current_stats.get("camera2", {}),
            "total_persons": total,
            "all_detections": all_dets
        })
    except Exception as e:
        logger.exception("Failed to emit stats via socketio: {}", e)

# ----------------------------------------------------
# ROUTES
# ----------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register")
def register_page():
    """
    Render tourist registration page.
    """
    try:
        return render_template("register.html")
    except Exception as e:
        
        logger.exception("Failed to render register page: {}", e)
        return jsonify({"error": "Failed to load page"}), 500



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
    """
    Start camera stream. Accepts payload:
    { camera: 1|2, source_type: 'webcam'|'video'|'esp32cam', video_path: '...', esp32_url: '...' }
    """
    global video_reader_1, video_reader_2
    global is_running_1, is_running_2
    global tracker_1, tracker_2

    data = request.get_json() or {}
    cam = int(data.get("camera", 1))
    stype = data.get("source_type", "webcam")

    if stype == "webcam":
        source = cam - 1  # device index
    elif stype == "video":
        source = data.get("video_path")
    else:
        source = data.get("esp32_url")

    try:
        if cam == 1:
            # close previous if exists
            if video_reader_1:
                try:
                    video_reader_1.release()
                except Exception:
                    pass
            video_reader_1 = VideoReader(source)
            # create global tracker object so generator can reuse same instance
            tracker_1 = ByteTrack()
            is_running_1 = True
            info = video_reader_1.get_info()
        else:
            if video_reader_2:
                try:
                    video_reader_2.release()
                except Exception:
                    pass
            video_reader_2 = VideoReader(source)
            tracker_2 = ByteTrack()
            is_running_2 = True
            info = video_reader_2.get_info()

        logger.info(f"Started camera {cam} (source={source})")
        # return video metadata to client
        return jsonify({"status": "started", "camera": cam, "video_info": info})
    except Exception as e:
        logger.exception("Failed to start camera %s: %s", cam, e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/stop_camera", methods=["POST"])
def stop_camera():
    """
    Stop camera stream for camera 1 or 2.
    We set is_running flag to False and release VideoReader.
    We avoid setting tracker global to None immediately to prevent generator race;
    instead keep it but allow it to be reused or GC later.
    """
    global video_reader_1, video_reader_2
    global is_running_1, is_running_2
    global tracker_1, tracker_2

    cam = int(request.get_json().get("camera", 1))

    try:
        if cam == 1:
            is_running_1 = False
            if video_reader_1:
                try:
                    video_reader_1.release()
                except Exception:
                    logger.exception("Error releasing video_reader_1")
                video_reader_1 = None
            # do not immediately destroy tracker_1; let it be GC'd later
            tracker_1 = None
        else:
            is_running_2 = False
            if video_reader_2:
                try:
                    video_reader_2.release()
                except Exception:
                    logger.exception("Error releasing video_reader_2")
                video_reader_2 = None
            tracker_2 = None

        logger.info(f"Stopped camera {cam}")
        return jsonify({"status": "stopped", "camera": cam})
    except Exception as e:
        logger.exception("Failed to stop camera %s: %s", cam, e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/register_tourist", methods=["POST"])
def register_tourist():
    global db_manager, mongo_manager

    if not db_manager:
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
    if "face_images" in data and len(data["face_images"]) > 0 and mongo_manager:
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


@app.route("/api/status", methods=["GET"])
def api_status():
    # Unified status endpoint used by the dashboard
    return jsonify({
        "status": "running",
        "camera1_running": bool(is_running_1),
        "camera2_running": bool(is_running_2),
        "camera1": current_stats.get("camera1", {}),
        "camera2": current_stats.get("camera2", {}),
        "total_persons": current_stats.get("total_persons", 0),
        "device": getattr(detector, "device", "none"),
        "model_loaded": detector is not None
    })


# ----------------------------------------------------
# WEBSOCKET EVENTS
# ----------------------------------------------------
@socketio.on("connect")
def handle_connect():
    logger.info("Client connected")
    emit("connected", {"data": "Connected"})
    # when a client connects, push a current stats snapshot immediately
    try:
        socketio.emit("stats", {
            "camera1": current_stats.get("camera1", {}),
            "camera2": current_stats.get("camera2", {}),
            "total_persons": current_stats.get("total_persons", 0),
            "all_detections": []
        })
    except Exception:
        pass


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

    # Instantiate detector (this might be slow)
    try:
        detector = PersonDetector("models/yolov8n.pt", conf_threshold=0.4, img_size=320)
        logger.info("Detector initialized")
    except Exception as e:
        logger.exception("Failed to initialize detector: {}", e)
        detector = None

    # Run socketio/flask app
    socketio.run(app, host="0.0.0.0", port=5000,
                 debug=False, allow_unsafe_werkzeug=True)
