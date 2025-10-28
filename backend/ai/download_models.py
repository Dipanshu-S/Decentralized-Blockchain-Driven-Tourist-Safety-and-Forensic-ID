from ultralytics import YOLO
import os
import shutil

print("=" * 60)
print("📥 Downloading YOLOv8x Model...")
print("=" * 60)

# Ensure models folder exists before saving
os.makedirs("models", exist_ok=True)

# Define paths
model_filename = "yolov8x.pt"
model_path = os.path.join(os.getcwd(), model_filename)
target_path = os.path.join("models", model_filename)

# Download model using Ultralytics (auto-handles cache)
model = YOLO(model_filename)

# Move downloaded model if it's not already in target
if os.path.exists(model_path):
    try:
        shutil.move(model_path, target_path)
        print(f"✅ Model moved to: {target_path}")
    except Exception as e:
        print(f"⚠️ Warning: Could not move model: {e}")
else:
    if os.path.exists(target_path):
        print("ℹ️ Model already exists in models folder.")
    else:
        print("❌ Model file not found after download. Please retry.")

print("=" * 60)
print("✅ Setup Complete!")
print("=" * 60)
