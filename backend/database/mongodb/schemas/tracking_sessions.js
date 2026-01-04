/**
 * MongoDB Schema: Real-time Tracking Sessions
 * Stores active tracking data from MCPT system
 */

const trackingSessionsSchema = {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["session_id", "camera_id", "tracking_id", "start_timestamp"],
      properties: {
        session_id: {
          bsonType: "string",
          description: "Unique session identifier"
        },
        camera_id: {
          bsonType: "string",
          description: "Camera identifier"
        },
        tracking_id: {
          bsonType: "int",
          description: "ByteTrack assigned ID"
        },
        
        // Association with registered tourist
        did: {
          bsonType: "string",
          description: "Linked DID if matched to registered tourist"
        },
        match_confidence: {
          bsonType: "double",
          description: "Confidence of Re-ID match (0-1)"
        },
        
        // Tracking Data
        tracklets: {
          bsonType: "array",
          description: "Sequence of detections",
          items: {
            bsonType: "object",
            properties: {
              frame_id: { bsonType: "int" },
              timestamp: { bsonType: "date" },
              bbox: {
                bsonType: "array",
                items: { bsonType: "int" },
                minItems: 4,
                maxItems: 4
              },
              confidence: { bsonType: "double" },
              velocity: {
                bsonType: "object",
                properties: {
                  vx: { bsonType: "double" },
                  vy: { bsonType: "double" }
                }
              }
            }
          }
        },
        
        // Session Metadata
        start_timestamp: { bsonType: "date" },
        last_seen_timestamp: { bsonType: "date" },
        end_timestamp: { bsonType: "date" },
        duration_seconds: { bsonType: "int" },
        
        // Status
        status: {
          bsonType: "string",
          enum: ["active", "lost", "exited", "transferred"],
          description: "Current tracking status"
        },
        
        // Cross-camera transfer
        transferred_to_camera: { bsonType: "string" },
        transfer_timestamp: { bsonType: "date" },
        
        // Analytics
        total_detections: { bsonType: "int" },
        avg_confidence: { bsonType: "double" },
        trajectory_path: {
          bsonType: "array",
          description: "Simplified path through camera view",
          items: {
            bsonType: "object",
            properties: {
              x: { bsonType: "int" },
              y: { bsonType: "int" },
              timestamp: { bsonType: "date" }
            }
          }
        }
      }
    }
  }
};

// Indexes
db.tracking_sessions.createIndex({ "session_id": 1 }, { unique: true });
db.tracking_sessions.createIndex({ "camera_id": 1, "tracking_id": 1 });
db.tracking_sessions.createIndex({ "did": 1 });
db.tracking_sessions.createIndex({ "status": 1 });
db.tracking_sessions.createIndex({ "start_timestamp": -1 });
