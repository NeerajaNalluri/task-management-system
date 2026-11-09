-- Useful queries for the task_management database.
-- In DBeaver: select the task_management database, open an SQL editor (Ctrl+]),
-- put the cursor on one query and press Ctrl+Enter to run it.

-- 1) All users (password is stored as a hash, so we don't show it)
SELECT id, username, email, role, created_at
FROM users
ORDER BY id;

-- 2) All tasks with the assignee's and creator's names
SELECT t.id,
       t.title,
       t.description,
       t.status,
       t.priority,
       t.due_date,
       a.username AS assigned_to,
       c.username AS created_by,
       t.created_at,
       t.updated_at
FROM tasks t
LEFT JOIN users a ON a.id = t.assigned_to
LEFT JOIN users c ON c.id = t.created_by
ORDER BY t.due_date NULLS LAST, t.id;

-- 3) Number of tasks per status
SELECT status, COUNT(*) AS total
FROM tasks
GROUP BY status
ORDER BY status;

-- 4) Tasks per user
SELECT COALESCE(u.username, 'Unassigned') AS assignee,
       COUNT(*) AS total,
       COUNT(*) FILTER (WHERE t.status = 'done') AS done
FROM tasks t
LEFT JOIN users u ON u.id = t.assigned_to
GROUP BY u.username
ORDER BY total DESC;

-- 5) Overdue tasks (past due date and not done)
SELECT t.id, t.title, t.due_date, t.status, u.username AS assigned_to
FROM tasks t
LEFT JOIN users u ON u.id = t.assigned_to
WHERE t.due_date < CURRENT_DATE
  AND t.status <> 'done'
ORDER BY t.due_date;

-- 6) Tasks due in the next 7 days
SELECT id, title, due_date, status
FROM tasks
WHERE due_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
  AND status <> 'done'
ORDER BY due_date;

-- 7) Logged-out (revoked) tokens, newest first
SELECT id, jti, revoked_at
FROM token_blocklist
ORDER BY revoked_at DESC;

-- 8) OAuth clients (secrets are hashed; public clients have none)
SELECT client_id, name,
       CASE WHEN client_secret_hash IS NULL THEN 'public' ELSE 'confidential' END AS type,
       allowed_scopes, grant_types, created_at
FROM oauth_clients
ORDER BY id;

-- 9) Tasks per category, with how many are done
SELECT category,
       COUNT(*) AS total,
       COUNT(*) FILTER (WHERE status = 'done') AS done
FROM tasks
GROUP BY category
ORDER BY total DESC;
