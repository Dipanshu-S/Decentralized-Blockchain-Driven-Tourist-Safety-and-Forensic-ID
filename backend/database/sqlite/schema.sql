-- Smart Tourist Safety System - SQLite Database Schema
-- Stores ENCRYPTED tourist PII (off-chain)

-- Tourists Table
CREATE TABLE IF NOT EXISTS tourists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    did TEXT UNIQUE NOT NULL,                    -- Digital Identity (links to blockchain)
    id_hash TEXT NOT NULL,                       -- SHA256(Aadhaar/Passport + timestamp + salt)
    
    -- Encrypted PII (AES-256-GCM)
    name_encrypted BLOB NOT NULL,
    id_type TEXT NOT NULL,                       -- 'aadhaar' or 'passport'
    id_number_encrypted BLOB NOT NULL,
    phone_encrypted BLOB,
    email_encrypted BLOB,
    emergency_contact_encrypted BLOB,
    nationality TEXT,
    
    -- Travel Information
    entry_point TEXT NOT NULL,                   -- Airport/Station code
    entry_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    expected_exit_timestamp DATETIME,
    itinerary_encrypted BLOB,                    -- JSON: [{place, date, hotel}...]
    
    -- Status & Security
    status TEXT DEFAULT 'active',                -- active/exited/flagged/suspicious
    risk_level TEXT DEFAULT 'low',               -- low/medium/high
    alerts_count INTEGER DEFAULT 0,
    last_seen_camera TEXT,
    last_seen_timestamp DATETIME,
    
    -- Blockchain linking
    blockchain_tx_id TEXT,                       -- Transaction ID where DID was created
    verification_status TEXT DEFAULT 'pending',  -- pending/verified/failed
    
    -- Metadata
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Encryption metadata
    encryption_key_id TEXT NOT NULL,             -- References which key was used
    encryption_algorithm TEXT DEFAULT 'AES-256-GCM'
);

-- Incidents Table (linked to tourists)
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT UNIQUE NOT NULL,            -- UUID
    tourist_id INTEGER,                          -- Foreign key to tourists
    did TEXT,                                    -- Quick lookup
    
    -- Incident details
    incident_type TEXT NOT NULL,                 -- fight/theft/medical/suspicious/lost
    severity TEXT NOT NULL,                      -- low/medium/high/critical
    description_encrypted BLOB,
    
    -- Location & Time
    camera_id TEXT NOT NULL,
    location TEXT,                               -- Detected location
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Evidence
    video_clip_path TEXT,                        -- Path to saved video segment
    snapshot_path TEXT,                          -- Path to frame snapshot
    tracking_id INTEGER,                         -- ByteTrack ID at incident time
    
    -- Response
    response_status TEXT DEFAULT 'pending',      -- pending/acknowledged/resolved
    assigned_to TEXT,                            -- Officer/Team assigned
    resolved_at DATETIME,
    
    -- Blockchain
    blockchain_tx_id TEXT,                       -- Incident logged on blockchain
    
    FOREIGN KEY (tourist_id) REFERENCES tourists(id)
);

-- Camera Tracking History (for audit trail)
CREATE TABLE IF NOT EXISTS tracking_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tourist_id INTEGER,
    did TEXT,
    camera_id TEXT NOT NULL,
    tracking_id INTEGER NOT NULL,                -- ByteTrack ID
    confidence REAL,
    bbox TEXT,                                   -- JSON: [x1, y1, x2, y2]
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (tourist_id) REFERENCES tourists(id)
);

-- Encryption Keys Management (for key rotation)
CREATE TABLE IF NOT EXISTS encryption_keys (
    key_id TEXT PRIMARY KEY,
    key_encrypted BLOB NOT NULL,                 -- Master key encrypted with system key
    algorithm TEXT DEFAULT 'AES-256-GCM',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    status TEXT DEFAULT 'active',                -- active/expired/revoked
    used_count INTEGER DEFAULT 0
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tourists_did ON tourists(did);
CREATE INDEX IF NOT EXISTS idx_tourists_status ON tourists(status);
CREATE INDEX IF NOT EXISTS idx_tourists_entry_timestamp ON tourists(entry_timestamp);
CREATE INDEX IF NOT EXISTS idx_incidents_tourist_id ON incidents(tourist_id);
CREATE INDEX IF NOT EXISTS idx_incidents_timestamp ON incidents(timestamp);
CREATE INDEX IF NOT EXISTS idx_tracking_history_did ON tracking_history(did);
CREATE INDEX IF NOT EXISTS idx_tracking_history_timestamp ON tracking_history(timestamp);

-- Triggers for updated_at
CREATE TRIGGER IF NOT EXISTS update_tourists_timestamp 
AFTER UPDATE ON tourists
BEGIN
    UPDATE tourists SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
