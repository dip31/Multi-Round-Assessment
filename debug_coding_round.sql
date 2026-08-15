-- Debug script for coding round 400 errors
-- Run this in your PostgreSQL database

-- 1. Check if you have an active coding round
SELECT 
    cr.id as round_id,
    cr.user_id,
    cr.started_at,
    cr.completed_at,
    CASE 
        WHEN cr.completed_at IS NULL THEN 'ACTIVE'
        ELSE 'COMPLETED'
    END as status,
    NOW() - cr.started_at as elapsed_time
FROM coding_rounds cr
WHERE cr.user_id = (SELECT id FROM users ORDER BY id DESC LIMIT 1) -- Replace with your user_id
ORDER BY cr.started_at DESC
LIMIT 5;

-- 2. Check if problems are assigned to your active round
SELECT 
    sp.id,
    sp.round_id,
    sp.problem_id,
    sp.problem_order,
    sp.assigned_at,
    cp.title as problem_title
FROM session_problems sp
JOIN coding_rounds cr ON sp.round_id = cr.id
JOIN coding_problems cp ON sp.problem_id = cp.id
WHERE cr.user_id = (SELECT id FROM users ORDER BY id DESC LIMIT 1) -- Replace with your user_id
AND cr.completed_at IS NULL
ORDER BY sp.problem_order;

-- 3. Check if coding problems exist in the database
SELECT COUNT(*) as total_problems FROM coding_problems;
SELECT id, title, difficulty FROM coding_problems LIMIT 5;

-- 4. Check if test cases exist for problems
SELECT 
    cp.id as problem_id,
    cp.title,
    COUNT(ctc.id) as test_case_count,
    COUNT(CASE WHEN ctc.is_hidden THEN 1 END) as hidden_count,
    COUNT(CASE WHEN NOT ctc.is_hidden THEN 1 END) as visible_count
FROM coding_problems cp
LEFT JOIN coding_test_cases ctc ON cp.id = ctc.problem_id
GROUP BY cp.id, cp.title
LIMIT 10;

-- 5. If you're getting "problem not assigned" error, check specific problem:
-- Replace 123 with the problem_id from your frontend
SELECT 
    sp.id,
    sp.round_id,
    sp.problem_id,
    cr.user_id,
    cr.completed_at
FROM session_problems sp
JOIN coding_rounds cr ON sp.round_id = cr.id
WHERE sp.problem_id = 123  -- Replace with actual problem_id
AND cr.user_id = (SELECT id FROM users ORDER BY id DESC LIMIT 1)  -- Replace with your user_id
AND cr.completed_at IS NULL;

-- 6. Check if round has expired (time limit check)
SELECT 
    cr.id as round_id,
    cr.started_at,
    cr.started_at + INTERVAL '30 minutes' as expected_end_time,  -- Adjust if your time limit differs
    NOW() as current_time,
    CASE 
        WHEN NOW() > cr.started_at + INTERVAL '30 minutes' THEN 'EXPIRED'
        ELSE 'ACTIVE'
    END as time_status
FROM coding_rounds cr
WHERE cr.user_id = (SELECT id FROM users ORDER BY id DESC LIMIT 1)  -- Replace with your user_id
AND cr.completed_at IS NULL;

-- 7. Fix: Mark expired round as completed
-- Uncomment and run if round shows as EXPIRED above
-- UPDATE coding_rounds 
-- SET completed_at = NOW()
-- WHERE id = <round_id_from_query_6>
-- AND completed_at IS NULL;
