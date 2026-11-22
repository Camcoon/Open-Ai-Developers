# COMP 3613 TA Allocations (Phase 2 starter)

Flawed baseline **0.2.0** built on [uwidcit/faststart](https://github.com/uwidcit/faststart) (`96ccfce`).

FastStart provides the SSR shell, JWT cookie auth, SQLModel, `manage.py`, and Render/Docker wiring. The ta-allocations scenario adds domain models/services and a JSON API under `/api` (see `/docs`).

## Quick start

```text
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Windows: Copy-Item .env.example .env
python manage.py init
python manage.py run
```

<!-- #recently edited -->
Open http://127.0.0.1:5000 — SSR auth shell; scenario JSON under `/api`. The OpenAPI docs at `/docs` and schema at `/openapi.json` require an admin login.

<!-- #recently edited -->
## Seeded accounts

| Username | Email | Password | Role |
| --- | --- | --- | --- |
| `hod` | `hod@example.com` | `hod-dev` | hod |
| `admin` | `admin@example.com` | `admin` | admin |

Sign in at `/login` as `admin` to view `/docs`. The seeded admin password is for local development; change it before using the app outside development. JSON login: `POST /api/auth/login` with `{"email","password"}`. Allocation endpoints identify the acting HOD with an `X-User-Id` header.

## Student brief

See [`ASSIGNMENT.md`](ASSIGNMENT.md) and [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md).

## Tests

```bash
python -m pytest tests -q
```
