# Phase 3: Authentication & Roles — Design Document

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add HIPAA-hardened authentication, role-based access control, data scoping, and audit logging to Call Monitor.

**Approach:** Auth middleware layer (Approach A) — JWT tokens with FastAPI dependency injection for auth, role checks, and data scoping. Same pattern as the Lionel project.

---

## 1. Data Model

### New Tables

**Team**
- `id` (PK), `name` (unique), `created_at`

**User**
- `id` (PK), `email` (unique), `hashed_password`, `name`, `role` (worker/supervisor/admin), `team_id` (FK to Team, nullable), `is_active`, `password_changed_at`, `created_at`

**AuditLog**
- `id` (PK), `user_id` (FK to User), `action` (enum: view_call, view_transcript, upload_call, delete_call, submit_review, update_review, login, logout, create_user, update_role), `resource_type` (e.g. "call", "review"), `resource_id` (nullable), `details` (JSON, optional), `ip_address`, `timestamp`

### Modified Tables

**Call** — add `uploaded_by` (FK to User, nullable). Existing calls get `uploaded_by = NULL`.

---

## 2. Authentication & HIPAA Hardening

### Auth Flow
- `POST /api/auth/register` — first user auto-becomes admin
- `POST /api/auth/login` — returns access token (15min) + refresh token (7 days)
- `POST /api/auth/refresh` — rotate tokens
- Dependencies: `get_current_user`, `require_admin`, `require_supervisor_or_admin`

### Password Complexity
- Minimum 8 characters
- At least one uppercase, one lowercase, one number

### Auto-Logoff
- Frontend inactivity timer: 15 minutes of no mouse/keyboard activity
- Warning shown at 13 minutes
- Clear tokens + redirect to login
- Server-side: 15min access token expiry provides enforcement

### Audit Logging
- Reusable `log_audit()` helper called explicitly in route handlers
- Captures: user, action, resource type/id, IP address, timestamp

---

## 3. Role Permissions & Data Scoping

| Action | Worker | Supervisor | Admin |
|--------|--------|------------|-------|
| Upload calls | Own calls only | Own calls only | Yes |
| View calls | Own calls only | Own team's calls | All calls |
| View transcripts | Own calls only | Own team's calls | All calls |
| Delete calls | No | Own team's calls | All calls |
| Submit/edit reviews | No | Own team's calls | All calls |
| View dashboard/stats | Own calls only | Team-scoped stats | Global stats |
| Manage users | No | No | Yes |
| Manage teams | No | No | Yes |
| View audit log | No | No | Yes |

### Scoping Implementation
A `get_accessible_calls()` dependency filters queries by role:
- **Worker:** `Call.uploaded_by == current_user.id`
- **Supervisor:** `Call.uploaded_by` in users where `user.team_id == current_user.team_id`
- **Admin:** no filter

403 returned if user accesses a call outside their scope.

---

## 4. API Surface

### New Endpoints
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | /api/auth/register | Public | Register (first user = admin) |
| POST | /api/auth/login | Public | Returns access + refresh tokens |
| POST | /api/auth/refresh | Public | Rotate tokens |
| GET | /api/users/me | Authenticated | Current user profile |
| GET | /api/users | Admin | List all users |
| PUT | /api/users/{id} | Admin | Update role/team (no self-demotion) |
| GET | /api/teams | Authenticated | List teams |
| POST | /api/teams | Admin | Create team |
| GET | /api/audit-log | Admin | Paginated audit log |

### Modified Endpoints (add auth + scoping + audit)
| Method | Path | Change |
|--------|------|--------|
| GET | /api/calls | + auth, scope filter, audit |
| GET | /api/calls/{id} | + auth, scope check, audit view_call |
| GET | /api/calls/{id}/status | + auth, scope check |
| GET | /api/calls/stats | + auth, scope-filtered stats |
| POST | /api/calls/upload | + auth, set uploaded_by, audit upload_call |
| DELETE | /api/calls/{id} | + auth, scope check, audit delete_call |
| GET | /api/calls/{id}/scores | + auth, scope check |
| GET | /api/calls/{id}/review | + auth, scope check |
| POST | /api/calls/{id}/review | + auth, require supervisor/admin, audit submit_review |

**GET /api/health** stays public.

---

## 5. Frontend Changes

### New Components
- `Login.jsx` — login/register form
- `AuthContext.jsx` — user state, tokens in localStorage, login/logout/getMe
- `ProtectedRoute.jsx` — redirect to login if unauthenticated
- `InactivityTimer.jsx` — 15min idle auto-logoff, 13min warning
- `AuditLog.jsx` — admin-only paginated table

### Modified Components
- `App.jsx` — wrap in AuthProvider, add ProtectedRoute, add login + admin routes
- `Navbar.jsx` — user name, role badge, logout, conditional admin links
- `CallDetail.jsx` — hide review panel for workers
- `api/client.js` — Bearer token interceptor + 401 refresh logic

Most existing components unchanged — scoping happens server-side.

---

## 6. Sub-Phases

**3a: Backend auth infrastructure**
User/Team/AuditLog models, auth utilities (hash/JWT), dependencies, auth router, user/team routers, password complexity. Tests for all new endpoints.

**3b: Retrofit existing endpoints**
Add auth + scoping to call/review/stats endpoints. Add `uploaded_by` to Call. Add audit logging. Update existing tests to use auth headers.

**3c: Frontend**
AuthContext, Login, ProtectedRoute, InactivityTimer, api/client.js token interceptor, App/Navbar updates, AuditLog component, hide review panel for workers.
