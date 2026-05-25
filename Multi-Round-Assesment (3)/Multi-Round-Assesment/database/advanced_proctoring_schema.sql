-- Advanced Proctoring Events Table for AI-Based Online Proctoring System
-- Extends basic proctoring with computer vision, audio analysis, and confidence scoring

-- Drop existing table if it exists (for development)
DROP TABLE IF EXISTS advanced_proctoring_events;

-- Create advanced_proctoring_events table
CREATE TABLE advanced_proctoring_events (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(10) NOT NULL DEFAULT 'INFO',
    round_type VARCHAR(20) CHECK (round_type IN ('APTITUDE', 'CODING', 'INTERVIEW')),
    confidence FLOAT CHECK (confidence >= 0.0 AND confidence <= 1.0),
    event_metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint
    FOREIGN KEY (session_id) 
        REFERENCES assessment_sessions(id) 
        ON DELETE CASCADE,
    
    -- Check constraint for severity (separate line)
    CONSTRAINT chk_severity CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL'))
);

-- Create indexes for performance (remove redundant id index)
CREATE INDEX IF NOT EXISTS idx_proctoring_session ON advanced_proctoring_events(session_id);
CREATE INDEX IF NOT EXISTS idx_proctoring_event_type ON advanced_proctoring_events(event_type);
CREATE INDEX IF NOT EXISTS idx_proctoring_severity ON advanced_proctoring_events(severity);
CREATE INDEX IF NOT EXISTS idx_proctoring_round ON advanced_proctoring_events(round_type);
CREATE INDEX IF NOT EXISTS idx_proctoring_created_at ON advanced_proctoring_events(created_at);

-- Create GIN index for JSONB metadata queries
CREATE INDEX IF NOT EXISTS idx_proctoring_metadata ON advanced_proctoring_events USING GIN(event_metadata);

-- Deduplication index (prevents duplicate burst events within same second)
CREATE UNIQUE INDEX IF NOT EXISTS idx_proctoring_dedup
ON advanced_proctoring_events (session_id, event_type, date_trunc('second', created_at));

-- Add comments for documentation
COMMENT ON TABLE advanced_proctoring_events IS 'Advanced proctoring events with AI-based detection capabilities including computer vision, audio analysis, and confidence scoring';
COMMENT ON COLUMN advanced_proctoring_events.session_id IS 'Reference to assessment session';
COMMENT ON COLUMN advanced_proctoring_events.event_type IS 'Type of proctoring event (e.g., MULTIPLE_PERSON_DETECTED, FACE_NOT_VISIBLE, etc.)';
COMMENT ON COLUMN advanced_proctoring_events.severity IS 'Severity level: INFO, WARNING, or CRITICAL';
COMMENT ON COLUMN advanced_proctoring_events.round_type IS 'Assessment round type: APTITUDE, CODING, or INTERVIEW';
COMMENT ON COLUMN advanced_proctoring_events.confidence IS 'AI model confidence score (0.0-1.0) for detection';
COMMENT ON COLUMN advanced_proctoring_events.event_metadata IS 'Detailed detection metadata including bounding boxes, landmarks, audio features, etc.';

-- Create function to calculate session risk score with proper bounds
CREATE OR REPLACE FUNCTION calculate_session_risk_score(p_session_id INTEGER)
RETURNS FLOAT AS $$
DECLARE
    total_weighted_score FLOAT;
    event_count INTEGER;
    final_score FLOAT;
