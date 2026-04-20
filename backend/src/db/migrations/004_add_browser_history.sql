CREATE TABLE IF NOT EXISTS browser_history (
    id           SERIAL PRIMARY KEY,
    session_id   TEXT NOT NULL,
    roll_no      TEXT NOT NULL,
    url          TEXT NOT NULL,
    title        TEXT,
    visit_count  INTEGER DEFAULT 1,
    last_visited DOUBLE PRECISION,
    browser      TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (session_id, roll_no, url)
);
CREATE INDEX IF NOT EXISTS idx_browser_history_session ON browser_history (session_id, roll_no);
