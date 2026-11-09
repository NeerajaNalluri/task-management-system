# Task Management System

Flask + PostgreSQL backend, plain HTML/CSS/JS frontend, OAuth 2.0 token authentication (JWT Bearer tokens with scopes).

| Role  | View tasks | Create / edit / delete tasks | Manage users | Reports | Logout |
|-------|:---:|:---:|:---:|:---:|:---:|
| Admin | ✅ | ✅ | ✅ | ✅ | ✅ |
| User  | ✅ | ❌ | ❌ | ❌ | ✅ |

## Folder layout

```
task-management-system/
├── backend/
│   ├── app.py               # Flask app; also serves the frontend
│   ├── config.py            # reads settings from .env
│   ├── extensions.py        # db + jwt objects
│   ├── models.py            # User, Task, OAuthClient, TokenBlocklist tables
│   ├── oauth.py             # scopes, client authentication, OAuth error format
│   ├── decorators.py        # @scope_required("tasks:write")
│   ├── routes/auth.py       # /api/auth/token, /revoke, /logout, /me
│   ├── routes/tasks.py      # task CRUD
│   ├── routes/users.py      # user management
│   ├── routes/reports.py    # report summary
│   ├── seed.py              # creates database, tables, starter data, OAuth clients
│   ├── database/schema.sql  # same tables as plain SQL
│   ├── database/queries.sql # handy queries for DBeaver
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── index.html           # login page (Admin / User tabs)
    ├── admin.html           # admin: Dashboard, Users, Reports views
    ├── user.html            # user: read-only dashboard
    ├── css/style.css
    └── js/
        ├── api.js           # OAuth client: login, refresh, revoke, Bearer requests
        ├── ui.js            # shared helpers (icons, toast, api calls)
        ├── login.js         # login form
        ├── dashboard.js     # task views + page navigation
        ├── users.js         # Users view (admin)
        └── reports.js       # Reports view (admin)
```

## Setup

```powershell
cd task-management-system\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then set DB_PASSWORD and JWT_SECRET_KEY
python seed.py              # creates the database, tables, accounts, tasks, OAuth clients
python app.py               # open http://localhost:5000
```

| Login | Username | Password |
|-------|----------|----------|
| Admin | `admin`  | `Admin@123` |
| User  | `user`   | `User@123`  |

In DBeaver: Edit Connection → PostgreSQL tab → tick **Show all databases**, then open
`task_management → Schemas → public → Tables`.

## OAuth 2.0

### Clients
| client_id | Type | Used by |
|---|---|---|
| `taskforge-web` | public (no secret) | the browser app — browser code can't keep a secret |
| `taskforge-cli` | confidential (has a secret) | scripts / Postman. `seed.py` prints the secret once; get a new one with `python seed.py --reset-cli-secret` |

### Scopes
| Scope | Allows | Admin | User |
|---|---|:---:|:---:|
| `tasks:read` | view tasks | ✅ | ✅ |
| `tasks:write` | create, edit, delete tasks | ✅ | |
| `users:manage` | manage accounts | ✅ | |
| `reports:read` | view reports | ✅ | |

A token gets *requested scopes ∩ scopes allowed for the role ∩ scopes allowed for the client*.
If no `scope` is sent, it gets everything the role allows.

### Endpoints
| Endpoint | Purpose |
|---|---|
| `POST /api/auth/token` `grant_type=password` | username + password → `access_token` (30 min) + `refresh_token` (7 days) |
| `POST /api/auth/token` `grant_type=refresh_token` | new access token **and** a new refresh token; the old refresh token stops working (rotation) |
| `POST /api/auth/revoke` | revoke an access or refresh token (RFC 7009) — used by Logout |
| `POST /api/auth/logout` | revoke the token in the `Authorization` header |
| `GET /api/auth/me` | current user + token scopes |

`/token` and `/revoke` take form data (`application/x-www-form-urlencoded`) and need `client_id`
(plus `client_secret`, or HTTP Basic auth, for confidential clients). Errors use the standard
`{"error": "...", "error_description": "..."}` format.

Example with the confidential client:
```bash
curl -X POST http://localhost:5000/api/auth/token \
  -u taskforge-cli:<secret> \
  -d grant_type=password -d username=admin -d password=Admin@123 -d "scope=tasks:read"
```

### Flow
1. Login page → `POST /token` with `client_id=taskforge-web`, `grant_type=password`.
2. Server checks client, password and portal (admin/user tab), then issues tokens containing `role` and `scope`.
3. `js/api.js` sends `Authorization: Bearer <access_token>` on every request.
4. `@scope_required(...)` checks the signature, expiry, revocation, that the user still exists, and the scope → 401 / 403.
5. On a 401 the browser uses the refresh token once (rotation), then retries.
6. Logout revokes both tokens via `/revoke`; they're stored in `token_blocklist`.

If an admin changes someone's role, that person's scopes are re-checked on their next token refresh.

## API

All need `Authorization: Bearer <access_token>`.

| Method | URL | Scope |
|---|---|---|
| GET | `/api/tasks` (optional `?status=todo`) | `tasks:read` |
| GET | `/api/tasks/<id>` | `tasks:read` |
| POST / PUT / DELETE | `/api/tasks`, `/api/tasks/<id>` | `tasks:write` |
| GET / POST | `/api/users` | `users:manage` |
| PUT / DELETE | `/api/users/<id>` | `users:manage` |
| GET | `/api/reports/summary` | `reports:read` |

Task fields: `title` (required), `description`, `status` (`todo` / `in_progress` / `done`),
`priority` (`low` / `medium` / `high`), `due_date` (`YYYY-MM-DD`), `assigned_to` (user id).

User fields: `username` (3-80 chars), `email`, `role` (`admin` / `user`), `password` (8+ chars;
optional on edit). An admin can't delete or demote themselves, and there must always be one admin.
Deleting a user unassigns their tasks.
