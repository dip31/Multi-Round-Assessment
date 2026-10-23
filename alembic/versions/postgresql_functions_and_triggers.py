"""Add PostgreSQL functions and triggers from baseline backup

Revision ID: pg_functions_triggers
Revises: post_baseline_consolidated
Create Date: 2026-10-21

Adds functions and triggers not captured in Alembic migrations:
- calculate_session_risk_score
- cleanup_old_proctoring_events
- update_event_risk_score (trigger function)
- trigger_update_event_risk_score on advanced_proctoring_events
- update_updated_at_column (trigger function) and triggers on tables with updated_at
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'pg_functions_triggers'
down_revision: Union[str, None] = 'post_baseline_consolidated'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ============================================
# FUNCTIONS
# ============================================

CALCULATE_SESSION_RISK_SCORE = """
CREATE OR REPLACE FUNCTION public.calculate_session_risk_score(p_session_id integer)
RETURNS double precision
LANGUAGE plpgsql
AS $function$
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
    
    final_score := CASE 
        WHEN event_count > 0 THEN LEAST(total_weighted_score / event_count, 1.0)
        ELSE 0.0
    END;
    
    RETURN COALESCE(final_score, 0.0);
END;
$function$
"""

CLEANUP_OLD_PROCTORING_EVENTS = """
CREATE OR REPLACE FUNCTION public.cleanup_old_proctoring_events(days_to_keep integer DEFAULT 90)
RETURNS integer
LANGUAGE plpgsql
AS $function$
DECLARE
    deleted_count INTEGER := 0;
    batch_count INTEGER := 0;
    total_deleted INTEGER := 0;
BEGIN
    LOOP
        DELETE FROM advanced_proctoring_events 
        WHERE id IN (
            SELECT id FROM advanced_proctoring_events
            WHERE created_at < CURRENT_DATE - INTERVAL '1 day' * days_to_keep
            LIMIT 10000
        );
        
        GET DIAGNOSTICS batch_count = ROW_COUNT;
        total_deleted := total_deleted + batch_count;
        
        EXIT WHEN batch_count = 0;
        
        COMMIT;
        
        PERFORM pg_sleep(0.1);
    END LOOP;
    
    RETURN total_deleted;
END;
$function$
"""

UPDATE_EVENT_RISK_SCORE = """
CREATE OR REPLACE FUNCTION public.update_event_risk_score()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    raw_score FLOAT;
BEGIN
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

    NEW.round_type := 'APTITUDE';

    NEW.event_metadata := COALESCE(NEW.event_metadata, '{}');
    NEW.event_metadata := jsonb_set(
        NEW.event_metadata, 
        '{risk_score}', 
        to_jsonb(LEAST(raw_score, 1.0))
    );

    RETURN NEW;
END;
$function$
"""

UPDATE_UPDATED_AT_COLUMN = """
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


# ============================================
# TRIGGERS
# ============================================

TRIGGER_UPDATE_EVENT_RISK_SCORE = """
CREATE TRIGGER trigger_update_event_risk_score
BEFORE INSERT OR UPDATE ON public.advanced_proctoring_events
FOR EACH ROW EXECUTE FUNCTION update_event_risk_score();
"""

# Tables with updated_at column that need the trigger
UPDATED_AT_TABLES = [
    'student_profiles',
    'faculty_profiles',
    'tpo_profiles',
    'assessment_policies',
    'dynamic_interviewers',
]


def upgrade() -> None:
    # Create functions
    op.execute(CALCULATE_SESSION_RISK_SCORE)
    op.execute(CLEANUP_OLD_PROCTORING_EVENTS)
    op.execute(UPDATE_EVENT_RISK_SCORE)
    op.execute(UPDATE_UPDATED_AT_COLUMN)

    # Create trigger on advanced_proctoring_events
    op.execute(TRIGGER_UPDATE_EVENT_RISK_SCORE)

    # Create update_updated_at triggers on tables with updated_at column
    for table in UPDATED_AT_TABLES:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade() -> None:
    # Drop update_updated_at triggers
    for table in UPDATED_AT_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")

    # Drop advanced_proctoring_events trigger
    op.execute("DROP TRIGGER IF EXISTS trigger_update_event_risk_score ON advanced_proctoring_events;")

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS public.update_updated_at_column();")
    op.execute("DROP FUNCTION IF EXISTS public.update_event_risk_score();")
    op.execute("DROP FUNCTION IF EXISTS public.cleanup_old_proctoring_events(integer);")
    op.execute("DROP FUNCTION IF EXISTS public.calculate_session_risk_score(integer);")