BEGIN
    SELECT 
        SUM(CASE 
            WHEN event_type = 'MULTIPLE_PERSON_DETECTED' THEN 0.9 * confidence
            WHEN event_type = 'CAMERA_PERMISSION_DENIED' THEN 0.9 * confidence
            WHEN event_type = 'PAGE_RELOAD' THEN 0.8 * confidence
            WHEN event_type = 'FACE_NOT_VISIBLE' THEN 0.7 * confidence
            WHEN event_type = 'VOICE_ACTIVITY_DETECTED' THEN 0.6 * confidence
            WHEN event_type = 'FULLSCREEN_EXIT' THEN 0.4 * confidence
            WHEN event_type = 'HEAD_TURN_DETECTED' THEN 0.4 * confidence
            WHEN event_type = 'MOUTH_MOVEMENT_DETECTED' THEN 0.3 * confidence
            WHEN event_type = 'TAB_SWITCH' THEN 0.3 * confidence
            WHEN event_type = 'LOOKING_AWAY' THEN 0.3 * confidence
            WHEN event_type = 'IDLE_ACTIVITY' THEN 0.2 * confidence
            ELSE 0.1 * confidence
        END)
    INTO total_weighted_score
    FROM advanced_proctoring_events
    WHERE session_id = p_session_id;
    
    SELECT COUNT(*)
    INTO event_count
    FROM advanced_proctoring_events
    WHERE session_id = p_session_id;
    
    -- Calculate average and cap at 1.0
    final_score := CASE 
        WHEN event_count >0 THEN LEAST(total_weighted_score / event_count, 1.0)
        ELSE 0.0
    END;
    
    RETURN COALESCE(final_score, 0.0);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_session_risk_score(INTEGER) IS 'Calculate comprehensive risk score for a session based on all proctoring events, capped at 1.0';

-- Create trigger to automatically update risk score and severity in event metadata
CREATE OR REPLACE FUNCTION update_event_risk_score()
RETURNS TRIGGER AS $$
DECLARE
    raw_score FLOAT;
