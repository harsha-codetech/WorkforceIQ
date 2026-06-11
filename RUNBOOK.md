# WorkforceIQ — Operations Runbook

Operational reference for running, seeding, troubleshooting, and maintaining WorkforceIQ.
For first-time setup, read **START_HERE.md** first.

---

## 1. Architecture at a glance

| Layer | Technology |
|-------|-----------|
| Web framework | Flask 3 (application factory + 12 blueprints) |
| ORM / DB | SQLAlchemy → MySQL 8.0 (`mysql+pymysql`) |
| Auth | Flask-Login (sessions) + Flask-WTF (CSRF) |
| Analytics | pandas, numpy (Growth Score engine) |
| Reports | ReportLab (PDF), OpenPyXL (Excel), csv (CSV) |
| File storage | AWS S3 when configured, else local `app/static/uploads` |
| Frontend | Bootstrap 5, Chart.js (CDN), Jinja templates |
| WSGI server | gunicorn (Docker/Linux); Flask dev server (local Windows) |

Entry points:
- `run.py` — local development server (loads `.env`, `python run.py`).
- `wsgi.py` — production WSGI target (`gunicorn wsgi:app`).
- `config.py` — `development` / `production` / `testing` configs.

---

## 2. Configuration (environment variables)

Set via `.env` (local) or the `environment:` block in `docker-compose.yml` (Docker).

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `SECRET_KEY` | Yes (prod) | dev value | Session signing key. Change in production. |
| `FLASK_CONFIG` | No | `development` | `development` / `production` / `testing`. |
| `DATABASE_URL` | Yes | local MySQL | SQLAlchemy connection string. |
| `SESSION_COOKIE_SECURE` | No | `0` | Set `1` only when served over HTTPS. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_S3_BUCKET` / `AWS_S3_REGION` | No | unset | S3 uploads. If unset, files save to local disk. |
| `MAIL_SERVER` / `MAIL_PORT` / `MAIL_USE_TLS` / `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_SENDER` | No | unset | SMTP email. If unset, notifications are dashboard-only. |

---

## 3. Running

### Docker (recommended)
```powershell
docker compose up --build      # build, start DB, seed, run
docker compose up              # subsequent runs (no rebuild)
docker compose down            # stop
docker compose down -v         # stop + wipe database volume
docker compose logs -f web     # tail application logs
```

### Local
```powershell
.\.venv\Scripts\Activate.ps1
flask --app run seed-demo      # first time only (creates tables + demo data)
python run.py                  # start dev server on :5000
```

---

## 4. Database lifecycle (CLI)

All commands run inside the app context.

| Command | Effect |
|---------|--------|
| `flask --app run init-db` | Create all tables (no data). |
| `flask --app run seed-demo` | Create tables + load demo org/users/content (idempotent). |
| `flask --app run recompute-scores --period monthly` | Recalculate Growth Scores. `--period` = `weekly`/`monthly`/`quarterly`. |

In Docker, replace `--app run` with `--app wsgi`, e.g.:
```powershell
docker compose exec web flask --app wsgi recompute-scores --period weekly
```

**Growth Score formula** (recomputed by the command above):
`0.30·Learning + 0.30·Assessment + 0.20·Goals + 0.10·SkillGrowth + 0.10·Consistency`
Categories: ≥90 Elite · ≥75 High Performer · ≥60 Good · ≥40 Needs Improvement · <40 Critical.

---

## 5. Demo accounts

Password for all: **`Password123`**

| Role | Email |
|------|-------|
| Admin | `admin@workforceiq.com` |
| Manager (Engineering) | `manager.eng@workforceiq.com` |
| Manager (Data) | `manager.data@workforceiq.com` |
| Manager (Cloud) | `manager.cloud@workforceiq.com` |
| Employees | `john@`, `jane@`, `raj@`, `sara@`, `tom@`, `nina@` `workforceiq.com` |

---

## 6. Module / route map

| Area | URL prefix | Key routes |
|------|-----------|-----------|
| Auth | `/` | `/login`, `/logout`, `/forgot-password`, `/account/password` |
| Dashboards | `/dashboard` | role-aware (admin/manager/employee) |
| Learning | `/learning` | catalog, `/modules/new`, `/modules/<id>`, `/modules/<id>/assign` |
| Assessments | `/assessments` | list, `/new`, `/<id>/manage`, `/<id>/take`, `/grading`, `/attempt/<id>/grade`, `/<id>/analytics` |
| Goals | `/goals` | list, `/new`, `/<id>/status` |
| Skills | `/skills` | matrix, `/employee/<id>`, `/catalog` |
| Intelligence | `/intelligence` | workforce analytics dashboard |
| Leaderboard | `/leaderboard` | `?period=weekly|monthly|quarterly` |
| Badges | `/badges` | catalog, `/employee/<id>`, `/refresh` |
| Reports | `/reports` | generate PDF/Excel/CSV |
| Notifications | `/notifications` | list, `/read-all` |
| API (JSON) | `/api` | `/learning/<id>/progress`, `/charts/score/<id>`, `/charts/assessment/<id>` |
| Admin | `/admin` | `/users`, `/users/new`, `/departments` |

---

## 7. Role-based access (enforced server-side)

| Capability | Admin | Manager | Employee |
|------------|:-----:|:-------:|:--------:|
| Manage users/departments, upload modules, create assessments, grade | ✅ | ❌ | ❌ |
| View any employee in org | ✅ | ❌ | ❌ |
| View own team only | ✅ | ✅ (direct reports) | ❌ |
| Own learning/goals/assessments | ✅ | ✅ | ✅ |
| Organization reports | ✅ | ❌ | ❌ |

Scope is computed from `users.manager_id` / `department_id`. Unauthorized access returns **403**.

---

## 8. Reports

Generated on demand from `/reports`:
- **Employee** — single person's learning, assessments, skills, Growth Score.
- **Team** — manager's direct reports (manager/admin).
- **Organization** — all employees + org averages (admin only).

Formats: PDF (ReportLab), Excel (OpenPyXL), CSV. Files stream to the browser as a download; an audit row is written to `report_exports`.

---

## 9. File uploads

- Learning modules (PDF/PPT/internal) and manual assessment submissions.
- Stored in S3 if AWS env vars are set; otherwise in `app/static/uploads/`.
- Limits: 50 MB per file; allowed extensions validated server-side.

---

## 10. Tests

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD=1   # avoids unrelated global pytest plugins
python -m pytest tests/test_smoke.py -q
```
Covers app boot + seed, login + dashboard, Growth Score computation. Uses an in-memory SQLite DB (no MySQL needed).

