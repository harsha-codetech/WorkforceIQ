# START HERE — Run WorkforceIQ on Windows

This guide assumes you have **never deployed a Flask app before**. Follow it top to bottom.

There are two ways to run the app:

- **Option A — Docker (RECOMMENDED).** One command. You do **not** need to install Python, MySQL, or any libraries. Best for a clean machine.
- **Option B — Local Python.** Use only if you cannot install Docker. Requires installing Python and MySQL yourself.

---

## OPTION A — Docker (recommended)

### A1. Prerequisites (install once)

| Software | Version | Where |
|----------|---------|-------|
| Docker Desktop for Windows | 4.30 or newer | https://www.docker.com/products/docker-desktop/ |

That is the **only** thing you need to install. After installing, **launch Docker Desktop** and wait until the whale icon in the system tray says **"Docker Desktop is running."**

### A2. Open a terminal in the project folder

Press `Win` + `R`, type `powershell`, press Enter. Then paste:

```powershell
cd "C:\Users\Admin\Desktop\WB\WorkforceIQ"
```

### A3. Start everything (build + database + seed + run)

```powershell
docker compose up --build
```

This single command builds the app image, starts MySQL, creates all tables, loads demo data, and starts the web server. The **first run takes 3–8 minutes** (it downloads images and installs libraries). Later runs take seconds.

### A4. Expected output (success looks like this)

You will see a lot of logs. The lines that confirm success:

```
workforceiq-db-1   | ... ready for connections
workforceiq-web-1  | Demo data seeded.
workforceiq-web-1  | [INFO] Starting gunicorn 22.0.0
workforceiq-web-1  | [INFO] Listening at: http://0.0.0.0:5000
```

When you see **"Listening at: http://0.0.0.0:5000"**, the app is ready. Leave this window open (it is running the server).

### A5. Open the app

Open a **second** PowerShell window (or just your browser) and go to:

```
http://localhost:5000
```

Or run:

```powershell
start http://localhost:5000
```

### A6. Log in (demo accounts)

All passwords are: **`Password123`**

| Role | Email | What you see |
|------|-------|--------------|
| Admin | `admin@workforceiq.com` | Full platform: users, modules, assessments, reports |
| Manager | `manager.eng@workforceiq.com` | Their team's performance |
| Employee | `john@workforceiq.com` | Personal dashboard, learning, goals, assessments |

### A7. Stop the app

In the terminal running Docker, press `Ctrl` + `C`. To fully shut down and free the ports:

```powershell
docker compose down
```

To also delete the database (start fresh next time):

```powershell
docker compose down -v
```

---

## OPTION B — Local Python (only if you can't use Docker)

### B1. Prerequisites (install once)

| Software | Version | Notes |
|----------|---------|-------|
| Python | **3.11 or 3.12** | https://www.python.org/downloads/ — during install, TICK **"Add python.exe to PATH"**. Avoid 3.13 for now (some math libraries lack prebuilt installers for it). |
| MySQL Community Server | 8.0 | https://dev.mysql.com/downloads/mysql/ — set the root password to `root` during setup, or remember the one you choose. |

Verify Python is installed:

```powershell
python --version
```

You should see `Python 3.11.x` or `Python 3.12.x`.

### B2. Create the database

Open **MySQL Command Line Client** (installed with MySQL), enter your root password, then run:

```sql
CREATE DATABASE workforceiq CHARACTER SET utf8mb4;
EXIT;
```

### B3. Set up the project

In PowerShell:

```powershell
cd "C:\Users\Admin\Desktop\WB\WorkforceIQ"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> If `Activate.ps1` is blocked with a red "running scripts is disabled" error, run this once, then repeat the activate line:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

### B4. Configure the database connection

```powershell
Copy-Item .env.example .env
```

Open `.env` in Notepad. Make sure this line matches **your** MySQL root password (replace `root:root` → `root:YOURPASSWORD` if different):

```
DATABASE_URL=mysql+pymysql://root:root@localhost:3306/workforceiq?charset=utf8mb4
```

### B5. Create tables + load demo data

```powershell
flask --app run seed-demo
```

Expected output:

```
Demo data seeded.
```

### B6. Start the app

```powershell
python run.py
```

Expected output:

```
 * Running on http://0.0.0.0:5000
```

### B7. Open and log in

Go to **http://localhost:5000** and use the same demo accounts from section A6.

To stop: press `Ctrl` + `C` in the terminal.

---

## Common errors and fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `error during connect ... docker_engine` | Docker Desktop not running | Launch Docker Desktop, wait for "running", retry. |
| `port is already allocated` / `bind: address already in use` (5000) | Another app uses port 5000 | Stop it, or in `docker-compose.yml` change `"5000:5000"` → `"5050:5000"` and open http://localhost:5050. |
| `ports are not available ... 3306` | A local MySQL already uses 3306 | Already fixed — the `db` service no longer publishes 3306 to the host. If you re-added it, comment the `ports:` block under `db` in `docker-compose.yml` back out. |
| Browser shows nothing / connection refused | Server not ready yet | Wait for "Listening at: http://0.0.0.0:5000", then refresh. |
| Login page reloads, never logs in | (Already fixed in this build.) Ensure `SESSION_COOKIE_SECURE=0` when using http | It defaults to 0 — only set 1 behind HTTPS. |
| `Can't connect to MySQL server` (local) | MySQL not started, or wrong password in `.env` | Start the MySQL service; fix `DATABASE_URL` password. |
| `Access denied for user 'root'` | Wrong MySQL password in `.env` | Edit `.env` → put your real root password. |
| `pip install` fails building numpy/pandas | Using Python 3.13 on local install | Use Python 3.11 or 3.12, or use Docker (Option A). |
| `flask : command not found` | Virtual env not activated | Run `.\.venv\Scripts\Activate.ps1` first. |
| `ModuleNotFoundError: pymysql` | Dependencies not installed | Activate the venv, run `pip install -r requirements.txt`. |
| Unknown column / table errors | Tables not created | Run `flask --app run seed-demo` (local) or `docker compose down -v` then `up` (Docker). |
| `'cryptography' package is required for ... caching_sha2_password` | Driver missing crypto for MySQL 8 auth | Already fixed (`cryptography` added to requirements). Rebuild: `docker compose up --build`. |

---

## Quick reference

- App URL: **http://localhost:5000**
- Login: any email below + password **`Password123`**
  - Admin: `admin@workforceiq.com`
  - Manager: `manager.eng@workforceiq.com`
  - Employee: `john@workforceiq.com`
- Full operations guide: see **RUNBOOK.md**
