-- Migration 002: give the tasks table database-level defaults,
-- so rows inserted directly with SQL (e.g. in DBeaver) get the same
-- values the app would fill in. Safe to run more than once.

ALTER TABLE tasks ALTER COLUMN description SET DEFAULT '';
ALTER TABLE tasks ALTER COLUMN created_at  SET DEFAULT NOW();
ALTER TABLE tasks ALTER COLUMN updated_at  SET DEFAULT NOW();
