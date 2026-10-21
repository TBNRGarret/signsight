-- ==============================================================================
-- SignSight original five-table schema (reference for migration 0001).
-- Runtime schema is versioned in backend/migrations; initialize/upgrade with:
-- python -m backend.manage migrate
-- This reference omits runtime additions from migrations 0002 through 0005.
-- ==============================================================================

-- 1. Users table (Contributors, Drivers, Reviewers)
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(50) DEFAULT 'contributor', -- 'contributor', 'reviewer', 'admin'
    reputation_score INT DEFAULT 100,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Sign Records (Core Georeferenced Traffic Signs Inventory)
CREATE TABLE IF NOT EXISTS sign_records (
    id VARCHAR(36) PRIMARY KEY,
    predicted_class INT NOT NULL,               -- 0 to 9 (Mapped to Vietnam Taxonomy)
    qcvn_code VARCHAR(20) NOT NULL,             -- e.g. 'P.127 (50)', 'P.102', 'W.227'
    name_vi VARCHAR(255) NOT NULL,              -- e.g. 'Tốc độ tối đa 50 km/h'
    confidence FLOAT NOT NULL,                  -- Confidence score (0.00 - 1.00)
    is_uncertain BOOLEAN DEFAULT FALSE,         -- True if confidence < 0.70
    latitude DOUBLE PRECISION NOT NULL,         -- WGS84 GPS Latitude
    longitude DOUBLE PRECISION NOT NULL,        -- WGS84 GPS Longitude
    location_source VARCHAR(50) DEFAULT 'user_confirmed', -- 'exif', 'device', 'manual'
    status VARCHAR(50) DEFAULT 'active',        -- 'active', 'pending_revalidation', 'expired', 'removed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    created_by VARCHAR(36) REFERENCES users(id)
);

-- 3. Evidence Images (Audit trail & image deduplication)
CREATE TABLE IF NOT EXISTS evidence (
    id VARCHAR(36) PRIMARY KEY,
    record_id VARCHAR(36) REFERENCES sign_records(id) ON DELETE CASCADE,
    image_url VARCHAR(500) NOT NULL,
    image_hash VARCHAR(64) NOT NULL,            -- dHash or SHA-256 for perceptual deduplication
    file_size_bytes INT,
    uploaded_by VARCHAR(36) REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Confirmation Events (Revalidation Log & Audit Trail)
CREATE TABLE IF NOT EXISTS confirmation_events (
    id VARCHAR(36) PRIMARY KEY,
    record_id VARCHAR(36) REFERENCES sign_records(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,                -- 'confirm_existing', 'report_removed', 'report_damaged', 'update_evidence'
    comment TEXT,
    evidence_id VARCHAR(36) REFERENCES evidence(id),
    confirmed_by VARCHAR(36) REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Duplicate Candidates (Near-duplicate spatial & class observation pairs)
CREATE TABLE IF NOT EXISTS duplicate_candidates (
    id VARCHAR(36) PRIMARY KEY,
    new_record_id VARCHAR(36) REFERENCES sign_records(id) ON DELETE CASCADE,
    existing_record_id VARCHAR(36) REFERENCES sign_records(id) ON DELETE CASCADE,
    distance_meters FLOAT NOT NULL,             -- Distance between observations
    class_match BOOLEAN NOT NULL,               -- True if same predicted class
    similarity_score FLOAT DEFAULT 0.0,
    status VARCHAR(50) DEFAULT 'pending_review' -- 'pending_review', 'confirmed_duplicate', 'dismissed'
);

-- Indexes for high-performance spatial & lifecycle querying
CREATE INDEX IF NOT EXISTS idx_signs_location ON sign_records (latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_signs_status ON sign_records (status);
CREATE INDEX IF NOT EXISTS idx_signs_expires_at ON sign_records (expires_at);
CREATE INDEX IF NOT EXISTS idx_evidence_record ON evidence (record_id);
CREATE INDEX IF NOT EXISTS idx_evidence_hash ON evidence (image_hash);
