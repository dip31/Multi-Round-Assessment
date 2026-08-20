-- Update proctoring_events table schema
-- This script updates the existing table to use session_id instead of round_id

-- First, drop the existing table if it exists with wrong schema
DROP TABLE IF EXISTS proctoring_events CASCADE;

-- Create the proctoring_events table with correct schema
CREATE TABLE proctoring_events (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (session_id)
        REFERENCES assessment_sessions(id) ON DELETE CASCADE
);

-- Create index for performance
CREATE INDEX idx_proctoring_session
ON proctoring_events(session_id);

-- Add some sample data for testing
INSERT INTO proctoring_events (session_id, event_type, event_metadata)
SELECT 
    s.id,
    'camera_permission_denied',
    '{"test": "sample_data"}'
FROM assessment_sessions s
WHERE s.status = 'in_progress'
LIMIT 1;