---

## 11. Troubleshooting

| Symptom | Diagnosis | Action |
|---------|-----------|--------|
| Web container restarts repeatedly | DB not ready / bad `DATABASE_URL` | `docker compose logs web`; confirm `db` healthy; check connection string. |
| `Can't connect to MySQL server` | DB down or wrong host/port | Local: start MySQL. Docker: ensure `db` service healthy. |
| Login reloads without entering | Secure cookie over http | Keep `SESSION_COOKIE_SECURE=0` for http; only `1` behind HTTPS. |
| `403` on a page | Role lacks permission | Expected; log in with an account that has access. |
| `pip` build failure (numpy/pandas) | Python 3.13 locally | Use Python 3.11/3.12, or run via Docker. |
| Port 5000/3306 in use | Another process bound | Change the host port mapping in `docker-compose.yml`. |
| Stale/odd data | Old seed | `docker compose down -v && docker compose up` (Docker) or recreate the MySQL database (local). |
| Emails not sending | SMTP not configured | Expected; notifications still appear in the dashboard. |

---

## 12. Production notes

- Set a strong `SECRET_KEY`; set `FLASK_CONFIG=production`.
- Terminate TLS at a reverse proxy and set `SESSION_COOKIE_SECURE=1`.
- Run `recompute-scores` on a schedule (e.g., nightly) for fresh dashboards/leaderboards.
- Configure S3 + SMTP env vars for durable storage and email delivery.
- Scale with gunicorn `--workers` (already 3 in the image); back with a managed MySQL.
