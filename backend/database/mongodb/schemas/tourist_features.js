/**
 * MongoDB Schema: Tourist Visual Features (MCPT Feature Bank)
 * Stores Re-ID embeddings, pose data, and appearance features
 */

const touristFeaturesSchema = {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["feature_id", "did", "capture_timestamp", "reid_embedding"],
      properties: {
        feature_id: {
          bsonType: "string",
          description: "Unique feature identifier (UUID)"
        },
        did: {
          bsonType: "string",
          description: "Digital Identity linking to blockchain"
        },
        
        // Re-ID Features (for cross-camera matching)
        reid_embedding: {
          bsonType: "array",
          description: "512-dimensional Re-ID feature vector from OSNet",
          items: { bsonType: "double" },
          minItems: 512,
          maxItems: 512
        },
        
        // Pose Features (from HRNet)
        pose_keypoints: {
          bsonType: "array",
          description: "17 body keypoints [x, y, confidence]",
          items: {
            bsonType: "object",
            properties: {
              x: { bsonType: "double" },
              y: { bsonType: "double" },
              confidence: { bsonType: "double" }
            }
          }
        },
        
        // Appearance Features
        appearance: {
          bsonType: "object",
          properties: {
            clothing_color_top: { bsonType: "string" },
            clothing_color_bottom: { bsonType: "string" },
            height_estimate: { bsonType: "int" },
            body_orientation: { bsonType: "string" }
          }
        },
        
        // Capture Metadata
        capture_timestamp: {
          bsonType: "date",
          description: "When features were extracted"
        },
        camera_id: {
          bsonType: "string",
          description: "Camera ID where captured"
        },
        capture_angles: {
          bsonType: "array",
          description: "Multiple angle captures",
          items: {
            bsonType: "object",
            properties: {
              angle: { bsonType: "string" },  // front/left/right/back
              embedding: { bsonType: "array" },
              quality_score: { bsonType: "double" }
            }
          }
        },
        
        // Quality Metrics
        feature_quality: {
          bsonType: "double",
          description: "Overall quality score (0-1)"
        },
        occlusion_score: {
          bsonType: "double",
          description: "How much person is occluded (0-1)"
        },
        
        // Blockchain Reference
        blockchain_tx_id: {
          bsonType: "string",
          description: "Transaction ID where feature hash is stored"
        },
        
        // Metadata
        created_at: { bsonType: "date" },
        updated_at: { bsonType: "date" }
      }
    }
  }
};

// Indexes
db.tourist_features.createIndex({ "did": 1 });
db.tourist_features.createIndex({ "feature_id": 1 }, { unique: true });
db.tourist_features.createIndex({ "capture_timestamp": -1 });
db.tourist_features.createIndex({ "camera_id": 1 });
