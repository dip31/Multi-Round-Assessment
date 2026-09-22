# Database Schema

`sql
CREATE TABLE aptitude_topics (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
)

CREATE TABLE assessment_policies (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	session_duration_minutes INTEGER NOT NULL, 
	round_duration_minutes INTEGER NOT NULL, 
	max_attempts INTEGER, 
	resume_allowed BOOLEAN NOT NULL, 
	exit_allowed BOOLEAN NOT NULL, 
	progression_mode VARCHAR(20) NOT NULL, 
	progression_config JSONB NOT NULL, 
	created_at DATETIME DEFAULT now() NOT NULL, 
	updated_at DATETIME DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
)

CREATE TABLE users (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	email VARCHAR(150) NOT NULL, 
	password_hash VARCHAR NOT NULL, 
	role VARCHAR(20) DEFAULT 'student' NOT NULL, 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	is_verified BOOLEAN DEFAULT false NOT NULL, 
	created_at DATETIME DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
)

CREATE TABLE aptitude_questions (
	id INTEGER NOT NULL, 
	question_text TEXT NOT NULL, 
	option_a TEXT NOT NULL, 
	option_b TEXT NOT NULL, 
	option_c TEXT NOT NULL, 
	option_d TEXT NOT NULL, 
	correct_option VARCHAR(1) NOT NULL, 
	difficulty VARCHAR(10) NOT NULL, 
	topic_id INTEGER, 
	version INTEGER DEFAULT 1 NOT NULL, 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	created_by INTEGER, 
	created_at DATETIME DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(topic_id) REFERENCES aptitude_topics (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

CREATE TABLE assessment_contexts (
	id INTEGER NOT NULL, 
	mode VARCHAR(50) NOT NULL, 
	purpose VARCHAR(100), 
	created_by_id INTEGER, 
	student_id INTEGER, 
	company_name VARCHAR(200), 
	target_role VARCHAR(100), 
	jd_text TEXT, 
	availability_start DATETIME, 
	availability_end DATETIME, 
	policy_id INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_at DATETIME DEFAULT now() NOT NULL, 
	completed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_id) REFERENCES users (id), 
	FOREIGN KEY(student_id) REFERENCES users (id), 
	FOREIGN KEY(policy_id) REFERENCES assessment_policies (id)
)

CREATE TABLE coding_problems (
	id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	description TEXT NOT NULL, 
	difficulty VARCHAR(10), 
	tags TEXT, 
	input_format TEXT, 
	output_format TEXT, 
	constraints TEXT, 
	created_by INTEGER, 
	created_at DATETIME DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

CREATE TABLE faculty_profiles (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	department VARCHAR(100) NOT NULL, 
	designation VARCHAR(100) NOT NULL, 
	institution VARCHAR(200) NOT NULL, 
	employee_id VARCHAR(50), 
	bio TEXT, 
	created_at DATETIME DEFAULT now() NOT NULL, 
	updated_at DATETIME DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

CREATE TABLE rl_attempt_log (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	session_id INTEGER, 
	question_id INTEGER, 
	difficulty TEXT, 
	state_before TEXT, 
	action_taken TEXT, 
	reward FLOAT, 
	state_after TEXT, 
	response_time FLOAT, 
	is_correct BOOLEAN, 
	created_at DATETIME DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

CREATE TABLE rl_q_table (
	user_id INTEGER NOT NULL, 
	state TEXT NOT NULL, 
	action TEXT NOT NULL, 
	q_value FLOAT, 
	visit_count INTEGER, 
	updated_at DATETIME DEFAULT now(), 
	PRIMARY KEY (user_id, state, action), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

CREATE TABLE student_profiles (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	roll_number VARCHAR(50), 
	department VARCHAR(100) NOT NULL, 
	cgpa FLOAT NOT NULL, 
	graduation_year INTEGER NOT NULL, 
	backlogs_count INTEGER NOT NULL, 
	institution VARCHAR(200) NOT NULL, 
	target_role VARCHAR(100), 
	skills_json JSONB NOT NULL, 
	phone_number VARCHAR(20), 
	mobile_no VARCHAR(50), 
	full_name VARCHAR(150), 
	college_email_id VARCHAR(150), 
	gender VARCHAR(50), 
	date_of_birth VARCHAR(50), 
	nationality VARCHAR(100), 
	tenth_marks FLOAT, 
	twelfth_marks FLOAT, 
	bio TEXT, 
	portfolio_data JSONB DEFAULT '{}' NOT NULL, 
	created_at DATETIME DEFAULT now() NOT NULL, 
	updated_at DATETIME DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

CREATE TABLE tpo_profiles (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	institution VARCHAR(200) NOT NULL, 
	designation VARCHAR(100) NOT NULL, 
	contact_email VARCHAR(150), 
	contact_phone VARCHAR(20), 
	bio TEXT, 
	created_at DATETIME DEFAULT now() NOT NULL, 
	updated_at DATETIME DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

CREATE TABLE user_resumes (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	cv_name VARCHAR(200) NOT NULL, 
	cv_type VARCHAR(100) NOT NULL, 
	file_name VARCHAR(255) NOT NULL, 
	file_path VARCHAR(500) NOT NULL, 
	file_size INTEGER NOT NULL, 
	resume_text TEXT, 
	parsed_skills JSONB NOT NULL, 
	parsed_projects JSONB NOT NULL, 
	uploaded_at DATETIME DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

CREATE TABLE admin_question_feedback (
	id INTEGER NOT NULL, 
	question_id INTEGER NOT NULL, 
	admin_id INTEGER, 
	action VARCHAR(20) NOT NULL, 
	suggestion TEXT, 
	created_at DATETIME DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(question_id) REFERENCES aptitude_questions (id) ON DELETE CASCADE, 
	FOREIGN KEY(admin_id) REFERENCES users (id) ON DELETE SET NULL
)

CREATE TABLE assessment_sessions (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	context_id INTEGER, 
	status VARCHAR(20) DEFAULT 'not_started' NOT NULL, 
	started_at DATETIME DEFAULT now() NOT NULL, 
	expires_at DATETIME, 
	completed_at DATETIME, 
	total_score FLOAT DEFAULT 0 NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(context_id) REFERENCES assessment_contexts (id)
)

CREATE TABLE coding_test_cases (
	id INTEGER NOT NULL, 
	problem_id INTEGER NOT NULL, 
	input_data TEXT NOT NULL, 
	expected_output TEXT NOT NULL, 
	is_hidden BOOLEAN DEFAULT true NOT NULL, 
	case_order INTEGER DEFAULT 0 NOT NULL, 
	explanation TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(problem_id) REFERENCES coding_problems (id) ON DELETE CASCADE
)

CREATE TABLE advanced_proctoring_events (
	id INTEGER NOT NULL, 
	session_id INTEGER NOT NULL, 
	event_type VARCHAR(50) NOT NULL, 
	confidence FLOAT, 
	event_metadata JSON, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES assessment_sessions (id) ON DELETE CASCADE
)

CREATE TABLE approved_question_pools (
	id INTEGER NOT NULL, 
	session_id INTEGER NOT NULL, 
	extracted_skills JSONB DEFAULT '[]' NOT NULL, 
	extracted_projects JSONB DEFAULT '{}' NOT NULL, 
	question_pool JSONB NOT NULL, 
	admin_approved BOOLEAN DEFAULT false NOT NULL, 
	approved_by INTEGER, 
	approved_at DATETIME, 
	detected_role VARCHAR(50), 
	created_at DATETIME DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES assessment_sessions (id) ON DELETE CASCADE, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
)

CREATE TABLE assessment_rounds (
	id INTEGER NOT NULL, 
	session_id INTEGER NOT NULL, 
	round_type VARCHAR(20) NOT NULL, 
	status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
	score FLOAT DEFAULT 0 NOT NULL, 
	max_questions INTEGER DEFAULT 20 NOT NULL, 
	started_at DATETIME DEFAULT now() NOT NULL, 
	expires_at DATETIME, 
	completed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES assessment_sessions (id) ON DELETE CASCADE
)

CREATE TABLE interview_sessions (
	id INTEGER NOT NULL, 
	session_id INTEGER NOT NULL, 
	phase VARCHAR(20) DEFAULT 'HR' NOT NULL, 
	current_turn INTEGER DEFAULT '0' NOT NULL, 
	total_turns INTEGER DEFAULT '10' NOT NULL, 
	rl_state JSONB DEFAULT '{}' NOT NULL, 
	status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL, 
	completion_reason VARCHAR(30), 
	completed_at DATETIME, 
	created_at DATETIME DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES assessment_sessions (id) ON DELETE CASCADE
)

CREATE TABLE proctoring_events (
	id INTEGER NOT NULL, 
	session_id INTEGER NOT NULL, 
	event_type VARCHAR(50) NOT NULL, 
	event_metadata TEXT, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES assessment_sessions (id) ON DELETE CASCADE
)

CREATE TABLE aptitude_attempts (
	id INTEGER NOT NULL, 
	round_id INTEGER NOT NULL, 
	question_id INTEGER NOT NULL, 
	attempt_number INTEGER NOT NULL, 
	selected_option VARCHAR(1), 
	is_correct BOOLEAN, 
	response_time FLOAT, 
	difficulty VARCHAR(10), 
	reward FLOAT, 
	attempted_at DATETIME DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(round_id) REFERENCES assessment_rounds (id) ON DELETE CASCADE, 
	FOREIGN KEY(question_id) REFERENCES aptitude_questions (id)
)

CREATE TABLE coding_submissions (
	id INTEGER NOT NULL, 
	round_id INTEGER NOT NULL, 
	problem_id INTEGER NOT NULL, 
	code TEXT NOT NULL, 
	language VARCHAR(50), 
	judge0_token VARCHAR(100), 
	status VARCHAR(30), 
	score FLOAT, 
	execution_time FLOAT, 
	memory_used INTEGER, 
	submitted_at DATETIME DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(round_id) REFERENCES assessment_rounds (id) ON DELETE CASCADE, 
	FOREIGN KEY(problem_id) REFERENCES coding_problems (id)
)

CREATE TABLE interview_turns (
	id INTEGER NOT NULL, 
	interview_id INTEGER NOT NULL, 
	turn_number INTEGER NOT NULL, 
	question_text TEXT NOT NULL, 
	question_difficulty VARCHAR(10), 
	candidate_response TEXT, 
	response_time_sec FLOAT, 
	content_score FLOAT, 
	final_score FLOAT, 
	intent VARCHAR(10), 
	behavioral_snapshot JSONB DEFAULT '{}' NOT NULL, 
	rl_reward FLOAT, 
	is_followup BOOLEAN DEFAULT false NOT NULL, 
	followup_number INTEGER DEFAULT 0 NOT NULL, 
	parent_turn_id INTEGER, 
	created_at DATETIME DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(interview_id) REFERENCES interview_sessions (id) ON DELETE CASCADE, 
	FOREIGN KEY(parent_turn_id) REFERENCES interview_turns (id)
)

CREATE TABLE proctoring_violations (
	id INTEGER NOT NULL, 
	session_id INTEGER NOT NULL, 
	event_type VARCHAR(50) NOT NULL, 
	confidence_score FLOAT, 
	face_count INTEGER, 
	metadata JSONB, 
	created_at DATETIME DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES interview_sessions (id) ON DELETE CASCADE
)

CREATE TABLE rl_sessions (
	id INTEGER NOT NULL, 
	round_id INTEGER NOT NULL, 
	step_number INTEGER NOT NULL, 
	prev_difficulty VARCHAR(10), 
	action_taken VARCHAR(10) NOT NULL, 
	reward_received FLOAT, 
	accuracy_so_far FLOAT, 
	avg_response_time FLOAT, 
	q_values TEXT, 
	created_at DATETIME DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(round_id) REFERENCES assessment_rounds (id) ON DELETE CASCADE
)

CREATE TABLE session_problems (
	id INTEGER NOT NULL, 
	round_id INTEGER NOT NULL, 
	problem_id INTEGER NOT NULL, 
	problem_order INTEGER NOT NULL, 
	marked_for_review BOOLEAN NOT NULL, 
	assigned_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(round_id) REFERENCES assessment_rounds (id) ON DELETE CASCADE, 
	FOREIGN KEY(problem_id) REFERENCES coding_problems (id) ON DELETE CASCADE
)
`
