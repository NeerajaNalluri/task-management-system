-- Migration 001: add a "category" to every task.
-- Safe to run more than once (IF NOT EXISTS / DROP ... IF EXISTS).
-- seed.py runs this automatically; you can also run it in DBeaver on task_management.

ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS category VARCHAR(20) NOT NULL DEFAULT 'general';

ALTER TABLE tasks DROP CONSTRAINT IF EXISTS ck_tasks_category;
ALTER TABLE tasks
    ADD CONSTRAINT ck_tasks_category
    CHECK (category IN ('general', 'development', 'design', 'testing', 'documentation'));
