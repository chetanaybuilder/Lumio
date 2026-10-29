-- Migration 0001_init.sql: Complete Production DDL for VexoVault
-- Supports PostgreSQL 16+ with pgvector and pg_trgm

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    google_sub text NOT NULL UNIQUE,
    email text NOT NULL UNIQUE,
    email_verified boolean NOT NULL DEFAULT false,
    full_name text,
    avatar_url text,
    class_level smallint CHECK (class_level BETWEEN 9 AND 12),
    board text NOT NULL DEFAULT 'CBSE' CHECK (board = 'CBSE'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    last_login_at timestamptz,
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    family_id uuid NOT NULL,
    refresh_token_hash char(64) NOT NULL UNIQUE,
    user_agent text,
    ip inet,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    replaced_by uuid REFERENCES auth_sessions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_auth_sessions_user ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_family ON auth_sessions(family_id);

CREATE TABLE IF NOT EXISTS documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title text NOT NULL,
    subject text,
    class_level smallint CHECK (class_level BETWEEN 9 AND 12),
    original_filename text NOT NULL,
    r2_key text NOT NULL UNIQUE,
    r2_upload_id text,
    size_bytes bigint CHECK (size_bytes > 0 AND size_bytes <= 52428800),
    sha256 char(64),
    page_count integer,
    ocr_page_count integer NOT NULL DEFAULT 0,
    status text NOT NULL DEFAULT 'uploading' CHECK (status IN ('uploading','uploaded','queued','processing','ready','failed')),
    error_code text,
    error_detail text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, sha256)
);

CREATE INDEX IF NOT EXISTS ix_documents_user_created ON documents(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    kind text NOT NULL DEFAULT 'ingest' CHECK (kind IN ('ingest','generate_notes','generate_paper')),
    payload jsonb NOT NULL DEFAULT '{}',
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','succeeded','failed','dead')),
    stage text,
    attempts integer NOT NULL DEFAULT 0,
    max_attempts integer NOT NULL DEFAULT 3,
    last_completed_page integer NOT NULL DEFAULT 0,
    progress_pct smallint NOT NULL DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),
    locked_by text,
    heartbeat_at timestamptz,
    run_after timestamptz NOT NULL DEFAULT now(),
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
);

CREATE INDEX IF NOT EXISTS ix_jobs_claim ON ingestion_jobs(status, run_after);

CREATE TABLE IF NOT EXISTS document_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    page_start integer NOT NULL,
    page_end integer NOT NULL,
    heading_path text[] NOT NULL DEFAULT '{}',
    content text NOT NULL,
    token_count integer NOT NULL,
    has_math boolean NOT NULL DEFAULT false,
    math_invalid boolean NOT NULL DEFAULT false,
    embedding vector(768),
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS ix_chunks_doc ON document_chunks(document_id, chunk_index);
CREATE INDEX IF NOT EXISTS ix_chunks_user ON document_chunks(user_id);
CREATE INDEX IF NOT EXISTS ix_chunks_tsv ON document_chunks USING gin(tsv);
CREATE INDEX IF NOT EXISTS ix_chunks_embedding ON document_chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS syllabus_topics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_key text NOT NULL UNIQUE,
    class_level smallint NOT NULL CHECK (class_level BETWEEN 9 AND 12),
    subject text NOT NULL,
    chapter_no integer NOT NULL,
    chapter_title text NOT NULL,
    parent_id uuid REFERENCES syllabus_topics(id) ON DELETE CASCADE,
    title text NOT NULL,
    ordinal integer NOT NULL DEFAULT 0,
    weightage_marks numeric(4,1),
    syllabus_year text NOT NULL,
    source_url text NOT NULL,
    embedding vector(768)
);

CREATE INDEX IF NOT EXISTS ix_syllabus_lookup ON syllabus_topics(class_level, subject, chapter_no);

CREATE TABLE IF NOT EXISTS exam_blueprints (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    class_level smallint NOT NULL CHECK (class_level BETWEEN 9 AND 12),
    subject text NOT NULL,
    syllabus_year text NOT NULL,
    total_marks integer NOT NULL,
    duration_min integer NOT NULL,
    spec jsonb NOT NULL,
    source_url text NOT NULL,
    UNIQUE (class_level, subject, syllabus_year)
);

