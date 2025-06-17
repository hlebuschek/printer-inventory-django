# Printer Inventory Django

This project provides a Django-based web interface for managing and polling network printers, originally migrated from a Flask service. It supports:

* **CRUD** for printers (add, edit, delete)
* **Inventory polling** via SNMP & HTTP checks
* **Multithreaded bulk polling** with APScheduler & ThreadPoolExecutor
* **Real-time UI updates** via WebSockets (Django Channels + Daphne)
* **Import** of legacy Flask SQLite data

---

## Prerequisites

* **Python 3.12+**
* **Git**
* **Virtual environment** (recommended)

Optional:

* **Daphne** for ASGI server
* **Uvicorn** (alternative ASGI server)

---

## Installation

1. **Create & activate virtualenv**

   ```bash
   python -m venv .venv
   # Windows (PowerShell)
   .\.venv\Scripts\Activate.ps1
   # macOS/Linux
   source .venv/bin/activate
   ```

2. **Install dependencies**

   * **Online** (requires Internet):

     ```bash
     pip install --upgrade pip
     pip install -r requirements.txt
     ```

   * **Offline** (no Internet):

     ```bash
     # pip_packages/ must contain wheels for all requirements
     pip install --no-index --find-links=pip_packages -r requirements.txt
     ```

## Database setup

1. **Migrate**

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

2. **Create superuser**

   ```bash
   python manage.py createsuperuser
   ```

---

## Running the application

### Development server (WSGI)

```bash
python manage.py runserver 0.0.0.0:8000
```

Visit `http://<host>:8000/` in your browser.

### Production-like (ASGI) with Daphne

```bash
# Use module invocation to avoid launcher issues
python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application
```

Open `http://<host>:5000/`. WebSockets will be served at `/ws/inventory/`.

---
