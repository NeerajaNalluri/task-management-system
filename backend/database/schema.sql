-- Run this in DBeaver if you want to create the database by hand.
-- (Alternatively, "python seed.py" creates the tables for you.)

-- 1) Connected to the default "postgres" database, run:
-- CREATE DATABASE task_management;

-- 2) Then connect to "task_management" and run the rest:

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(80)  NOT NULL UNIQUE,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(10)  NOT NULL DEFAULT 'user',
    created_at    TIMESTAMPTZ  DEFAULT NOW(),
    CONSTRAINT ck_users_role CHECK (role IN ('admin', 'user'))
);

CREATE TABLE IF NOT EXISTS token_blocklist (
    id         SERIAL PRIMARY KEY,
    jti        VARCHAR(36) NOT NULL UNIQUE,
    revoked_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_token_blocklist_jti ON token_blocklist (jti);

CREATE TABLE IF NOT EXISTS tasks (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    description TEXT         NOT NULL DEFAULT '',
    status      VARCHAR(20)  NOT NULL DEFAULT 'todo',
    priority    VARCHAR(10)  NOT NULL DEFAULT 'medium',
    category    VARCHAR(20)  NOT NULL DEFAULT 'general',
    due_date    DATE,
    assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT ck_tasks_status   CHECK (status   IN ('todo', 'in_progress', 'done')),
    CONSTRAINT ck_tasks_priority CHECK (priority IN ('low', 'medium', 'high')),
    CONSTRAINT ck_tasks_category CHECK (category IN ('general', 'development', 'design', 'testing', 'documentation'))
);

CREATE TABLE IF NOT EXISTS oauth_clients (
    id                 SERIAL PRIMARY KEY,
    client_id          VARCHAR(80)  NOT NULL UNIQUE,
    client_secret_hash VARCHAR(255),            -- NULL = public client (browser)
    name               VARCHAR(120) NOT NULL,
    allowed_scopes     TEXT         NOT NULL,   -- space-separated
    grant_types        TEXT         NOT NULL,   -- space-separated
    created_at         TIMESTAMPTZ  DEFAULT NOW()
);
-- Clients are created by "python seed.py" (the secret must be hashed).

-- SELECT t.id, t.title, t.status, t.priority, t.due_date, u.username AS assignee
-- FROM tasks t LEFT JOIN users u ON u.id = t.assigned_to ORDER BY t.due_date;

-- Passwords are stored hashed, so create users with "python seed.py", not plain INSERTs.
-- Useful checks:
-- SELECT id, username, email, role, created_at FROM users;
-- SELECT * FROM token_blocklist ORDER BY revoked_at DESC;