BEGIN
    -- Calculate raw risk score based on event type
    raw_score := CASE NEW.event_type
        WHEN 'MULTIPLE_PERSON_DETECTED'  THEN 0.9
        WHEN 'CAMERA_PERMISSION_DENIED'  THEN 0.9
        WHEN 'PAGE_RELOAD'               THEN 0.8
        WHEN 'FACE_NOT_VISIBLE'          THEN 0.7
        WHEN 'VOICE_ACTIVITY_DETECTED'   THEN 0.6
        WHEN 'FULLSCREEN_EXIT'           THEN 0.4
        WHEN 'HEAD_TURN_DETECTED'        THEN 0.4
        WHEN 'MOUTH_MOVEMENT_DETECTED'   THEN 0.3
        WHEN 'TAB_SWITCH'               THEN 0.3
        WHEN 'LOOKING_AWAY'             THEN 0.3
        WHEN 'IDLE_ACTIVITY'            THEN 0.2
        ELSE 0.1
    END * NEW.confidence;

    -- Set severity based on event type
    NEW.severity := CASE NEW.event_type
        WHEN 'MULTIPLE_PERSON_DETECTED' THEN 'CRITICAL'
        WHEN 'FACE_NOT_VISIBLE'         THEN 'CRITICAL'
        WHEN 'CAMERA_PERMISSION_DENIED' THEN 'CRITICAL'
        WHEN 'PAGE_RELOAD'               THEN 'CRITICAL'
        WHEN 'TAB_SWITCH'               THEN 'WARNING'
        WHEN 'FULLSCREEN_EXIT'          THEN 'WARNING'
        WHEN 'HEAD_TURN_DETECTED'       THEN 'WARNING'
        WHEN 'VOICE_ACTIVITY_DETECTED'  THEN 'WARNING'
        WHEN 'MOUTH_MOVEMENT_DETECTED'   THEN 'WARNING'
        ELSE 'INFO'
    END;

    -- Set round_type based on session (would need to join with assessment_sessions)
    -- For now, default to APTITUDE - this should be updated in application layer
    NEW.round_type := 'APTITUDE';

    -- Safe null guard before jsonb_set
    NEW.event_metadata := COALESCE(NEW.event_metadata, '{}');
    NEW.event_metadata := jsonb_set(
        NEW.event_metadata, 
        '{risk_score}', 
        to_jsonb(LEAST(raw_score, 1.0))
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_event_risk_score
    BEFORE INSERT OR UPDATE ON advanced_proctoring_events
    FOR EACH ROW
    EXECUTE FUNCTION update_event_risk_score();

-- Create view for high-risk sessions analysis using proper function
CREATE OR REPLACE VIEW high_risk_sessions AS
SELECT 
    session_id,
    COUNT(*) as event_count,
    calculate_session_risk_score(session_id) as avg_risk_score,
    MAX(CAST(event_metadata->>'risk_score' AS FLOAT)) as max_risk_score,
    COUNT(*) FILTER (WHERE severity = 'CRITICAL') as critical_violation_count,
    COUNT(*) FILTER (WHERE severity = 'WARNING') as warning_violation_count,
    COUNT(*) FILTER (WHERE event_type = 'MULTIPLE_PERSON_DETECTED') as multiple_person_count,
    COUNT(*) FILTER (WHERE event_type = 'FACE_NOT_VISIBLE') as face_not_visible_count,
    COUNT(*) FILTER (WHERE event_type = 'VOICE_ACTIVITY_DETECTED') as voice_activity_count,
    COUNT(*) FILTER (WHERE event_type IN ('TAB_SWITCH', 'FULLSCREEN_EXIT', 'PAGE_RELOAD')) as browser_violation_count,
    MAX(created_at) as last_activity,
    MIN(created_at) as first_activity
FROM advanced_proctoring_events
GROUP BY session_id
HAVING calculate_session_risk_score(session_id) > 0.5
ORDER BY avg_risk_score DESC;

COMMENT ON VIEW high_risk_sessions IS 'View of sessions with elevated proctoring risk scores for admin dashboard';

-- Create procedure to clean up old proctoring events (batched for performance)
CREATE OR REPLACE FUNCTION cleanup_old_proctoring_events(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER := 0;
    batch_count INTEGER := 0;
    total_deleted INTEGER := 0;
BEGIN
    LOOP
        -- Delete in batches of 10,000 to avoid table locks
        DELETE FROM advanced_proctoring_events 
        WHERE id IN (
            SELECT id FROM advanced_proctoring_events
            WHERE created_at < CURRENT_DATE - INTERVAL '1 day' * days_to_keep
            LIMIT 10000
        );
        
        GET DIAGNOSTICS batch_count = ROW_COUNT;
        total_deleted := total_deleted + batch_count;
        
        -- Exit when no more rows to delete
        EXIT WHEN batch_count = 0;
        
        -- Commit each batch to avoid long transactions
        COMMIT;
        
        -- Optional: Add small delay to reduce load
        PERFORM pg_sleep(0.1);
    END LOOP;
    
    RETURN total_deleted;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_proctoring_events(INTEGER) IS 'Clean up proctoring events older than specified number of days in batches to avoid table locks';

-- Sample data for testing (with proper session existence check)
DO $$
BEGIN
    -- Only insert sample data if session exists
    IF EXISTS (SELECT 1 FROM assessment_sessions WHERE id = 1) THEN
        INSERT INTO advanced_proctoring_events (session_id, event_type, confidence, event_metadata) VALUES
        (1, 'PROCTORING_INITIALIZED', 1.0, '{"timestamp": 1640995200000, "config": {"camera_fps": 30, "processing_fps": 5}}'),
        (1, 'MULTIPLE_PERSON_DETECTED', 0.92, '{"face_count": 2, "detection_boxes": [[100, 100, 200, 200], [300, 100, 400, 200]], "timestamp": 1640995250000}'),
        (1, 'FACE_NOT_VISIBLE', 0.85, '{"visibility_ratio": 0.3, "duration_seconds": 45, "timestamp": 1640995300000}'),
        (1, 'VOICE_ACTIVITY_DETECTED', 0.78, '{"duration_seconds": 12, "amplitude": 0.65, "timestamp": 1640995350000}'),
        (1, 'LOOKING_AWAY', 0.67, '{"gaze_direction": "left", "deviation": 0.45, "timestamp": 1640995400000}'),
        (1, 'HEAD_TURN_DETECTED', 0.73, '{"head_yaw": 42, "confidence": 0.73, "timestamp": 1640995450000}'),
        (1, 'MOUTH_MOVEMENT_DETECTED', 0.61, '{"mouth_opening": 0.025, "timestamp": 1640995500000}'),
        (1, 'TAB_SWITCH', 1.0, '{"timestamp": 1640995550000, "user_agent": "Mozilla/5.0..."}'),
        (1, 'FULLSCREEN_EXIT', 1.0, '{"timestamp": 1640995600000, "was_fullscreen": true}'),
        (1, 'IDLE_ACTIVITY', 1.0, '{"timestamp": 1640995650000, "idle_duration": 60000}');
    END IF;
END $$;
