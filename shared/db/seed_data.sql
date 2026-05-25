-- ═══════════════════════════════════════════════════════════════
-- Seed Data — Sample jobs and candidates for development testing
-- ═══════════════════════════════════════════════════════════════

INSERT INTO jobs (id, title, department, location, employment_type, experience_min, experience_max, salary_min, salary_max, skills, status) VALUES
('job-001', 'Senior Python Developer', 'Engineering', 'Bangalore, India', 'full-time', 3, 7, 1500000, 2500000, '["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"]', 'active'),
('job-002', 'ML Engineer', 'Data Science', 'Mumbai, India', 'full-time', 2, 5, 1200000, 2000000, '["Python", "TensorFlow", "PyTorch", "MLOps", "SQL"]', 'draft'),
('job-003', 'Frontend Developer', 'Engineering', 'Remote', 'full-time', 1, 4, 800000, 1500000, '["React", "TypeScript", "CSS", "Next.js", "Figma"]', 'active');

INSERT INTO candidates (id, name, email, phone, location, current_role, experience_years, skills, source, status) VALUES
('cand-001', 'Priya Sharma', 'priya@example.com', '+91-9876543210', 'Bangalore', 'Software Engineer', 4.0, '["Python", "Django", "PostgreSQL", "Docker"]', 'upload', 'parsed'),
('cand-002', 'Rahul Verma', 'rahul@example.com', '+91-9876543211', 'Mumbai', 'Data Scientist', 3.0, '["Python", "TensorFlow", "SQL", "Pandas"]', 'linkedin', 'new');
