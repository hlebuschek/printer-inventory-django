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

## Error Handling & Debugging

The project includes a comprehensive error handling system with beautiful error pages, logging, and security middleware.

### Debug Mode Management

```bash
# Check current DEBUG status
python manage.py toggle_debug --status

# Enable DEBUG mode (development)
python manage.py toggle_debug --on

# Disable DEBUG mode (production)  
python manage.py toggle_debug --off

# Test error handlers
python manage.py test_errors --test-all
```

### Testing Error Pages

**In DEBUG mode**, visit `/debug/errors/` for an interactive error testing menu.

**In PRODUCTION mode**, error handlers activate automatically:
- Custom error pages (400, 403, 404, 405, 500)
- Error logging to `logs/django.log` and `logs/errors.log`
- Security headers and CSRF protection
- User-friendly error messages

### Error Types Handled

- **400** - Bad Request
- **403** - Access Denied / CSRF Failures  
- **404** - Page Not Found
- **405** - Method Not Allowed
- **500** - Internal Server Error

See `docs/ERROR_HANDLING.md` for complete documentation.

---