CREATE TABLE IF NOT EXISTS study_notes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    topic_id uuid REFERENCES syllabus_topics(id) ON DELETE SET NULL,
    title text NOT NULL,
    scope jsonb NOT NULL DEFAULT '{}',
    content_md text NOT NULL,
    math_invalid boolean NOT NULL DEFAULT false,
    model text NOT NULL,
    prompt_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_notes_user ON study_notes(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS coverage_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id uuid NOT NULL REFERENCES study_notes(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    syllabus_year text NOT NULL,
    total_topics integer NOT NULL,
    covered_topics integer NOT NULL,
    missing jsonb NOT NULL DEFAULT '[]',
    score numeric(5,2) NOT NULL CHECK (score BETWEEN 0 AND 100),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS flashcards (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    note_id uuid REFERENCES study_notes(id) ON DELETE SET NULL,
    source_chunk_id uuid REFERENCES document_chunks(id) ON DELETE SET NULL,
    topic_id uuid REFERENCES syllabus_topics(id) ON DELETE SET NULL,
    front text NOT NULL,
    back text NOT NULL,
    tags text[] NOT NULL DEFAULT '{}',
    ease_factor real NOT NULL DEFAULT 2.5 CHECK (ease_factor >= 1.3),
    interval_days integer NOT NULL DEFAULT 0,
    repetitions integer NOT NULL DEFAULT 0,
    due_at timestamptz NOT NULL DEFAULT now(),
    last_reviewed_at timestamptz,
    suspended boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, front)
);

CREATE INDEX IF NOT EXISTS ix_flash_due ON flashcards(user_id, due_at) WHERE NOT suspended;

CREATE TABLE IF NOT EXISTS cheat_sheets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    title text NOT NULL,
    content_md text NOT NULL,
    formula_count integer NOT NULL DEFAULT 0,
    math_invalid boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quizzes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
    blueprint_id uuid REFERENCES exam_blueprints(id) ON DELETE SET NULL,
    mode text NOT NULL CHECK (mode IN ('quick','full_mock')),
    class_level smallint NOT NULL,
    subject text NOT NULL,
    total_marks integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id uuid NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    section char(1) NOT NULL CHECK (section BETWEEN 'A' AND 'E'),
    q_no integer NOT NULL,
    q_type text NOT NULL CHECK (q_type IN ('mcq','assertion_reason','vsa','sa','la','case_based')),
    marks numeric(4,1) NOT NULL CHECK (marks > 0),
    question_md text NOT NULL,
    options jsonb,
    answer_md text NOT NULL,
    marking_scheme jsonb NOT NULL,
    topic_id uuid REFERENCES syllabus_topics(id) ON DELETE SET NULL,
    difficulty text CHECK (difficulty IN ('easy','medium','hard')),
    source_chunk_ids uuid[] NOT NULL DEFAULT '{}',
    math_invalid boolean NOT NULL DEFAULT false,
    UNIQUE (quiz_id, q_no)
);

CREATE TABLE IF NOT EXISTS user_quiz_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quiz_id uuid NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress','submitted','evaluated')),
    answers jsonb NOT NULL DEFAULT '{}',
    score numeric(6,2),
    max_score numeric(6,2),
    time_spent_sec integer,
    started_at timestamptz NOT NULL DEFAULT now(),
    submitted_at timestamptz
);

CREATE INDEX IF NOT EXISTS ix_attempts_user ON user_quiz_attempts(user_id, started_at DESC);

CREATE TABLE IF NOT EXISTS answer_evaluations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    attempt_id uuid REFERENCES user_quiz_attempts(id) ON DELETE CASCADE,
    question_id uuid REFERENCES quiz_questions(id) ON DELETE SET NULL,
    question_text text NOT NULL,
    answer_text text NOT NULL,
    max_marks numeric(4,1) NOT NULL,
    awarded_marks numeric(4,1) NOT NULL CHECK (awarded_marks >= 0),
    step_breakdown jsonb NOT NULL,
    feedback_md text NOT NULL,
    model text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (awarded_marks <= max_marks)
);

CREATE TABLE IF NOT EXISTS user_mistakes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_id uuid REFERENCES quiz_questions(id) ON DELETE SET NULL,
    attempt_id uuid REFERENCES user_quiz_attempts(id) ON DELETE SET NULL,
    topic_id uuid REFERENCES syllabus_topics(id) ON DELETE SET NULL,
    category text NOT NULL CHECK (category IN ('concept_gap','formula_recall','calculation_error','unit_error','misread_question','incomplete_steps','diagram_error')),
    student_answer text,
    correct_answer text NOT NULL,
    explanation_md text NOT NULL,
    times_missed integer NOT NULL DEFAULT 1,
    resolved boolean NOT NULL DEFAULT false,
    last_missed_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_mistake_user_question ON user_mistakes(user_id, question_id) WHERE question_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_mistake_user_topic ON user_mistakes(user_id, topic_id) WHERE NOT resolved;

CREATE TABLE IF NOT EXISTS mistake_drills (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mistake_id uuid NOT NULL REFERENCES user_mistakes(id) ON DELETE CASCADE,
    questions jsonb NOT NULL,
    score numeric(5,2),
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS tutor_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
    topic_id uuid REFERENCES syllabus_topics(id) ON DELETE SET NULL,
    title text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tutor_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES tutor_sessions(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('user','assistant')),
    content text NOT NULL,
    hint_level smallint CHECK (hint_level BETWEEN 0 AND 4),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_tutor_msgs ON tutor_messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS exam_targets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    class_level smallint NOT NULL,
    subject text NOT NULL,
    exam_date date NOT NULL,
    daily_minutes integer NOT NULL DEFAULT 90 CHECK (daily_minutes BETWEEN 15 AND 600),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, class_level, subject, exam_date)
);

CREATE TABLE IF NOT EXISTS roadmap_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exam_target_id uuid NOT NULL REFERENCES exam_targets(id) ON DELETE CASCADE,
    topic_id uuid NOT NULL REFERENCES syllabus_topics(id) ON DELETE CASCADE,
    plan_date date NOT NULL,
    task_type text NOT NULL CHECK (task_type IN ('learn','revise','drill','mock')),
    est_minutes integer NOT NULL,
    priority_score numeric(8,4) NOT NULL,
    done_at timestamptz,
    UNIQUE (exam_target_id, topic_id, plan_date, task_type)
);

CREATE INDEX IF NOT EXISTS ix_roadmap_day ON roadmap_items(user_id, plan_date);

CREATE TABLE IF NOT EXISTS usage_ledger (
    id bigserial PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feature text NOT NULL,
    model text NOT NULL,
    input_tokens integer NOT NULL DEFAULT 0,
    output_tokens integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_usage_user_day ON usage_ledger(user_id, created_at);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_users_updated') THEN
        CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_documents_updated') THEN
        CREATE TRIGGER trg_documents_updated BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_notes_updated') THEN
        CREATE TRIGGER trg_notes_updated BEFORE UPDATE ON study_notes FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    END IF;
END $$;
