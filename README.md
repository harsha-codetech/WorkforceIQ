# WorkforceIQ™

Employee Growth & Performance Intelligence Platform (Flask + MySQL).

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
# App: http://localhost:5000  (demo data auto-seeded)
```

## Local development

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env                                # set DATABASE_URL
flask --app run seed-demo                           # create tables + demo data
python run.py
```

## CLI

```bash
flask --app run init-db            # create tables
flask --app run seed-demo          # demo org/users/content
flask --app run recompute-scores --period monthly
```

## Demo accounts (password: `Password123`)

| Role | Email |
|------|-------|
| Admin | admin@workforceiq.com |
| Manager | manager.eng@workforceiq.com |
| Employee | john@workforceiq.com |

## Stack
Flask · SQLAlchemy · MySQL · Bootstrap 5 · Chart.js · Pandas/NumPy · OpenPyXL · ReportLab · AWS S3 (local fallback).
